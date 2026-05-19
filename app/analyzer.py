import re
import threading
from collections import Counter, defaultdict
from app.db import get_connection, get_db, STOP_WORDS
from datetime import datetime
def sql_placeholders(n: int) -> str:
    """Return a comma-separated list of '?' placeholders."""
    return ",".join("?" * n)

# --- spaCy NLP pipeline (lazy-loaded singleton) ---
_nlp = None


def get_nlp():
    """Load and cache the spaCy English model."""
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# --- Excluded words (user-managed blacklist) ---

def get_excluded_words() -> set[str]:
    """Load all excluded words from DB."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT word FROM excluded_words")
        words = {r["word"].lower() for r in cur.fetchall()}
    return words


_excluded_lock = threading.Lock()
_excluded_cache: set[str] | None = None


def _is_excluded(word: str) -> bool:
    """Check if a word (lowercase) is in the excluded list."""
    global _excluded_cache
    with _excluded_lock:
        if _excluded_cache is None:
            _excluded_cache = get_excluded_words()
        return word.lower() in _excluded_cache


def refresh_excluded_cache():
    """Force reload the excluded words cache."""
    global _excluded_cache
    with _excluded_lock:
        _excluded_cache = get_excluded_words()


# --- Case-sensitive words (not handled by spaCy) ---

CASE_SENSITIVE_MAP: dict[str, str] = {
    "i": "I",
    "mr": "Mr", "mrs": "Mrs", "ms": "Ms", "miss": "Miss",
    "dr": "Dr", "prof": "Prof", "sir": "Sir",
    "mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu",
    "fri": "Fri", "sat": "Sat", "sun": "Sun",
    "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday",
    "thursday": "Thursday", "friday": "Friday", "saturday": "Saturday", "sunday": "Sunday",
    "jan": "Jan", "feb": "Feb", "mar": "Mar", "apr": "Apr",
    "jun": "Jun", "jul": "Jul", "aug": "Aug", "sep": "Sep",
    "oct": "Oct", "nov": "Nov", "dec": "Dec",
    "january": "January", "february": "February", "march": "March",
    "april": "April", "may": "May", "june": "June", "july": "July",
    "august": "August", "september": "September", "october": "October",
    "november": "November", "december": "December",
    "christmas": "Christmas", "easter": "Easter", "halloween": "Halloween",
    "thanksgiving": "Thanksgiving",
    "chinese": "Chinese", "english": "English", "american": "American",
    "japanese": "Japanese", "french": "French", "german": "German",
    "spanish": "Spanish", "korean": "Korean", "italian": "Italian",
    "russian": "Russian", "british": "British", "canadian": "Canadian",
    "australian": "Australian",
    # Acronyms (spaCy may lowercase these)
    "tv": "TV", "dvd": "DVD", "uk": "UK", "usa": "USA",
    "ok": "OK", "pc": "PC", "id": "ID", "cd": "CD",
    # Interjections (spaCy may over-lemmatize)
    "oops": "oops", "wow": "wow", "hey": "hey",
    "hi": "hi", "hello": "hello", "goodbye": "goodbye",
}
CASE_SENSITIVE_LOWER = frozenset(CASE_SENSITIVE_MAP.keys())


# --- Dialogue-tag pre-processing ---
_dialogue_tag_re = re.compile(r"([A-Z][A-Z ]+[A-Z]|ALL):(\s*)")


def _normalise_dialogue_tags(text: str) -> str:
    """Title-case dialogue-tag names so spaCy sees mixed case."""
    def _title(m):
        return m.group(1).title() + ":" + m.group(2)
    return _dialogue_tag_re.sub(_title, text)


# --- Core: spaCy-based lemmatisation ---

def spacy_lemmatize(word: str) -> str:
    """Lemmatize a single word using spaCy."""
    nlp = get_nlp()
    doc = nlp(word.lower())
    return doc[0].lemma_.lower()


# --- Core: extract words from text ---

def extract_words(text: str) -> list[tuple[str, str]]:
    """Extract (lemma, form) pairs using spaCy NLP pipeline."""
    # Collect dialogue tag names BEFORE normalisation
    dialogue_names: set[str] = set()  # title-cased names from tags
    for m in _dialogue_tag_re.finditer(text):
        for w in m.group(1).split():
            dialogue_names.add(w.title())
    dialogue_names_lower = {n.lower() for n in dialogue_names}

    text = _normalise_dialogue_tags(text)
    nlp = get_nlp()
    doc = nlp(text)

    results: list[tuple[str, str]] = []
    for token in doc:
        if not token.is_alpha:
            continue
        text_lower = token.text.lower()
        if len(token.text) <= 1 and text_lower not in ('a', 'i'):
            continue
        if text_lower in STOP_WORDS:
            continue
        if _is_excluded(text_lower):
            continue

        # Case-sensitive words (I, Mr, English, Monday)
        if text_lower in CASE_SENSITIVE_LOWER:
            canonical = CASE_SENSITIVE_MAP[text_lower]
            results.append((canonical, canonical))
            continue

        # Dialogue-tag names -> always proper noun with title case
        if text_lower in dialogue_names_lower:
            title_name = text_lower.title()
            results.append((title_name, title_name))
            continue

        lemma = token.lemma_

        # PROPN with uppercase lemma -> possible proper noun
        if token.pos_ == "PROPN" and lemma[0].isupper():
            # If followed by possessive 's -> it's a common noun
            next_tok = token.nbor(1) if token.i + 1 < len(doc) else None
            if next_tok and next_tok.text == "'s":
                check = nlp(lemma.lower())[0]
                results.append((check.lemma_.lower(), lemma.lower()))
                continue
            lemma_lower = lemma.lower()
            # Check: is the lowercase form a common word?
            check = nlp(lemma_lower)[0]
            if check.pos_ != "PROPN" and check.lemma_.islower():
                results.append((check.lemma_, lemma_lower))
                continue
            # True proper noun
            if token.text.isupper() and len(token.text) > 1:
                lemma = token.text if len(token.text) <= 4 else token.text.title()
            results.append((lemma, lemma))
            continue

        # Common word
        results.append((lemma.lower(), token.text.lower()))

    return results



def get_or_create_book(name: str, publisher=None, grade=None, semester=None) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM books WHERE name = ?", (name,))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO books (name, publisher, grade, semester) VALUES (?, ?, ?, ?)",
                   (name, publisher, grade, semester))
        book_id = cur.lastrowid
        conn.commit()

    return book_id


def get_or_create_unit(book_id: int, unit_no: int, title=None) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM units WHERE book_id = ? AND unit_no = ?", (book_id, unit_no))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO units (book_id, unit_no, title) VALUES (?, ?, ?)",
                   (book_id, unit_no, title))
        unit_id = cur.lastrowid
        conn.commit()

    return unit_id


def get_or_create_lesson(unit_id: int, lesson_no: int, title=None) -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM lessons WHERE unit_id = ? AND lesson_no = ?", (unit_id, lesson_no))
        row = cur.fetchone()
        if row:
            return row["id"]
        cur.execute("INSERT INTO lessons (unit_id, lesson_no, title) VALUES (?, ?, ?)",
                   (unit_id, lesson_no, title))
        lesson_id = cur.lastrowid
        conn.commit()

    return lesson_id


def add_lesson_text(lesson_id: int, content: str, text_type: str = 'main') -> int:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM lesson_texts WHERE lesson_id = ? AND text_type = ?",
                   (lesson_id, text_type))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE lesson_texts SET content = ? WHERE id = ?", (content, row["id"]))
            text_id = row["id"]
        else:
            cur.execute("INSERT INTO lesson_texts (lesson_id, text_type, content) VALUES (?, ?, ?)",
                        (lesson_id, text_type, content))
            text_id = cur.lastrowid
        conn.commit()

    return text_id


def analyze_and_update_words(lesson_id: int, content: str) -> list[str]:
    word_pairs = extract_words(content)
    lemma_data = defaultdict(lambda: {"count": 0, "forms": Counter()})
    for lemma, form in word_pairs:
        lemma_data[lemma]["count"] += 1
        lemma_data[lemma]["forms"][form] += 1

    with get_db() as conn:
        cur = conn.cursor()
        new_words = []

        for lemma, data in lemma_data.items():
            total = data["count"]
            forms = data["forms"]

            cur.execute("SELECT id, first_lesson_id FROM words WHERE word = ? COLLATE NOCASE", (lemma,))
            row = cur.fetchone()
            if row:
                word_id = row["id"]
            else:
                cur.execute("INSERT INTO words (word, first_lesson_id) VALUES (?, ?)",
                            (lemma, lesson_id))
                word_id = cur.lastrowid
                new_words.append(lemma)

            for form, form_count in forms.items():
                cur.execute("""
                    INSERT INTO word_forms (word_id, form, count)
                    VALUES (?, ?, ?)
                    ON CONFLICT(word_id, form) DO UPDATE SET count = count + excluded.count
                """, (word_id, form, form_count))

            cur.execute("""
                INSERT INTO word_occurrences (word_id, lesson_id, count)
                VALUES (?, ?, ?)
                ON CONFLICT(word_id, lesson_id) DO UPDATE SET count = excluded.count
            """, (word_id, lesson_id, total))

        conn.commit()

    return sorted(new_words)


def lookup_word(word: str) -> dict | None:
    word = word.strip()
    lower_w = word.lower()
    lemma = spacy_lemmatize(lower_w)

    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id, first_lesson_id FROM words WHERE word = ? COLLATE NOCASE", (lemma,))
        row = cur.fetchone()
        if not row:
            cur.execute("SELECT id, first_lesson_id FROM words WHERE word = ? COLLATE NOCASE", (word,))
            row = cur.fetchone()
        if not row:
            return None

        word_id = row["id"]
        first_lesson_id = row["first_lesson_id"]

        cur.execute("SELECT form, count FROM word_forms WHERE word_id = ? ORDER BY count DESC", (word_id,))
        forms = [(r["form"], r["count"]) for r in cur.fetchall()]

        cur.execute("""
            SELECT wo.lesson_id, wo.count,
                   l.lesson_no, l.title AS lesson_title,
                   u.unit_no, u.title AS unit_title,
                   b.name AS book_name, b.grade, b.semester
            FROM word_occurrences wo
            JOIN lessons l ON l.id = wo.lesson_id
            JOIN units u ON u.id = l.unit_id
            JOIN books b ON b.id = u.book_id
            WHERE wo.word_id = ?
            ORDER BY b.id, u.unit_no, l.lesson_no
        """, (word_id,))
        occurrences = [dict(r) for r in cur.fetchall()]

        first_lesson = None
        if first_lesson_id:
            cur.execute("""
                SELECT l.id as lesson_id, l.lesson_no, l.title AS lesson_title,
                       u.unit_no, u.title AS unit_title,
                       b.name AS book_name, b.grade, b.semester
                FROM lessons l
                JOIN units u ON u.id = l.unit_id
                JOIN books b ON b.id = u.book_id
                WHERE l.id = ?
            """, (first_lesson_id,))
            fl_row = cur.fetchone()
            if fl_row:
                first_lesson = dict(fl_row)


    total_count = sum(o["count"] for o in occurrences)

    # Extract sentence-level contexts for each lesson
    all_forms_set = {lemma, lower_w}
    all_forms_set.update(f for f, _ in forms)
    form_pattern = re.compile(
        r'\b(' + '|'.join(re.escape(f) for f in all_forms_set) + r')\b',
        re.IGNORECASE
    )

    for occ in occurrences:
        with get_db() as conn2:
            c2 = conn2.cursor()
            c2.execute("SELECT content FROM lesson_texts WHERE lesson_id = ?", (occ["lesson_id"],))
            text_rows = c2.fetchall()

        full_text = ' '.join(r["content"] for r in text_rows)
        sentences = re.split(r'(?<=[.!?])\s+', full_text)
        # Find matched sentences and include ±1 neighbors for context
        matched_indices = [i for i, s in enumerate(sentences) if form_pattern.search(s)]
        context_indices = set()
        for idx in matched_indices[:3]:
            for offset in (-1, 0, 1):
                context_indices.add(max(0, min(idx + offset, len(sentences) - 1)))
        occ["contexts"] = [sentences[i] for i in sorted(context_indices)]

    return {
        "word": lemma,
        "first_lesson_id": first_lesson_id,
        "first_lesson": first_lesson,
        "total_lessons": len(occurrences),
        "total_count": total_count,
        "forms": forms,
        "lessons": occurrences,
    }


def get_lesson_new_words(lesson_id: int) -> list[str]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT word FROM words WHERE first_lesson_id = ? ORDER BY word", (lesson_id,))
        words = [row["word"] for row in cur.fetchall()]

    return words


def get_lesson_word_forms(lesson_id: int) -> dict[str, list[str]]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, word FROM words WHERE first_lesson_id = ? ORDER BY word", (lesson_id,))
        new_words = cur.fetchall()
        result = {}
        for row in new_words:
            cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY form", (row["id"],))
            forms = [r["form"] for r in cur.fetchall()]
            result[row["word"]] = forms

    return result


def get_all_new_words_for_lesson(lesson_id: int) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content FROM lesson_texts WHERE lesson_id = ?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            return {"new_words": [], "review_words": [], "all_words": []}

        text = row["content"]
        pairs = extract_words(text)
        all_lemmas = sorted(set(lemma for lemma, _ in pairs))

        new_words = []
        review_words = []
        for lemma in all_lemmas:
            cur.execute("SELECT first_lesson_id FROM words WHERE word = ?", (lemma,))
            word_row = cur.fetchone()
            if word_row and word_row["first_lesson_id"] == lesson_id:
                new_words.append(lemma)
            else:
                review_words.append(lemma)


    return {"new_words": new_words, "review_words": review_words, "all_words": all_lemmas}


def get_lesson_text(lesson_id: int) -> str | None:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT content FROM lesson_texts WHERE lesson_id = ? ORDER BY text_type", (lesson_id,))
        rows = cur.fetchall()

    if not rows:
        return None
    return "\n\n".join(r["content"] for r in rows)



def get_lesson_texts_by_type(lesson_id: int) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, text_type, content FROM lesson_texts WHERE lesson_id = ? ORDER BY text_type", (lesson_id,))
        rows = [dict(r) for r in cur.fetchall()]

    return rows


def update_lesson_text(lesson_id: int, content: str, text_type: str = "main") -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM lesson_texts WHERE lesson_id = ? AND text_type = ?",
                   (lesson_id, text_type))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE lesson_texts SET content = ? WHERE id = ?", (content, row["id"]))
        else:
            cur.execute("INSERT INTO lesson_texts (lesson_id, text_type, content) VALUES (?, ?, ?)",
                        (lesson_id, text_type, content))
        conn.commit()

    total = rebuild_word_index()
    return {"lesson_id": lesson_id, "text_type": text_type, "total_words": total}

def rebuild_word_index() -> int:
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT lt.lesson_id, lt.content
            FROM lesson_texts lt
            JOIN lessons l ON l.id = lt.lesson_id
            JOIN units u ON u.id = l.unit_id
            JOIN books b ON b.id = u.book_id
            ORDER BY b.id, u.unit_no, l.lesson_no, lt.text_type
        """)
        texts = cur.fetchall()

        cur.execute("DELETE FROM word_forms")
        cur.execute("DELETE FROM word_occurrences")
        cur.execute("DELETE FROM words")

        seen = {}

        # Phase 1: extract all word pairs from every lesson
        all_lesson_pairs: dict[int, list[tuple[str, str]]] = {}
        for row in texts:
            all_lesson_pairs[row["lesson_id"]] = extract_words(row["content"])

        # Phase 2: cross-lesson merge - unify casing for same word
        from collections import defaultdict as _dd
        from nltk.corpus import wordnet as _wn
        lemma_groups: dict[str, list[tuple[str, str, int]]] = _dd(list)
        for lid, pairs in all_lesson_pairs.items():
            for lemma, form in pairs:
                lemma_groups[lemma.lower()].append((lemma, form, lid))

        merge_map: dict[tuple[str, str, int], tuple[str, str]] = {}
        for lower, entries in lemma_groups.items():
            if lower in CASE_SENSITIVE_LOWER:
                continue
            lemmas_seen = {e[0] for e in entries}
            has_upper = any(l[0].isupper() for l in lemmas_seen)
            has_lower = any(l.islower() for l in lemmas_seen)
            if not (has_upper and has_lower):
                continue
            upper_lemma = next(l for l in lemmas_seen if l[0].isupper())
            # Use WordNet: if lowercase form is a real English word, demote to common word
            # If not in WordNet, it is likely a name -> keep uppercase
            if _wn.synsets(lower):
                # Real English word (book, orange, star, cd) -> demote to lowercase
                common_lemma = spacy_lemmatize(lower)
                for lemma, form, lid in entries:
                    merge_map[(lemma, form, lid)] = (common_lemma, lower)
            else:
                # Unknown word (suzy, meera) -> keep as proper noun
                for lemma, form, lid in entries:
                    merge_map[(lemma, form, lid)] = (upper_lemma, upper_lemma)

        for lid in list(all_lesson_pairs.keys()):
            all_lesson_pairs[lid] = [
                merge_map.get((l, f, lid), (l, f))
                for l, f in all_lesson_pairs[lid]
            ]

        # Phase 3: write to database
        for row in texts:
            lesson_id = row["lesson_id"]
            word_pairs = all_lesson_pairs[lesson_id]

            lemma_data = defaultdict(lambda: {"count": 0, "forms": Counter()})
            for lemma, form in word_pairs:
                lemma_data[lemma]["count"] += 1
                lemma_data[lemma]["forms"][form] += 1

            for lemma, data in lemma_data.items():
                if lemma not in seen:
                    seen[lemma] = lesson_id
                first_lesson_id = seen[lemma]

                cur.execute("SELECT id FROM words WHERE word = ?", (lemma,))
                wrow = cur.fetchone()
                if wrow:
                    word_id = wrow["id"]
                    cur.execute("UPDATE words SET first_lesson_id = ? WHERE id = ?",
                               (first_lesson_id, word_id))
                else:
                    cur.execute("INSERT INTO words (word, first_lesson_id) VALUES (?, ?)",
                               (lemma, first_lesson_id))
                    word_id = cur.lastrowid

                for form, form_count in data["forms"].items():
                    cur.execute("""
                        INSERT INTO word_forms (word_id, form, count)
                        VALUES (?, ?, ?)
                        ON CONFLICT(word_id, form) DO UPDATE SET count = count + excluded.count
                    """, (word_id, form, form_count))

                cur.execute("""
                    INSERT INTO word_occurrences (word_id, lesson_id, count)
                    VALUES (?, ?, ?)
                    ON CONFLICT(word_id, lesson_id) DO UPDATE SET count = count + excluded.count
                """, (word_id, lesson_id, data["count"]))
        conn.commit()
        total_words = len(seen)

    return total_words


