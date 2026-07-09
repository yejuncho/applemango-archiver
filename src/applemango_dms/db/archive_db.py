import sqlite3
from pathlib import Path
from applemango_dms.config import DEFAULT_DOCUMENT_TYPES

class ArchiveDatabase:
    STATUS_ACTIVE = 'active'
    STATUS_DELETED = 'deleted'
    STATUS_MISSING = 'missing'

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
                    archived_filename TEXT NOT NULL UNIQUE,
                    display_title TEXT,

                    -- paths
                    full_path TEXT NOT NULL UNIQUE,
                    source_path TEXT,

                    -- document meaning
                    document_type TEXT,
                    document_date TEXT,
                    tags TEXT,
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
            self._migrate_files_table(conn)
            conn.commit()

    def _migrate_files_table(self, conn):
        required_columns = {
            # workspace / ownership
            'workspace': 'TEXT',
            'uploaded_by': 'TEXT',

            # file names
            'original_filename': 'TEXT',
            'archived_filename': 'TEXT',
            'display_title': 'TEXT',

            # paths
            'full_path': 'TEXT',
            'source_path': 'TEXT',

            # document meaning
            'document_type': 'TEXT',
            'document_date': 'TEXT',
            'tags': 'TEXT',
            'description': 'TEXT',
            'notes': 'TEXT',

            # file technical metadata
            'file_ext': 'TEXT',
            'mime_type': 'TEXT',
            'file_size': 'INTEGER',
            'checksum': 'TEXT',

            # lifecycle
            'archive_date': 'TEXT',
            'archived_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
            'modified_at': 'TEXT',
            'last_accessed_at': 'TEXT',

            # status
            'status': "TEXT DEFAULT 'active'",
            'is_favorite': 'INTEGER DEFAULT 0',
            'is_deleted': 'INTEGER DEFAULT 0',
            'deleted_at': 'TEXT',
        }

        existing_columns = {
            row[1] for row in conn.execute('PRAGMA table_info(files)').fetchall()
        }

        for column_name, column_definition in required_columns.items():
            if column_name in existing_columns:
                continue
            conn.execute(f'ALTER TABLE files ADD COLUMN {column_name} {column_definition}')

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
                    workspace, uploaded_by,
                    original_filename, archived_filename, display_title,
                    full_path, source_path,
                    document_type, document_date, tags, description, notes,
                    file_ext, mime_type, file_size, checksum,
                    archive_date, archived_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("workspace", ""),
                    record.get("uploaded_by", ""),

                    record.get("original_filename", ""),
                    record.get("archived_filename", ""),
                    record.get("display_title", ""),

                    record.get("full_path", ""),
                    record.get("source_path", ""),

                    record.get("document_type", ""),
                    record.get("document_date", ""),
                    record.get("tags", ""),
                    record.get("description", ""),
                    record.get("notes", ""),

                    record.get("file_ext", ""),
                    record.get("mime_type", ""),
                    int(record.get("file_size", 0) or 0),
                    record.get("checksum", ""),

                    record.get("archive_date", ""),
                    record.get("archived_at", ""),
                ),
            )
            conn.commit()

    def _normalize_statuses(self, statuses):
        if statuses is None:
            return [self.STATUS_ACTIVE]

        normalized = []
        for value in statuses:
            token = str(value or '').strip().lower()
            if token:
                normalized.append(token)
        return normalized or [self.STATUS_ACTIVE]

    def audit_missing_files(self, workspace):
        workspace_name = str(workspace or '').strip()
        if not workspace_name:
            return 0

        with self._connect() as conn:
            rows = conn.execute(
                'SELECT id, full_path FROM files WHERE workspace = ? AND status = ?',
                (workspace_name, self.STATUS_ACTIVE),
            ).fetchall()

            missing_ids = []
            for row_id, full_path in rows:
                try:
                    exists = Path(str(full_path or '')).exists()
                except Exception:
                    exists = False
                if not exists:
                    missing_ids.append(int(row_id))

            if not missing_ids:
                return 0

            placeholders = ','.join('?' for _ in missing_ids)
            conn.execute(
                f'UPDATE files SET status = ? WHERE id IN ({placeholders})',
                [self.STATUS_MISSING] + missing_ids,
            )
            conn.commit()
            return len(missing_ids)

    def search_files(self, workspace, date_prefix=None, document_type='전체', tags='', free_text='', statuses=None):
        self.audit_missing_files(workspace)

        normalized_statuses = self._normalize_statuses(statuses)
        query = (
            'SELECT archive_date, document_type, tags, archived_filename, uploaded_by, file_size, full_path '
            'FROM files WHERE workspace = ?'
        )
        params = [workspace]

        status_placeholders = ','.join('?' for _ in normalized_statuses)
        query += f' AND status IN ({status_placeholders})'
        params.extend(normalized_statuses)

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
        self.audit_missing_files(workspace)
        with self._connect() as conn:
            row = conn.execute(
                'SELECT COUNT(*) FROM files WHERE workspace = ? AND status = ?',
                (workspace, self.STATUS_ACTIVE),
            ).fetchone()
        return int(row[0] if row and row[0] is not None else 0)

    def get_archived_filenames(self, workspace):
        with self._connect() as conn:
            rows = conn.execute(
                'SELECT archived_filename FROM files WHERE workspace = ? AND archived_filename IS NOT NULL AND archived_filename != ""',
                (workspace,),
            ).fetchall()
        return {row[0] for row in rows if row and row[0]}

    def mark_files_deleted_by_paths(self, workspace, full_paths):
        targets = [str(path) for path in full_paths if str(path).strip()]
        if not targets:
            return 0

        with self._connect() as conn:
            placeholders = ','.join('?' for _ in targets)
            cursor = conn.execute(
                f'''
                UPDATE files
                SET
                    status = ?,
                    is_deleted = 1,
                    deleted_at = CURRENT_TIMESTAMP
                WHERE workspace = ? AND full_path IN ({placeholders})
                ''',
                [self.STATUS_DELETED, workspace] + targets,
            )
            conn.commit()
            return int(cursor.rowcount or 0)

    def delete_file_records_by_paths(self, workspace, full_paths):
        # Backward-compatible alias. Records are now soft-deleted instead of removed.
        return self.mark_files_deleted_by_paths(workspace, full_paths)