import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "english_helper.db")

STOP_WORDS = frozenset({
    "a", "an", "the",
    "am", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "will", "would", "shall", "should", "can", "could", "may", "might", "must",
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "what", "which", "who", "whom", "whose",
    "this", "that", "these", "those",
    "and", "or", "but", "not", "no", "nor",
    "if", "then", "than", "too", "very",
    "in", "on", "at", "to", "for", "of", "with", "from", "by",
    "up", "down", "out", "off", "over", "under",
    "about", "into", "through", "between", "after", "before",
    "so", "as", "just", "also", "there", "here",
})


def get_connection(autocommit=False):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    if autocommit:
        conn.isolation_level = None
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            name        TEXT NOT NULL UNIQUE,
            publisher   TEXT,
            grade       TEXT,
            semester    TEXT,
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS units (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id     INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
            unit_no     INTEGER NOT NULL,
            title       TEXT,
            UNIQUE(book_id, unit_no)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lessons (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            unit_id     INTEGER NOT NULL REFERENCES units(id) ON DELETE CASCADE,
            lesson_no   INTEGER NOT NULL,
            title       TEXT,
            UNIQUE(unit_id, lesson_no)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS lesson_texts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lesson_id   INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            text_type   TEXT NOT NULL DEFAULT 'main',
            content     TEXT NOT NULL,
            UNIQUE(lesson_id, text_type)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS words (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            word            TEXT NOT NULL UNIQUE,
            first_lesson_id INTEGER REFERENCES lessons(id),
            created_at      TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS word_forms (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id     INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
            form        TEXT NOT NULL,
            count       INTEGER NOT NULL DEFAULT 1,
            UNIQUE(word_id, form)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS word_occurrences (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id     INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
            lesson_id   INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
            count       INTEGER NOT NULL DEFAULT 1,
            UNIQUE(word_id, lesson_id)
        )
    """)

    cur.execute("CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_word_forms_word_id ON word_forms(word_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_word_forms_form ON word_forms(form)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_word_occurrences_word_id ON word_occurrences(word_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_word_occurrences_lesson_id ON word_occurrences(lesson_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_lessons_unit_id ON lessons(unit_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_units_book_id ON units(book_id)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS word_quiz_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            word_id     INTEGER NOT NULL REFERENCES words(id) ON DELETE CASCADE,
            result      TEXT NOT NULL CHECK(result IN ('known', 'unknown')),
            quiz_type   TEXT NOT NULL DEFAULT 'random',
            lesson_id   INTEGER REFERENCES lessons(id),
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_quiz_log_word_id ON word_quiz_log(word_id)")

    conn.commit()
    conn.close()
    print(f"Database initialized: {DB_PATH}")


if __name__ == "__main__":
    init_db()