def list_books() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM books ORDER BY id")
        books = [dict(r) for r in cur.fetchall()]

    return books


def list_units(book_id: int) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM units WHERE book_id = ? ORDER BY unit_no", (book_id,))
        units = [dict(r) for r in cur.fetchall()]

    return units


def list_lessons(unit_id: int) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lessons WHERE unit_id = ? ORDER BY lesson_no", (unit_id,))
        lessons = [dict(r) for r in cur.fetchall()]

    return lessons


def get_full_lesson_path(lesson_id: int) -> str:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT b.name AS book_name, u.unit_no, u.title AS unit_title,
                   l.lesson_no, l.title AS lesson_title
            FROM lessons l
            JOIN units u ON u.id = l.unit_id
            JOIN books b ON b.id = u.book_id
            WHERE l.id = ?
        """, (lesson_id,))
        row = cur.fetchone()

    if not row:
        return "Unknown lesson"
    parts = [row["book_name"]]
    if row["unit_title"]:
        parts.append(f"Unit {row['unit_no']} {row['unit_title']}")
    else:
        parts.append(f"Unit {row['unit_no']}")
    if row["lesson_title"]:
        parts.append(f"Lesson {row['lesson_no']} {row['lesson_title']}")
    else:
        parts.append(f"Lesson {row['lesson_no']}")
    return " > ".join(parts)


# --- Management functions ---

def _count_descendants_book(conn, book_id: int) -> dict:
    """Count units, lessons, and texts under a book for cascade info."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM units WHERE book_id = ?", (book_id,))
    unit_count = cur.fetchone()["cnt"]
    cur.execute("""
        SELECT COUNT(*) AS cnt FROM lessons l
        JOIN units u ON u.id = l.unit_id WHERE u.book_id = ?
    """, (book_id,))
    lesson_count = cur.fetchone()["cnt"]
    cur.execute("""
        SELECT COUNT(*) AS cnt FROM lesson_texts lt
        JOIN lessons l ON l.id = lt.lesson_id
        JOIN units u ON u.id = l.unit_id WHERE u.book_id = ?
    """, (book_id,))
    text_count = cur.fetchone()["cnt"]
    return {"units": unit_count, "lessons": lesson_count, "texts": text_count}


