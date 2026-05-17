import re
from collections import Counter, defaultdict
from app.db import get_connection, STOP_WORDS


# Common irregular word forms mapping (form -> lemma)
IRREGULAR_FORMS = {
    # be
    "am": "be", "is": "be", "are": "be", "was": "be", "were": "be",
    "been": "be", "being": "be",
    # have
    "has": "have", "had": "have", "having": "have",
    # do
    "does": "do", "did": "do", "doing": "do", "done": "do",
    # go
    "goes": "go", "went": "go", "gone": "go", "going": "go",
    # come
    "came": "come", "coming": "come",
    # see
    "saw": "see", "seen": "see", "seeing": "see", "sees": "see",
    # take
    "took": "take", "taken": "take", "takes": "take", "taking": "take",
    # make
    "made": "make", "makes": "make", "making": "make",
    # give
    "gave": "give", "given": "give", "gives": "give", "giving": "give",
    # get
    "got": "get", "gotten": "get", "gets": "get", "getting": "get",
    # say
    "said": "say", "says": "say", "saying": "say",
    # tell
    "told": "tell", "tells": "tell", "telling": "tell",
    # know
    "knew": "know", "known": "know", "knows": "know", "knowing": "know",
    # think
    "thought": "think", "thinks": "think", "thinking": "think",
    # feel
    "felt": "feel", "feels": "feel", "feeling": "feel",
    # find
    "found": "find", "finds": "find", "finding": "find",
    # leave
    "left": "leave", "leaves": "leave", "leaving": "leave",
    # stand
    "stood": "stand", "stands": "stand", "standing": "stand",
    # keep
    "kept": "keep", "keeps": "keep", "keeping": "keep",
    # let
    "lets": "let", "letting": "let",
    # begin
    "began": "begin", "begun": "begin", "begins": "begin", "beginning": "begin",
    # write
    "wrote": "write", "written": "write", "writes": "write", "writing": "write",
    # read
    "reads": "read", "reading": "read",
    # speak
    "spoke": "speak", "spoken": "speak", "speaks": "speak", "speaking": "speak",
    # eat
    "ate": "eat", "eaten": "eat", "eats": "eat", "eating": "eat",
    # drink
    "drank": "drink", "drunk": "drink", "drinks": "drink", "drinking": "drink",
    # run
    "ran": "run", "runs": "run", "running": "run",
    # swim
    "swam": "swim", "swum": "swim", "swims": "swim", "swimming": "swim",
    # sing
    "sang": "sing", "sung": "sing", "sings": "sing", "singing": "sing",
    # bring
    "brought": "bring", "brings": "bring", "bringing": "bring",
    # buy
    "bought": "buy", "buys": "buy", "buying": "buy",
    # catch
    "caught": "catch", "catches": "catch", "catching": "catch",
    # teach
    "taught": "teach", "teaches": "teach", "teaching": "teach",
    # learn
    "learnt": "learn", "learned": "learn", "learns": "learn", "learning": "learn",
    # fly
    "flew": "fly", "flown": "fly", "flies": "fly", "flying": "fly",
    # draw
    "drew": "draw", "drawn": "draw", "draws": "draw", "drawing": "draw",
    # grow
    "grew": "grow", "grown": "grow", "grows": "grow", "growing": "grow",
    # drive
    "drove": "drive", "driven": "drive", "drives": "drive", "driving": "drive",
    # ride
    "rode": "ride", "ridden": "ride", "rides": "ride", "riding": "ride",
    # ring
    "rang": "ring", "rung": "ring", "rings": "ring", "ringing": "ring",
    # wear
    "wore": "wear", "worn": "wear", "wears": "wear", "wearing": "wear",
    # break
    "broke": "break", "broken": "break", "breaks": "break", "breaking": "break",
    # choose
    "chose": "choose", "chosen": "choose", "chooses": "choose", "choosing": "choose",
    # forget
    "forgot": "forget", "forgotten": "forget", "forgets": "forget", "forgetting": "forget",
    # sleep
    "slept": "sleep", "sleeps": "sleep", "sleeping": "sleep",
    # sweep
    "swept": "sweep", "sweeps": "sweep", "sweeping": "sweep",
    # meet
    "met": "meet", "meets": "meet", "meeting": "meet",
    # sit
    "sat": "sit", "sits": "sit", "sitting": "sit",
    # put
    "puts": "put", "putting": "put",
    # cut
    "cuts": "cut", "cutting": "cut",
    # hit
    "hits": "hit", "hitting": "hit",
    # shut
    "shuts": "shut", "shutting": "shut",
    # hurt
    "hurts": "hurt", "hurting": "hurt",
    # cost
    "costs": "cost", "costing": "cost",
    # spread
    "spreads": "spread", "spreading": "spread",
    # build
    "built": "build", "builds": "build", "building": "build",
    # send
    "sent": "send", "sends": "send", "sending": "send",
    # spend
    "spent": "spend", "spends": "spend", "spending": "spend",
    # lend
    "lent": "lend", "lends": "lend", "lending": "lend",
    # win
    "won": "win", "wins": "win", "winning": "win",
    # lose
    "lost": "lose", "loses": "lose", "losing": "lose",
    # pay
    "paid": "pay", "pays": "pay", "paying": "pay",
    # lay
    "laid": "lay", "lays": "lay", "laying": "lay",
    # lie (as in lie down)
    "lay": "lie", "lies": "lie", "lying": "lie",
    # die
    "died": "die", "dies": "die", "dying": "die",
    # hang
    "hung": "hang", "hangs": "hang", "hanging": "hang",
    # hold
    "held": "hold", "holds": "hold", "holding": "hold",
    # hear
    "heard": "hear", "hears": "hear", "hearing": "hear",
    # mean
    "meant": "mean", "means": "mean", "meaning": "mean",
    # show
    "showed": "show", "shown": "show", "shows": "show", "showing": "show",
    # sell
    "sold": "sell", "sells": "sell", "selling": "sell",
    # understand
    "understood": "understand", "understands": "understand", "understanding": "understand",
    # Irregular nouns
    "children": "child", "men": "man", "women": "woman",
    "people": "person", "feet": "foot", "teeth": "tooth",
    "mice": "mouse", "geese": "goose", "oxen": "ox",
    "lice": "louse", "phenomena": "phenomenon", "criteria": "criterion",
    # Irregular adjectives
    "better": "good", "best": "good",
    "worse": "bad", "worst": "bad",
    "less": "little", "least": "little",
    "more": "much", "most": "much",
    "further": "far", "farthest": "far", "furthest": "far",
    "leaves": "leaf",
    "knives": "knife",
    "lives": "life",
    "wives": "wife",
    "halves": "half",
    "selves": "self",
    "shelves": "shelf",
    "wolves": "wolf",
    "calves": "calf",
    "thieves": "thief",
    "loaves": "loaf",
}


