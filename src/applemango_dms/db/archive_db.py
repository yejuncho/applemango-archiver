import sqlite3
from pathlib import Path
from applemango_dms.config import DEFAULT_DOCUMENT_TYPES

class ArchiveDatabase:
    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- workspace / ownership
                    workspace TEXT NOT NULL,
                    uploaded_by TEXT,

                    -- file names
                    original_filename TEXT NOT NULL,
                    archived_filename TEXT NOT NULL,
                    display_title TEXT,

                    -- paths
                    full_path TEXT NOT NULL UNIQUE,
                    source_path TEXT,

                    -- document meaning
                    document_type TEXT,
                    document_date TEXT,
                    description TEXT,
                    notes TEXT,

                    -- file technical metadata
                    file_ext TEXT,
                    mime_type TEXT,
                    file_size INTEGER,
                    checksum TEXT,

                    -- lifecycle
                    archive_date TEXT,
                    archived_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    modified_at TEXT,
                    last_accessed_at TEXT,

                    -- status
                    status TEXT DEFAULT 'active',
                    is_favorite INTEGER DEFAULT 0,
                    is_deleted INTEGER DEFAULT 0,
                    deleted_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_types (
                    name TEXT PRIMARY KEY
                )
                """
            )
            conn.executemany(
                'INSERT OR IGNORE INTO document_types(name) VALUES (?)',
                [(item,) for item in DEFAULT_DOCUMENT_TYPES],
            )
            conn.commit()

    def get_document_types(self):
        with self._connect() as conn:
            rows = conn.execute('SELECT name FROM document_types ORDER BY name COLLATE NOCASE').fetchall()
        values = [row[0] for row in rows]
        return values or list(DEFAULT_DOCUMENT_TYPES)

    def insert_file_record(self, record):
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO files (
                    workspace, original_filename, archived_filename, full_path,
                    document_type, tags, uploaded_by, archive_date, archived_at,
                    file_ext, file_size, source_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                (
                    record.get('workspace', ''),
                    record.get('original_filename', ''),
                    record.get('archived_filename', ''),
                    record.get('full_path', ''),
                    record.get('document_type', ''),
                    record.get('tags', ''),
                    record.get('uploaded_by', ''),
                    record.get('archive_date', ''),
                    record.get('archived_at', ''),
                    record.get('file_ext', ''),
                    int(record.get('file_size', 0) or 0),
                    record.get('source_path', ''),
                ),
            )
            conn.commit()

    def search_files(self, workspace, date_prefix=None, document_type='전체', tags='', free_text=''):
        query = (
            'SELECT archive_date, document_type, tags, archived_filename, uploaded_by, file_size, full_path '
            'FROM files WHERE workspace = ?'
        )
        params = [workspace]

        if date_prefix:
            query += ' AND archive_date LIKE ?'
            params.append(f'{date_prefix}%')

        if document_type and document_type != '전체':
            query += ' AND document_type = ?'
            params.append(document_type)

        if tags:
            query += ' AND tags LIKE ?'
            params.append(f'%{tags}%')

        if free_text:
            query += (
                ' AND ('
                'original_filename LIKE ? OR archived_filename LIKE ? OR tags LIKE ? OR '
                'uploaded_by LIKE ? OR source_path LIKE ? OR full_path LIKE ?'
                ')'
            )
            token = f'%{free_text}%'
            params.extend([token, token, token, token, token, token])

        query += ' ORDER BY archive_date DESC, archived_at DESC'

        with self._connect() as conn:
            return conn.execute(query, params).fetchall()

    def count_files_by_workspace(self, workspace):
        with self._connect() as conn:
            row = conn.execute('SELECT COUNT(*) FROM files WHERE workspace = ?', (workspace,)).fetchone()
        return int(row[0] if row and row[0] is not None else 0)

    def get_archived_filenames(self, workspace):
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT archived_filename FROM files WHERE workspace = ? AND archived_filename IS NOT NULL AND archived_filename != ""',
                (workspace,),
            ).fetchall()
        return {row[0] for row in rows if row and row[0]}

    def delete_file_records_by_paths(self, workspace, full_paths):
        targets = [str(path) for path in full_paths if str(path).strip()]
        if not targets:
            return

        with self._connect() as conn:
            placeholders = ','.join('?' for _ in targets)
            conn.execute(
                f'DELETE FROM files WHERE workspace = ? AND full_path IN ({placeholders})',
                [workspace] + targets,
            )
            conn.commit()