def _count_descendants_unit(conn, unit_id: int) -> dict:
    """Count lessons and texts under a unit for cascade info."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS cnt FROM lessons WHERE unit_id = ?", (unit_id,))
    lesson_count = cur.fetchone()["cnt"]
    cur.execute("""
        SELECT COUNT(*) AS cnt FROM lesson_texts lt
        JOIN lessons l ON l.id = lt.lesson_id WHERE l.unit_id = ?
    """, (unit_id,))
    text_count = cur.fetchone()["cnt"]
    return {"lessons": lesson_count, "texts": text_count}


def update_book(book_id: int, name: str = None, publisher: str | None = ..., grade: str | None = ..., semester: str | None = ...) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Book {book_id} not found")
        updates = {}
        if name is not None:
            updates["name"] = name
        if publisher is not ...:
            updates["publisher"] = publisher
        if grade is not ...:
            updates["grade"] = grade
        if semester is not ...:
            updates["semester"] = semester
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            cur.execute(f"UPDATE books SET {set_clause} WHERE id = ?", list(updates.values()) + [book_id])
        conn.commit()
        cur.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        result = dict(cur.fetchone())

    return result


def update_unit(unit_id: int, unit_no: int = None, title: str | None = ...) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unit {unit_id} not found")
        updates = {}
        if unit_no is not None:
            updates["unit_no"] = unit_no
        if title is not ...:
            updates["title"] = title
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            cur.execute(f"UPDATE units SET {set_clause} WHERE id = ?", list(updates.values()) + [unit_id])
        conn.commit()
        cur.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
        result = dict(cur.fetchone())

    return result


def update_lesson(lesson_id: int, lesson_no: int = None, title: str | None = ...) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Lesson {lesson_id} not found")
        updates = {}
        if lesson_no is not None:
            updates["lesson_no"] = lesson_no
        if title is not ...:
            updates["title"] = title
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            cur.execute(f"UPDATE lessons SET {set_clause} WHERE id = ?", list(updates.values()) + [lesson_id])
        conn.commit()
        cur.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
        result = dict(cur.fetchone())

    return result


def delete_lesson(lesson_id: int) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT l.id, l.title, l.lesson_no FROM lessons l WHERE l.id = ?", (lesson_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Lesson {lesson_id} not found")
        # Null out first_lesson_id references before deleting (no ON DELETE SET NULL)
        cur.execute("UPDATE words SET first_lesson_id = NULL WHERE first_lesson_id = ?", (lesson_id,))
        # Delete word occurrences for this lesson first
        cur.execute("""
            DELETE FROM word_occurrences WHERE lesson_id = ?
        """, (lesson_id,))
        # ON DELETE CASCADE handles lesson_texts
        cur.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
        # Clean up orphan words (no occurrences left)
        cur.execute("""
            DELETE FROM word_forms WHERE word_id IN (
                SELECT w.id FROM words w
                LEFT JOIN word_occurrences wo ON wo.word_id = w.id
                WHERE wo.id IS NULL
            )
        """)
        cur.execute("""
            DELETE FROM words WHERE id IN (
                SELECT w.id FROM words w
                LEFT JOIN word_occurrences wo ON wo.word_id = w.id
                WHERE wo.id IS NULL
            )
        """)
        conn.commit()

    return {"deleted": "lesson", "id": lesson_id, "title": row["title"], "lesson_no": row["lesson_no"]}


def delete_unit(unit_id: int) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Unit {unit_id} not found")
        info = _count_descendants_unit(conn, unit_id)
        # Get all lesson ids under this unit
        cur.execute("SELECT id FROM lessons WHERE unit_id = ?", (unit_id,))
        lesson_ids = [r["id"] for r in cur.fetchall()]
        # Null out first_lesson_id references before deleting
        if lesson_ids:
            placeholders = sql_placeholders(len(lesson_ids))
            cur.execute(f"UPDATE words SET first_lesson_id = NULL WHERE first_lesson_id IN ({placeholders})", lesson_ids)
        # Delete word occurrences for all lessons in this unit
        if lesson_ids:
            placeholders = sql_placeholders(len(lesson_ids))
            cur.execute(f"DELETE FROM word_occurrences WHERE lesson_id IN ({placeholders})", lesson_ids)
        # ON DELETE CASCADE handles lesson_texts and lessons
        cur.execute("DELETE FROM units WHERE id = ?", (unit_id,))
        # Clean up orphan words
        cur.execute("""
            DELETE FROM word_forms WHERE word_id IN (
                SELECT w.id FROM words w
                LEFT JOIN word_occurrences wo ON wo.word_id = w.id
                WHERE wo.id IS NULL
            )
        """)
        cur.execute("""
            DELETE FROM words WHERE id IN (
                SELECT w.id FROM words w
                LEFT JOIN word_occurrences wo ON wo.word_id = w.id
                WHERE wo.id IS NULL
            )
        """)
        conn.commit()

    return {"deleted": "unit", "id": unit_id, "title": row["title"], "unit_no": row["unit_no"], **info}


def delete_book(book_id: int) -> dict:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM books WHERE id = ?", (book_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Book {book_id} not found")
        info = _count_descendants_book(conn, book_id)
        # Get all lesson ids under this book
        cur.execute("""
            SELECT l.id FROM lessons l
            JOIN units u ON u.id = l.unit_id WHERE u.book_id = ?
        """, (book_id,))
        lesson_ids = [r["id"] for r in cur.fetchall()]
        # Null out first_lesson_id references before deleting
        if lesson_ids:
            placeholders = sql_placeholders(len(lesson_ids))
            cur.execute(f"UPDATE words SET first_lesson_id = NULL WHERE first_lesson_id IN ({placeholders})", lesson_ids)
        # Delete word occurrences for all lessons in this book
        if lesson_ids:
            placeholders = sql_placeholders(len(lesson_ids))
            cur.execute(f"DELETE FROM word_occurrences WHERE lesson_id IN ({placeholders})", lesson_ids)
        # ON DELETE CASCADE handles the rest
        cur.execute("DELETE FROM books WHERE id = ?", (book_id,))
        # Clean up orphan words
        cur.execute("""
            DELETE FROM word_forms WHERE word_id IN (
                SELECT w.id FROM words w
                LEFT JOIN word_occurrences wo ON wo.word_id = w.id
                WHERE wo.id IS NULL
            )
        """)
        cur.execute("""
            DELETE FROM words WHERE id IN (
                SELECT w.id FROM words w
                LEFT JOIN word_occurrences wo ON wo.word_id = w.id
                WHERE wo.id IS NULL
            )
        """)
        conn.commit()

    return {"deleted": "book", "id": book_id, "name": row["name"], **info}


def reorder_units(book_id: int, unit_ids: list[int]) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM units WHERE book_id = ?", (book_id,))
        existing = {r["id"] for r in cur.fetchall()}
        if set(unit_ids) != existing:
            raise ValueError("unit_ids do not match existing units for this book")
        for new_no, uid in enumerate(unit_ids, 1):
            cur.execute("UPDATE units SET unit_no = ? WHERE id = ?", (new_no, uid))
        conn.commit()
        cur.execute("SELECT * FROM units WHERE book_id = ? ORDER BY unit_no", (book_id,))
        result = [dict(r) for r in cur.fetchall()]

    return result


def reorder_lessons(unit_id: int, lesson_ids: list[int]) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM lessons WHERE unit_id = ?", (unit_id,))
        existing = {r["id"] for r in cur.fetchall()}
        if set(lesson_ids) != existing:
            raise ValueError("lesson_ids do not match existing lessons for this unit")
        for new_no, lid in enumerate(lesson_ids, 1):
            cur.execute("UPDATE lessons SET lesson_no = ? WHERE id = ?", (new_no, lid))
        conn.commit()
        cur.execute("SELECT * FROM lessons WHERE unit_id = ? ORDER BY lesson_no", (unit_id,))
        result = [dict(r) for r in cur.fetchall()]

    return result


# --- Vocab & Quiz functions ---

def get_all_vocab(q: str | None = None, sort: str = "alpha") -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()

        sql = """
            SELECT w.id, w.word, w.first_lesson_id, w.created_at,
                   COALESCE(SUM(wo.count), 0) AS total_count
            FROM words w
            LEFT JOIN word_occurrences wo ON wo.word_id = w.id
        """
        params = []
        if q:
            sql += " WHERE w.word LIKE ?"
            params.append(f"%{q}%")
        sql += " GROUP BY w.id"
        if sort == "time":
            sql += " ORDER BY w.created_at DESC"
        else:
            sql += " ORDER BY w.word"

        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

        for row in rows:
            # Get word forms
            cur.execute("SELECT form, count FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
            row["forms"] = [dict(r) for r in cur.fetchall()]
            # Get first lesson path
            if row["first_lesson_id"]:
                row["first_lesson_path"] = get_full_lesson_path(row["first_lesson_id"])
            else:
                row["first_lesson_path"] = None

            # Extract first context sentence from first lesson
            row["context"] = None
            if row["first_lesson_id"]:
                cur.execute("SELECT content FROM lesson_texts WHERE lesson_id = ?", (row["first_lesson_id"],))
                text_rows = cur.fetchall()
                full_text = " ".join(r["content"] for r in text_rows)
                forms_set = {row["word"]}
                forms_set.update(f["form"] for f in row["forms"])
                form_pattern = re.compile(
                    r"\b(" + "|".join(re.escape(f) for f in forms_set) + r")\b",
                    re.IGNORECASE
                )
                sentences = re.split(r"(?<=[.!?])\s+", full_text)
                for s in sentences:
                    if form_pattern.search(s):
                        row["context"] = s
                        break


    return rows


def get_random_quiz_words(count: int = 10) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT w.id, w.word, w.first_lesson_id,
                   COALESCE(SUM(wo.count), 0) AS total_count
            FROM words w
            LEFT JOIN word_occurrences wo ON wo.word_id = w.id
            GROUP BY w.id
            ORDER BY RANDOM()
            LIMIT ?
        """, (count,))
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
            row["forms"] = [r["form"] for r in cur.fetchall()]
            if row["first_lesson_id"]:
                row["first_lesson_path"] = get_full_lesson_path(row["first_lesson_id"])
            else:
                row["first_lesson_path"] = None

    return rows