def lemmatize_word(word: str) -> str:
    """
    Rule-based lemmatization for English words.
    Handles irregular forms via dictionary lookup,
    then applies suffix rules for regular forms.
    """
    lower = word.lower()

    if lower in IRREGULAR_FORMS:
        return IRREGULAR_FORMS[lower]

    # -ied past tense: studied -> study, tried -> try
    if lower.endswith("ied") and len(lower) > 3:
        return lower[:-3] + "y"

    # -ying progressive: lying -> lie, playing -> play
    if lower.endswith("ying") and len(lower) > 4:
        stem = lower[:-4]
        if stem.endswith("l"):
            return stem + "ie"
        return stem + "y"

    # -ing progressive
    if lower.endswith("ing") and len(lower) > 4:
        stem = lower[:-3]
        # running -> run (double consonant)
        if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] in "bdfglmnprst":
            return stem[:-1]
        # silent e: making -> make, writing -> write
        if len(stem) >= 2 and stem[-1] in "ktvcg":
            return stem + "e"
        return stem

    # -es verb/noun: watches -> watch, boxes -> box, stories -> story
    if lower.endswith("es") and len(lower) > 3:
        if lower.endswith("ies") and len(lower) > 4:
            return lower[:-3] + "y"
        stem = lower[:-2]
        if lower.endswith("ves") and len(lower) > 4:
            return lower[:-3] + "f"
        if lower[-3] in "sxz":
            return stem
        if len(lower) > 4 and lower[-4:-2] in ("ch", "sh"):
            return stem
        return lower[:-1]


    # -ed past tense
    if lower.endswith("ed") and len(lower) > 3:
        stem = lower[:-2]
        # stopped -> stop (double consonant)
        if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] in "bdfglmnprst":
            return stem[:-1]
        # silent e: liked -> like, created -> create
        if len(stem) >= 2 and stem[-1] in "kvcg":
            return stem + "e"
        return stem

    # -er comparative
    if lower.endswith("er") and len(lower) > 3:
        stem = lower[:-2]
        if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] in "bdfglmnprst":
            return stem[:-1]
        return stem

    # -est superlative
    if lower.endswith("est") and len(lower) > 4:
        stem = lower[:-3]
        if len(stem) >= 2 and stem[-1] == stem[-2] and stem[-1] in "bdfglmnprst":
            return stem[:-1]
        return stem

    # -s plural/verb
    if lower.endswith("s") and len(lower) > 2 and not lower.endswith("ss"):
        if lower.endswith("ies") and len(lower) > 4:
            return lower[:-3] + "y"
        if lower.endswith("ves") and len(lower) > 4:
            return lower[:-3] + "f"
        if lower.endswith(("ses", "shes", "ches", "xes", "zes")):
            return lower[:-2]
        return lower[:-1]

    return lower


