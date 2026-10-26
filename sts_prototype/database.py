"""SQLite history. Each saved session keeps its full export and a small summary."""
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager


@contextmanager
def connect(path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY, saved_at TEXT NOT NULL,
        input_source TEXT NOT NULL, complete INTEGER NOT NULL,
        cycles INTEGER NOT NULL, attempt_count INTEGER NOT NULL,
        payload TEXT NOT NULL
    )''')
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def save_session(path, sid, saved_at, data):
    with connect(path) as connection:
        connection.execute('''INSERT INTO sessions
            (id, saved_at, input_source, complete, cycles, attempt_count, payload)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO NOTHING''',
            (sid, saved_at, data['input_source'], data['complete'], data['cycles'],
             len(data['attempts']), json.dumps(data, allow_nan=False)))


def list_sessions(path, limit=50, offset=0):
    with connect(path) as connection:
        total = connection.execute('SELECT COUNT(*) FROM sessions').fetchone()[0]
        rows = connection.execute('''SELECT id, saved_at, input_source, complete,
            cycles, attempt_count FROM sessions
            ORDER BY saved_at DESC, id DESC LIMIT ? OFFSET ?''', (limit, offset)).fetchall()
    return {'items': [dict(row) for row in rows], 'total': total,
            'limit': limit, 'offset': offset}


def load_session(path, sid):
    with connect(path) as connection:
        row = connection.execute('SELECT id, saved_at, payload FROM sessions WHERE id = ?', (sid,)).fetchone()
    if row is None:
        return None
    return {'id': row['id'], 'saved_at': row['saved_at'], 'data': json.loads(row['payload'])}