def get_lesson_quiz_words(lesson_id: int) -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT w.id, w.word, w.first_lesson_id,
                   COALESCE(SUM(wo.count), 0) AS total_count
            FROM words w
            JOIN word_occurrences wo ON wo.word_id = w.id
            WHERE wo.lesson_id = ?
            GROUP BY w.id
            ORDER BY w.word
        """, (lesson_id,))
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
            row["forms"] = [r["form"] for r in cur.fetchall()]
            if row["first_lesson_id"]:
                row["first_lesson_path"] = get_full_lesson_path(row["first_lesson_id"])
            else:
                row["first_lesson_path"] = None

    return rows



def get_lesson_quiz_words_by_ids(lesson_ids: list[int]) -> list[dict]:
    """Get quiz words for a list of lesson IDs."""
    if not lesson_ids:
        return []
    with get_db() as conn:
        cur = conn.cursor()
        ph = sql_placeholders(len(lesson_ids))
        cur.execute(f"""
            SELECT w.id, w.word, w.first_lesson_id,
                   COALESCE(SUM(wo.count), 0) AS total_count
            FROM words w
            JOIN word_occurrences wo ON wo.word_id = w.id
            WHERE wo.lesson_id IN ({ph})
            GROUP BY w.id
            ORDER BY w.word
        """, lesson_ids)
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
            row["forms"] = [r["form"] for r in cur.fetchall()]
            if row["first_lesson_id"]:
                row["first_lesson_path"] = get_full_lesson_path(row["first_lesson_id"])
            else:
                row["first_lesson_path"] = None

    return rows

def get_mistake_words() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        # Find word_ids whose latest quiz result is unknown
        cur.execute("SELECT word_id, MAX(id) as max_id FROM word_quiz_log GROUP BY word_id")
        latest_ids = {r["word_id"]: r["max_id"] for r in cur.fetchall()}
        mistake_word_ids = []
        for wid, mid in latest_ids.items():
            cur.execute("SELECT result FROM word_quiz_log WHERE id = ?", (mid,))
            row = cur.fetchone()
            if row and row["result"] == "unknown":
                mistake_word_ids.append(wid)

        if not mistake_word_ids:
            return []

        placeholders = sql_placeholders(len(mistake_word_ids))
        cur.execute(
            "SELECT w.id, w.word, w.first_lesson_id, COALESCE(SUM(wo.count), 0) AS total_count "
            "FROM words w LEFT JOIN word_occurrences wo ON wo.word_id = w.id "
            "WHERE w.id IN (" + placeholders + ") "
            "GROUP BY w.id ORDER BY w.word",
            mistake_word_ids
        )
        rows = [dict(r) for r in cur.fetchall()]
        for row in rows:
            cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
            row["forms"] = [r["form"] for r in cur.fetchall()]
            if row["first_lesson_id"]:
                row["first_lesson_path"] = get_full_lesson_path(row["first_lesson_id"])
            else:
                row["first_lesson_path"] = None

    return rows


def record_quiz_result(word_id: int, result: str, quiz_type: str = "random", lesson_id: int | None = None):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO word_quiz_log (word_id, result, quiz_type, lesson_id)
            VALUES (?, ?, ?, ?)
        """, (word_id, result, quiz_type, lesson_id))
        conn.commit()

    return {"word_id": word_id, "result": result}


