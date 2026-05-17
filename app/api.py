from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import re

from app.db import init_db
from app.analyzer import (
    get_or_create_book, get_or_create_unit, get_or_create_lesson,
    add_lesson_text, analyze_and_update_words,
    lookup_word, get_all_new_words_for_lesson,
    list_books, list_units, list_lessons,
    get_full_lesson_path, get_lesson_new_words,
    get_lesson_text, get_lesson_word_forms,
    rebuild_word_index,
    get_all_vocab, get_random_quiz_words, get_lesson_quiz_words,
    get_mistake_words, record_quiz_result, clear_mistake,
)

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="English Learning Helper")

# Mount static files
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


# --- Pydantic models ---

class BookCreate(BaseModel):
    name: str
    publisher: str | None = None
    grade: str | None = None
    semester: str | None = None


class UnitCreate(BaseModel):
    book_id: int
    unit_no: int
    title: str | None = None


class LessonCreate(BaseModel):
    unit_id: int
    lesson_no: int
    title: str | None = None


class LessonTextCreate(BaseModel):
    content: str
    text_type: str = "main"


class BatchImportRequest(BaseModel):
    text: str


# --- Pages ---

@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = BASE_DIR / "templates" / "index.html"
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))




class QuizResultRequest(BaseModel):
    word_id: int
    result: str  # known / unknown
    quiz_type: str = 'random'
    lesson_id: int | None = None

# --- API routes ---
router = APIRouter(prefix="/api")


# Books
@router.get("/books")
async def api_list_books():
    return list_books()


@router.post("/books")
async def api_create_book(req: BookCreate):
    book_id = get_or_create_book(req.name, req.publisher, req.grade, req.semester)
    return {"id": book_id, "name": req.name}


# Units
@router.get("/books/{book_id}/units")
async def api_list_units(book_id: int):
    units = list_units(book_id)
    for u in units:
        u["lessons"] = list_lessons(u["id"])
    return units


@router.post("/units")
async def api_create_unit(req: UnitCreate):
    unit_id = get_or_create_unit(req.book_id, req.unit_no, req.title)
    return {"id": unit_id, "unit_no": req.unit_no}


# Lessons
@router.get("/units/{unit_id}/lessons")
async def api_list_lessons(unit_id: int):
    return list_lessons(unit_id)


@router.post("/lessons")
async def api_create_lesson(req: LessonCreate):
    lesson_id = get_or_create_lesson(req.unit_id, req.lesson_no, req.title)
    return {"id": lesson_id, "lesson_no": req.lesson_no}


# Lesson text
@router.post("/lessons/{lesson_id}/text")
async def api_add_lesson_text(lesson_id: int, req: LessonTextCreate):
    add_lesson_text(lesson_id, req.content, req.text_type)
    new_words = analyze_and_update_words(lesson_id, req.content)
    word_forms = {}
    for lemma in new_words:
        from app.analyzer import get_lesson_word_forms
        wf = get_lesson_word_forms(lesson_id)
        word_forms = wf
    return {
        "lesson_id": lesson_id,
        "new_words": new_words,
        "word_forms": word_forms,
        "path": get_full_lesson_path(lesson_id),
    }


@router.get("/lessons/{lesson_id}/text")
async def api_get_lesson_text(lesson_id: int):
    text = get_lesson_text(lesson_id)
    if text is None:
        raise HTTPException(status_code=404, detail="Lesson text not found")
    return {"lesson_id": lesson_id, "content": text, "path": get_full_lesson_path(lesson_id)}


# Lesson words
@router.get("/lessons/{lesson_id}/words")
async def api_lesson_words(lesson_id: int):
    result = get_all_new_words_for_lesson(lesson_id)
    word_forms = get_lesson_word_forms(lesson_id)
    return {
        "lesson_id": lesson_id,
        "path": get_full_lesson_path(lesson_id),
        "new_words": result["new_words"],
        "review_words": result["review_words"],
        "word_forms": word_forms,
    }


# Word lookup
@router.get("/words/{word:path}")
async def api_lookup_word(word: str):
    result = lookup_word(word)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Word '{word}' not found")
    if result["first_lesson_id"]:
        result["first_lesson_path"] = get_full_lesson_path(result["first_lesson_id"])
    else:
        result["first_lesson_path"] = None
    for lesson in result["lessons"]:
        lesson["path"] = get_full_lesson_path(lesson["lesson_id"])
    return result


# Batch import
@router.post("/import/batch")
async def api_batch_import(req: BatchImportRequest):
    content = req.text
    lines = content.split("\n")
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    content = "\n".join(lines)

    entries = re.split(r"^---\s*$", content, flags=re.MULTILINE)
    results = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        entry_lines = entry.split("\n")
        header = entry_lines[0].strip()
        parts = [p.strip() for p in header.split("|")]
        if len(parts) < 4:
            continue
        book_name = parts[0]
        unit_no = int(parts[1])
        unit_title = parts[2] if len(parts) > 2 and parts[2] else None
        lesson_no = int(parts[3])
        lesson_title = parts[4] if len(parts) > 4 and parts[4] else None
        text_content = "\n".join(entry_lines[1:]).strip()
        if not text_content:
            continue
        book_id = get_or_create_book(book_name)
        unit_id = get_or_create_unit(book_id, unit_no, unit_title)
        lesson_id = get_or_create_lesson(unit_id, lesson_no, lesson_title)
        add_lesson_text(lesson_id, text_content)
        new_words = analyze_and_update_words(lesson_id, text_content)
        results.append({
            "book_name": book_name,
            "unit_no": unit_no,
            "lesson_no": lesson_no,
            "new_word_count": len(new_words),
            "new_words": new_words,
        })
    return {"imported": len(results), "entries": results}


# Rebuild index
@router.post("/rebuild")
async def api_rebuild():
    total = rebuild_word_index()
    return {"total_words": total}




# Vocab (word list)
@router.get('/vocab')
async def api_vocab(q: str | None = None, sort: str = 'alpha'):
    return get_all_vocab(q=q, sort=sort)


# Quiz endpoints
@router.get('/quiz/random')
async def api_quiz_random(count: int = 10):
    words = get_random_quiz_words(count)
    return {'words': words, 'total': len(words)}


@router.get('/quiz/lesson/{lesson_id}')
async def api_quiz_lesson(lesson_id: int):
    words = get_lesson_quiz_words(lesson_id)
    return {'words': words, 'total': len(words), 'lesson_id': lesson_id}


@router.get('/quiz/mistakes')
async def api_quiz_mistakes():
    words = get_mistake_words()
    return {'words': words, 'total': len(words)}


@router.post('/quiz/result')
async def api_quiz_result(req: QuizResultRequest):
    if req.result not in ('known', 'unknown'):
        raise HTTPException(status_code=400, detail='result must be known or unknown')
    return record_quiz_result(req.word_id, req.result, req.quiz_type, req.lesson_id)


# Mistakes (wrong word list)
@router.get('/mistakes')
async def api_list_mistakes():
    return get_mistake_words()


@router.delete('/mistakes/{word_id}')
async def api_clear_mistake(word_id: int):
    return clear_mistake(word_id)


# Register router
app.include_router(router)


@app.on_event("startup")
async def startup():
    init_db()