def extract_words(text: str) -> list[tuple[str, str]]:
    raw_words = re.findall(r"[a-zA-Z']+", text.lower())
    results = []
    for w in raw_words:
        if len(w) <= 1 and w not in ('a', 'i'):
            continue
        if w in STOP_WORDS:
            continue
        lemma = lemmatize_word(w)
        if lemma in STOP_WORDS:
            continue
        results.append((lemma, w))
    return results


def get_or_create_book(name: str, publisher=None, grade=None, semester=None) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM books WHERE name = ?", (name,))
    row = cur.fetchone()
    if row:
        conn.close()
        return row["id"]
    cur.execute("INSERT INTO books (name, publisher, grade, semester) VALUES (?, ?, ?, ?)",
               (name, publisher, grade, semester))
    book_id = cur.lastrowid
    conn.commit()
    conn.close()
    return book_id


def get_or_create_unit(book_id: int, unit_no: int, title=None) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM units WHERE book_id = ? AND unit_no = ?", (book_id, unit_no))
    row = cur.fetchone()
    if row:
        conn.close()
        return row["id"]
    cur.execute("INSERT INTO units (book_id, unit_no, title) VALUES (?, ?, ?)",
               (book_id, unit_no, title))
    unit_id = cur.lastrowid
    conn.commit()
    conn.close()
    return unit_id


def get_or_create_lesson(unit_id: int, lesson_no: int, title=None) -> int:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM lessons WHERE unit_id = ? AND lesson_no = ?", (unit_id, lesson_no))
    row = cur.fetchone()
    if row:
        conn.close()
        return row["id"]
    cur.execute("INSERT INTO lessons (unit_id, lesson_no, title) VALUES (?, ?, ?)",
               (unit_id, lesson_no, title))
    lesson_id = cur.lastrowid
    conn.commit()
    conn.close()
    return lesson_id


def add_lesson_text(lesson_id: int, content: str, text_type: str = 'main') -> int:
    conn = get_connection()
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
    conn.close()
    return text_id


def analyze_and_update_words(lesson_id: int, content: str) -> list[str]:
    word_pairs = extract_words(content)
    lemma_data = defaultdict(lambda: {"count": 0, "forms": Counter()})
    for lemma, form in word_pairs:
        lemma_data[lemma]["count"] += 1
        lemma_data[lemma]["forms"][form] += 1

    conn = get_connection()
    cur = conn.cursor()
    new_words = []

    for lemma, data in lemma_data.items():
        total = data["count"]
        forms = data["forms"]

        cur.execute("SELECT id, first_lesson_id FROM words WHERE word = ?", (lemma,))
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
    conn.close()
    return sorted(new_words)