def clear_mistake(word_id: int):
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO word_quiz_log (word_id, result, quiz_type)
            VALUES (?, 'known', 'manual')
        """, (word_id,))
        conn.commit()

    return {"word_id": word_id, "result": "cleared"}



def get_excluded_list() -> list[dict]:
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id, word, created_at FROM excluded_words ORDER BY word")
        rows = [dict(r) for r in cur.fetchall()]

    return rows


def add_excluded_word(word: str) -> dict:
    word = word.strip().lower()
    if not word:
        raise ValueError("Word cannot be empty")
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("INSERT OR IGNORE INTO excluded_words (word) VALUES (?)", (word,))
        conn.commit()
        cur.execute("SELECT id FROM excluded_words WHERE word = ?", (word,))
        row = cur.fetchone()
        excluded_id = row["id"]

    refresh_excluded_cache()
    return {"id": excluded_id, "word": word}


def remove_excluded_word(word: str) -> dict:
    word = word.strip().lower()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM excluded_words WHERE word = ?", (word,))
        conn.commit()

    refresh_excluded_cache()
    return {"word": word, "removed": True}


def exclude_word_from_vocab(word_id: int) -> dict:
    """Exclude a word from vocab by word_id: add to excluded_words and remove from words tables."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT word FROM words WHERE id = ?", (word_id,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"Word id {word_id} not found")
        word = row["word"]
        # Add to excluded list
        cur.execute("INSERT OR IGNORE INTO excluded_words (word) VALUES (?)", (word.lower(),))
        # Remove from words, word_forms, word_occurrences (CASCADE handles it)
        cur.execute("DELETE FROM words WHERE id = ?", (word_id,))
        conn.commit()

    refresh_excluded_cache()
    return {"word": word, "excluded": True}


