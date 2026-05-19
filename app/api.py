from contextlib import asynccontextmanager
from fastapi import FastAPI, APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from pathlib import Path
import re

from app.db import init_db, get_connection, get_db
from app.analyzer import (
    get_or_create_book, get_or_create_unit, get_or_create_lesson,
    add_lesson_text, analyze_and_update_words,
    lookup_word, get_all_new_words_for_lesson,
    list_books, list_units, list_lessons,
    get_full_lesson_path, get_lesson_new_words,
    get_lesson_text, get_lesson_word_forms,
    get_lesson_texts_by_type, update_lesson_text,
    rebuild_word_index,
    get_all_vocab, get_random_quiz_words, get_lesson_quiz_words, get_lesson_quiz_words_by_ids,
    get_mistake_words, record_quiz_result, clear_mistake,
    get_units_word_stats, get_book_word_stats, get_unit_word_detail,
    update_book, update_unit, update_lesson,
    delete_book, delete_unit, delete_lesson,
    reorder_units, reorder_lessons,
    get_excluded_list, add_excluded_word, remove_excluded_word,
    exclude_word_from_vocab, unexclude_word,
)
from app.analyzer import (
    export_textbook, export_all_textbooks, export_quiz_data,
    import_textbooks, import_quiz_data,
)

BASE_DIR = Path(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app):
    init_db()
    yield

app = FastAPI(title="English Learning Helper", lifespan=lifespan)

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


class BookUpdate(BaseModel):
    name: str | None = None
    publisher: str | None = None
    grade: str | None = None
    semester: str | None = None


class UnitUpdate(BaseModel):
    unit_no: int | None = None
    title: str | None = None


class LessonUpdate(BaseModel):
    lesson_no: int | None = None
    title: str | None = None


class ReorderRequest(BaseModel):
    ids: list[int]


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
    books = list_books()
    for b in books:
        stats = get_book_word_stats(b["id"])
        b["total_units"] = stats["total_units"]
        b["total_lessons"] = stats["total_lessons"]
        b["new_count"] = stats["new_count"]
    return books


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
    stats = get_units_word_stats(book_id)
    for u in units:
        s = stats.get(u["id"], {"new_count": 0, "review_count": 0, "lesson_count": 0})
        u["new_count"] = s["new_count"]
        u["review_count"] = s["review_count"]
        u["lesson_count"] = s["lesson_count"]
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
    word_forms = get_lesson_word_forms(lesson_id)
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


@router.get("/lessons/{lesson_id}/texts")
async def api_get_lesson_texts(lesson_id: int):
    texts = get_lesson_texts_by_type(lesson_id)
    return {"lesson_id": lesson_id, "texts": texts, "path": get_full_lesson_path(lesson_id)}


@router.put("/lessons/{lesson_id}/text")
async def api_update_lesson_text(lesson_id: int, req: LessonTextCreate):
    result = update_lesson_text(lesson_id, req.content, req.text_type)
    return result


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


# Unit word detail
@router.get("/units/{unit_id}/word-detail")
async def api_unit_word_detail(unit_id: int):
    return get_unit_word_detail(unit_id)


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


@router.get('/quiz/lessons')
async def api_quiz_lessons(lesson_ids: str = ''):
    if not lesson_ids:
        return {'words': [], 'total': 0}
    ids = [int(x) for x in lesson_ids.split(',') if x.strip()]
    words = get_lesson_quiz_words_by_ids(ids)
    return {'words': words, 'total': len(words)}


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


# --- Management: edit, delete, reorder ---

@router.put('/books/{book_id}')
async def api_update_book(book_id: int, req: BookUpdate):
    try:
        result = update_book(book_id, name=req.name, publisher=req.publisher, grade=req.grade, semester=req.semester)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.put('/units/{unit_id}')
async def api_update_unit(unit_id: int, req: UnitUpdate):
    try:
        result = update_unit(unit_id, unit_no=req.unit_no, title=req.title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.put('/lessons/{lesson_id}')
async def api_update_lesson(lesson_id: int, req: LessonUpdate):
    try:
        result = update_lesson(lesson_id, lesson_no=req.lesson_no, title=req.title)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete('/books/{book_id}')
async def api_delete_book(book_id: int):
    try:
        result = delete_book(book_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete('/units/{unit_id}')
async def api_delete_unit(unit_id: int):
    try:
        result = delete_unit(unit_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.delete('/lessons/{lesson_id}')
async def api_delete_lesson(lesson_id: int):
    try:
        result = delete_lesson(lesson_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return result


@router.put('/books/{book_id}/units/reorder')
async def api_reorder_units(book_id: int, req: ReorderRequest):
    try:
        result = reorder_units(book_id, req.ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result


@router.put('/units/{unit_id}/lessons/reorder')
async def api_reorder_lessons(unit_id: int, req: ReorderRequest):
    try:
        result = reorder_lessons(unit_id, req.ids)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result



# Excluded words management
@router.get('/excluded')
async def api_list_excluded():
    return get_excluded_list()


class ExcludeWordRequest(BaseModel):
    word: str


@router.post('/excluded')
async def api_add_excluded(req: ExcludeWordRequest):
    try:
        return add_excluded_word(req.word)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete('/excluded/{word}')
async def api_remove_excluded(word: str):
    return unexclude_word(word)


@router.post('/words/{word_id}/exclude')
async def api_exclude_word(word_id: int):
    try:
        return exclude_word_from_vocab(word_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post('/words/{word_id}/unexclude')
async def api_unexclude_word(word_id: int):
    """Remove from excluded list so word can be picked up on next text analysis."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT word FROM words WHERE id = ?", (word_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Word not found")
        unexclude_word(row["word"])
        return {"word": row["word"], "unexcluded": True}

# Register router
app.include_router(router)


# --- Export / Import ---

from fastapi.responses import JSONResponse
from fastapi import Query
import json


@app.get("/api/export/textbooks")
async def api_export_all_textbooks():
    data = export_all_textbooks()
    filename = f"textbook_export_all_{data['exported_at'].replace(':','-').replace(' ','_')}.json"
    content = json.dumps(data, ensure_ascii=False, indent=2)
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/textbook/{book_id}")
async def api_export_textbook(book_id: int):
    try:
        data = export_textbook(book_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Book not found")
    book_name = data['books'][0]['name'].replace(' ', '_')
    filename = f"textbook_export_{book_name}_{data['exported_at'].replace(':','-').replace(' ','_')}.json"
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/quiz")
async def api_export_quiz():
    data = export_quiz_data()
    filename = f"quiz_export_{data['exported_at'].replace(':','-').replace(' ','_')}.json"
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


class ImportTextbooksRequest(BaseModel):
    data: dict
    clear: bool = False


@app.post("/api/import/textbooks")
async def api_import_textbooks(req: ImportTextbooksRequest):
    if req.data.get("type") != "textbook":
        raise HTTPException(status_code=400, detail="Invalid data type, expected 'textbook'")
    result = import_textbooks(req.data, clear=req.clear)
    return result


class ImportQuizRequest(BaseModel):
    data: dict
    clear: bool = False


@app.post("/api/import/quiz")
async def api_import_quiz(req: ImportQuizRequest):
    if req.data.get("type") != "quiz":
        raise HTTPException(status_code=400, detail="Invalid data type, expected 'quiz'")
    result = import_quiz_data(req.data, clear=req.clear)
    return result