def lookup_word(word: str) -> dict | None:
    word = word.lower().strip()
    lemma = lemmatize_word(word)

    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id, first_lesson_id FROM words WHERE word = ?", (lemma,))
    row = cur.fetchone()
    if not row:
        cur.execute("SELECT id, first_lesson_id FROM words WHERE word = ?", (word,))
        row = cur.fetchone()
    if not row:
        conn.close()
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

    conn.close()
    total_count = sum(o["count"] for o in occurrences)

    # Extract sentence-level contexts for each lesson
    all_forms_set = {lemma, word}
    all_forms_set.update(f for f, _ in forms)
    form_pattern = __import__('re').compile(
        r'(' + '|'.join(__import__('re').escape(f) for f in all_forms_set) + r')',
        __import__('re').IGNORECASE
    )

    for occ in occurrences:
        cur2 = get_connection()
        cur2.execute("SELECT content FROM lesson_texts WHERE lesson_id = ?", (occ["lesson_id"],))
        text_rows = cur2.fetchall()
        cur2.close()
        full_text = ' '.join(r["content"] for r in text_rows)
        sentences = __import__('re').split(r'(?<=[.!?])\s+', full_text)
        occ["contexts"] = [s for s in sentences if form_pattern.search(s)][:3]

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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT word FROM words WHERE first_lesson_id = ? ORDER BY word", (lesson_id,))
    words = [row["word"] for row in cur.fetchall()]
    conn.close()
    return words


def get_lesson_word_forms(lesson_id: int) -> dict[str, list[str]]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, word FROM words WHERE first_lesson_id = ? ORDER BY word", (lesson_id,))
    new_words = cur.fetchall()
    result = {}
    for row in new_words:
        cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY form", (row["id"],))
        forms = [r["form"] for r in cur.fetchall()]
        result[row["word"]] = forms
    conn.close()
    return result