def unexclude_word(word: str) -> dict:
    """Remove a word from the excluded list so it can be picked up again."""
    word = word.strip().lower()
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM excluded_words WHERE word = ? COLLATE NOCASE", (word,))
        conn.commit()

    refresh_excluded_cache()
    return {"word": word, "unexcluded": True}


def get_units_word_stats(book_id: int) -> dict[int, dict]:
    """Get word statistics for all units in a book."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("""
            SELECT u.id as unit_id, l.id as lesson_id
            FROM units u
            LEFT JOIN lessons l ON l.unit_id = u.id
            WHERE u.book_id = ?
            ORDER BY u.unit_no, l.lesson_no
        """, (book_id,))

        unit_lessons: dict[int, list[int]] = {}
        for row in cur.fetchall():
            uid = row["unit_id"]
            if uid not in unit_lessons:
                unit_lessons[uid] = []
            if row["lesson_id"]:
                unit_lessons[uid].append(row["lesson_id"])

        if not unit_lessons:
            return {}

        all_lesson_ids = []
        for lids in unit_lessons.values():
            all_lesson_ids.extend(lids)

        if not all_lesson_ids:
            return {uid: {"new_count": 0, "review_count": 0, "lesson_count": len(lids)} for uid, lids in unit_lessons.items()}

        lesson_ph = sql_placeholders(len(all_lesson_ids))
        cur.execute(
            f"SELECT first_lesson_id, COUNT(*) as cnt FROM words WHERE first_lesson_id IN ({lesson_ph}) GROUP BY first_lesson_id",
            all_lesson_ids
        )
        lesson_new_counts = {row["first_lesson_id"]: row["cnt"] for row in cur.fetchall()}

        result = {}
        for uid, lids in unit_lessons.items():
            new_count = sum(lesson_new_counts.get(lid, 0) for lid in lids)
            review_count = 0
            if lids:
                ph = sql_placeholders(len(lids))
                cur.execute(f"""
                    SELECT COUNT(DISTINCT w.id) as cnt
                    FROM word_occurrences wo
                    JOIN words w ON w.id = wo.word_id
                    WHERE wo.lesson_id IN ({ph})
                    AND w.first_lesson_id NOT IN ({ph})
                """, lids + lids)
                review_count = cur.fetchone()["cnt"]
            result[uid] = {"new_count": new_count, "review_count": review_count, "lesson_count": len(lids)}


    return result


def get_book_word_stats(book_id: int) -> dict:
    """Get aggregated word statistics for a book."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) as cnt FROM units WHERE book_id = ?", (book_id,))
        total_units = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM lessons l
            JOIN units u ON l.unit_id = u.id
            WHERE u.book_id = ?
        """, (book_id,))
        total_lessons = cur.fetchone()["cnt"]

        cur.execute("""
            SELECT COUNT(*) as cnt FROM words w
            JOIN lessons l ON w.first_lesson_id = l.id
            JOIN units u ON l.unit_id = u.id
            WHERE u.book_id = ?
        """, (book_id,))
        new_count = cur.fetchone()["cnt"]


    return {
        "total_units": total_units,
        "total_lessons": total_lessons,
        "new_count": new_count,
    }


def get_unit_word_detail(unit_id: int) -> dict:
    """Get detailed word list for a unit."""
    with get_db() as conn:
        cur = conn.cursor()

        cur.execute("SELECT id FROM lessons WHERE unit_id = ? ORDER BY lesson_no", (unit_id,))
        lesson_ids = [row["id"] for row in cur.fetchall()]

        if not lesson_ids:
            return {"new_words": [], "review_words": [], "new_count": 0, "review_count": 0, "lessons": []}

        ph = sql_placeholders(len(lesson_ids))

        cur.execute(f"SELECT id, word FROM words WHERE first_lesson_id IN ({ph}) ORDER BY word", lesson_ids)
        new_word_rows = cur.fetchall()
        new_words = []
        for row in new_word_rows:
            cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
            forms = [r["form"] for r in cur.fetchall()]
            new_words.append({"word": row["word"], "forms": forms})

        cur.execute(f"""
            SELECT DISTINCT w.word
            FROM word_occurrences wo
            JOIN words w ON w.id = wo.word_id
            WHERE wo.lesson_id IN ({ph})
            AND w.first_lesson_id NOT IN ({ph})
            ORDER BY w.word
        """, lesson_ids + lesson_ids)
        review_words = [row["word"] for row in cur.fetchall()]

        lessons = []
        for lid in lesson_ids:
            lesson_data = get_all_new_words_for_lesson(lid)
            cur.execute("SELECT lesson_no, title FROM lessons WHERE id = ?", (lid,))
            lrow = cur.fetchone()
            lessons.append({
                "lesson_id": lid,
                "lesson_no": lrow["lesson_no"],
                "title": lrow["title"],
                "new_words": lesson_data["new_words"],
                "review_words": lesson_data["review_words"],
            })


    return {
        "new_words": new_words,
        "review_words": review_words,
        "new_count": len(new_words),
        "review_count": len(review_words),
        "lessons": lessons,
    }


# --- Export / Import ---

def _export_book(conn, book_id: int) -> dict:
    """Export a single book with its full hierarchy."""
    cur = conn.cursor()
    cur.execute("SELECT name, publisher, grade, semester FROM books WHERE id = ?", (book_id,))
    row = cur.fetchone()
    book = {
        "name": row["name"],
        "publisher": row["publisher"],
        "grade": row["grade"],
        "semester": row["semester"],
    }

    cur.execute("SELECT id, unit_no, title FROM units WHERE book_id = ? ORDER BY unit_no", (book_id,))
    units = []
    for u in cur.fetchall():
        unit = {"unit_no": u["unit_no"], "title": u["title"], "lessons": []}
        cur.execute("SELECT id, lesson_no, title FROM lessons WHERE unit_id = ? ORDER BY lesson_no", (u["id"],))
        for l in cur.fetchall():
            lesson = {"lesson_no": l["lesson_no"], "title": l["title"], "texts": []}
            cur.execute("SELECT text_type, content FROM lesson_texts WHERE lesson_id = ? ORDER BY text_type", (l["id"],))
            for t in cur.fetchall():
                lesson["texts"].append({"text_type": t["text_type"], "content": t["content"]})
            unit["lessons"].append(lesson)
        units.append(unit)
    book["units"] = units
    return book


def _export_excluded_words(conn) -> list[str]:
    cur = conn.cursor()
    cur.execute("SELECT word FROM excluded_words ORDER BY word")
    return [r["word"] for r in cur.fetchall()]


def export_textbook(book_id: int) -> dict:
    """Export a single textbook as a portable dict."""
    with get_db() as conn:
        book = _export_book(conn, book_id)
        excluded = _export_excluded_words(conn)
    return {
        "version": 1,
        "type": "textbook",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "excluded_words": excluded,
        "books": [book],
    }


def export_all_textbooks() -> dict:
    """Export all textbooks as a portable dict."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM books ORDER BY id")
        book_ids = [r["id"] for r in cur.fetchall()]
        books = [_export_book(conn, bid) for bid in book_ids]
        excluded = _export_excluded_words(conn)
    return {
        "version": 1,
        "type": "textbook",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "excluded_words": excluded,
        "books": books,
    }


def export_quiz_data() -> dict:
    """Export all quiz log data as a portable dict."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT w.word, q.result, q.quiz_type, q.lesson_id, q.created_at
            FROM word_quiz_log q
            JOIN words w ON w.id = q.word_id
            ORDER BY q.created_at
        """)
        rows = cur.fetchall()
        logs = []
        for r in rows:
            entry = {
                "word": r["word"],
                "result": r["result"],
                "quiz_type": r["quiz_type"],
                "created_at": r["created_at"],
            }
            if r["lesson_id"]:
                cur.execute("""
                    SELECT b.name, u.unit_no, l.lesson_no
                    FROM lessons l
                    JOIN units u ON l.unit_id = u.id
                    JOIN books b ON u.book_id = b.id
                    WHERE l.id = ?
                """, (r["lesson_id"],))
                path = cur.fetchone()
                if path:
                    entry["book_name"] = path["name"]
                    entry["unit_no"] = path["unit_no"]
                    entry["lesson_no"] = path["lesson_no"]
            logs.append(entry)
    return {
        "version": 1,
        "type": "quiz",
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "logs": logs,
    }


def import_textbooks(data: dict, clear: bool = False) -> dict:
    """Import textbook data. Returns summary stats."""
    books_imported = 0
    books_skipped = 0
    lessons_created = 0
    words_imported = 0
    excluded_added = 0

    with get_db() as conn:
        cur = conn.cursor()

        if clear:
            cur.execute("DELETE FROM books")
            cur.execute("DELETE FROM excluded_words")
            conn.commit()
            refresh_excluded_cache()

        for book_data in data.get("books", []):
            cur.execute("SELECT id FROM books WHERE name = ?", (book_data["name"],))
            existing = cur.fetchone()
            if existing:
                books_skipped += 1
                continue

            book_id = get_or_create_book(
                book_data["name"],
                book_data.get("publisher"),
                book_data.get("grade"),
                book_data.get("semester"),
            )
            books_imported += 1

            for unit_data in book_data.get("units", []):
                unit_id = get_or_create_unit(book_id, unit_data["unit_no"], unit_data.get("title"))

                for lesson_data in unit_data.get("lessons", []):
                    lesson_id = get_or_create_lesson(unit_id, lesson_data["lesson_no"], lesson_data.get("title"))
                    lessons_created += 1

                    for text_data in lesson_data.get("texts", []):
                        add_lesson_text(lesson_id, text_data["content"], text_data.get("text_type", "main"))
                        new_words = analyze_and_update_words(lesson_id, text_data["content"])
                        words_imported += len(new_words)

        # Import excluded words
        for word in data.get("excluded_words", []):
            cur.execute("SELECT 1 FROM excluded_words WHERE word = ?", (word,))
            if not cur.fetchone():
                cur.execute("INSERT OR IGNORE INTO excluded_words (word) VALUES (?)", (word,))
                excluded_added += 1
        conn.commit()
    refresh_excluded_cache()

    return {
        "books_imported": books_imported,
        "books_skipped": books_skipped,
        "lessons_created": lessons_created,
        "words_imported": words_imported,
        "excluded_added": excluded_added,
    }