def get_all_new_words_for_lesson(lesson_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT content FROM lesson_texts WHERE lesson_id = ?", (lesson_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
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

    conn.close()
    return {"new_words": new_words, "review_words": review_words, "all_words": all_lemmas}


def get_lesson_text(lesson_id: int) -> str | None:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT content FROM lesson_texts WHERE lesson_id = ? ORDER BY text_type", (lesson_id,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    return "\n\n".join(r["content"] for r in rows)


def rebuild_word_index() -> int:
    conn = get_connection()
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

    for row in texts:
        lesson_id = row["lesson_id"]
        content = row["content"]
        word_pairs = extract_words(content)

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
    conn.close()
    return total_words


def list_books() -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books ORDER BY id")
    books = [dict(r) for r in cur.fetchall()]
    conn.close()
    return books


def list_units(book_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM units WHERE book_id = ? ORDER BY unit_no", (book_id,))
    units = [dict(r) for r in cur.fetchall()]
    conn.close()
    return units


def list_lessons(unit_id: int) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lessons WHERE unit_id = ? ORDER BY lesson_no", (unit_id,))
    lessons = [dict(r) for r in cur.fetchall()]
    conn.close()
    return lessons


def get_full_lesson_path(lesson_id: int) -> str:
    conn = get_connection()
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
    conn.close()
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
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
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
    conn.close()
    return result


def update_unit(unit_id: int, unit_no: int = None, title: str | None = ...) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
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
    conn.close()
    return result


def update_lesson(lesson_id: int, lesson_no: int = None, title: str | None = ...) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
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
    conn.close()
    return result


def delete_lesson(lesson_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT l.id, l.title, l.lesson_no FROM lessons l WHERE l.id = ?", (lesson_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Lesson {lesson_id} not found")
    # Delete word occurrences for this lesson first
    cur.execute("""
        DELETE FROM word_occurrences WHERE lesson_id = ?
    """, (lesson_id,))
    # The ON DELETE CASCADE will handle lesson_texts, but we clean words manually
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
    conn.close()
    return {"deleted": "lesson", "id": lesson_id, "title": row["title"], "lesson_no": row["lesson_no"]}


def delete_unit(unit_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM units WHERE id = ?", (unit_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Unit {unit_id} not found")
    info = _count_descendants_unit(conn, unit_id)
    # Get all lesson ids under this unit
    cur.execute("SELECT id FROM lessons WHERE unit_id = ?", (unit_id,))
    lesson_ids = [r["id"] for r in cur.fetchall()]
    # Delete word occurrences for all lessons in this unit
    if lesson_ids:
        placeholders = ",".join("?" * len(lesson_ids))
        cur.execute(f"DELETE FROM word_occurrences WHERE lesson_id IN ({placeholders})", lesson_ids)
    # ON DELETE CASCADE handles lesson_texts and lessons when we delete the unit
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
    conn.close()
    return {"deleted": "unit", "id": unit_id, "title": row["title"], "unit_no": row["unit_no"], **info}


def delete_book(book_id: int) -> dict:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM books WHERE id = ?", (book_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        raise ValueError(f"Book {book_id} not found")
    info = _count_descendants_book(conn, book_id)
    # Get all lesson ids under this book
    cur.execute("""
        SELECT l.id FROM lessons l
        JOIN units u ON u.id = l.unit_id WHERE u.book_id = ?
    """, (book_id,))
    lesson_ids = [r["id"] for r in cur.fetchall()]
    # Delete word occurrences for all lessons in this book
    if lesson_ids:
        placeholders = ",".join("?" * len(lesson_ids))
        cur.execute(f"DELETE FROM word_occurrences WHERE lesson_id IN ({placeholders})", lesson_ids)
    # ON DELETE CASCADE handles the rest when we delete the book
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
    conn.close()
    return {"deleted": "book", "id": book_id, "name": row["name"], **info}


def reorder_units(book_id: int, unit_ids: list[int]) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM units WHERE book_id = ?", (book_id,))
    existing = {r["id"] for r in cur.fetchall()}
    if set(unit_ids) != existing:
        conn.close()
        raise ValueError("unit_ids do not match existing units for this book")
    for new_no, uid in enumerate(unit_ids, 1):
        cur.execute("UPDATE units SET unit_no = ? WHERE id = ?", (new_no, uid))
    conn.commit()
    cur.execute("SELECT * FROM units WHERE book_id = ? ORDER BY unit_no", (book_id,))
    result = [dict(r) for r in cur.fetchall()]
    conn.close()
    return result


def reorder_lessons(unit_id: int, lesson_ids: list[int]) -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM lessons WHERE unit_id = ?", (unit_id,))
    existing = {r["id"] for r in cur.fetchall()}
    if set(lesson_ids) != existing:
        conn.close()
        raise ValueError("lesson_ids do not match existing lessons for this unit")
    for new_no, lid in enumerate(lesson_ids, 1):
        cur.execute("UPDATE lessons SET lesson_no = ? WHERE id = ?", (new_no, lid))
    conn.commit()
    cur.execute("SELECT * FROM lessons WHERE unit_id = ? ORDER BY lesson_no", (unit_id,))
    result = [dict(r) for r in cur.fetchall()]
    conn.close()
    return result


# --- Vocab & Quiz functions ---

def get_all_vocab(q: str | None = None, sort: str = "alpha") -> list[dict]:
    conn = get_connection()
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

    conn.close()
    return rows


def get_random_quiz_words(count: int = 10) -> list[dict]:
    conn = get_connection()
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
    conn.close()
    return rows


def get_lesson_quiz_words(lesson_id: int) -> list[dict]:
    conn = get_connection()
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
    conn.close()
    return rows


def get_mistake_words() -> list[dict]:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT w.id, w.word, w.first_lesson_id,
               COALESCE(SUM(wo.count), 0) AS total_count,
               latest.latest_result, latest.latest_time,
               latest.unknown_count
        FROM words w
        LEFT JOIN word_occurrences wo ON wo.word_id = w.id
        JOIN (
            SELECT word_id,
                   MAX(CASE WHEN result = 'unknown' THEN created_at END) AS latest_time,
                   SUM(CASE WHEN result = 'unknown' THEN 1 ELSE 0 END) AS unknown_count,
                   FIRST_VALUE(result) OVER (PARTITION BY word_id ORDER BY created_at DESC) AS latest_result
            FROM word_quiz_log
        ) latest ON latest.word_id = w.id AND latest.latest_result = 'unknown'
        GROUP BY w.id
        ORDER BY latest.latest_time DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        cur.execute("SELECT form FROM word_forms WHERE word_id = ? ORDER BY count DESC", (row["id"],))
        row["forms"] = [r["form"] for r in cur.fetchall()]
        if row["first_lesson_id"]:
            row["first_lesson_path"] = get_full_lesson_path(row["first_lesson_id"])
        else:
            row["first_lesson_path"] = None
    conn.close()
    return rows


def record_quiz_result(word_id: int, result: str, quiz_type: str = "random", lesson_id: int | None = None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO word_quiz_log (word_id, result, quiz_type, lesson_id)
        VALUES (?, ?, ?, ?)
    """, (word_id, result, quiz_type, lesson_id))
    conn.commit()
    conn.close()
    return {"word_id": word_id, "result": result}


def clear_mistake(word_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO word_quiz_log (word_id, result, quiz_type)
        VALUES (?, 'known', 'manual')
    """, (word_id,))
    conn.commit()
    conn.close()
    return {"word_id": word_id, "result": "cleared"}