def import_quiz_data(data: dict, clear: bool = False) -> dict:
    """Import quiz log data. Returns summary stats."""
    imported = 0
    skipped = 0

    with get_db() as conn:
        cur = conn.cursor()

        if clear:
            cur.execute("DELETE FROM word_quiz_log")
            conn.commit()

        for entry in data.get("logs", []):
            cur.execute("SELECT id FROM words WHERE word = ? COLLATE NOCASE", (entry["word"],))
            word_row = cur.fetchone()
            if not word_row:
                skipped += 1
                continue
            word_id = word_row["id"]

            lesson_id = None
            if entry.get("book_name") and entry.get("unit_no") is not None and entry.get("lesson_no") is not None:
                cur.execute("""
                    SELECT l.id
                    FROM lessons l
                    JOIN units u ON l.unit_id = u.id
                    JOIN books b ON u.book_id = b.id
                    WHERE b.name = ? AND u.unit_no = ? AND l.lesson_no = ?
                """, (entry["book_name"], entry["unit_no"], entry["lesson_no"]))
                path_row = cur.fetchone()
                if path_row:
                    lesson_id = path_row["id"]

            cur.execute("""
                INSERT INTO word_quiz_log (word_id, result, quiz_type, lesson_id, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (word_id, entry["result"], entry.get("quiz_type", "random"), lesson_id, entry.get("created_at")))
            imported += 1

        conn.commit()

    return {
        "imported": imported,
        "skipped": skipped,
    }
