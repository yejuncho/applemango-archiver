import sqlite3
from pathlib import Path

class ArchiveDatabase:
    STATUS_ACTIVE = 'active'
    STATUS_DELETED = 'deleted'
    STATUS_MISSING = 'missing'

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON;')
        return conn

    def _init_db(self):
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workspaces (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    name TEXT NOT NULL UNIQUE,
                    share_path TEXT NOT NULL UNIQUE,

                    is_active INTEGER NOT NULL DEFAULT 1
                        CHECK (is_active IN (0, 1)),

                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TEXT
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS document_types (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    workspace_id INTEGER NOT NULL,
                    name TEXT NOT NULL,

                    is_active INTEGER NOT NULL DEFAULT 1
                        CHECK (is_active IN (0, 1)),
                    
                    sort_order INTEGER NOT NULL DEFAULT 0,

                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    deleted_at TEXT,

                    UNIQUE (workspace_id, name),
                    UNIQUE (workspace_id, id),

                    FOREIGN KEY (workspace_id)
                        REFERENCES workspaces(id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,

                    -- relationships
                    workspace_id INTEGER NOT NULL,
                    document_type_id INTEGER NOT NULL,

                    -- ownership
                    uploaded_by TEXT NOT NULL,

                    -- file names
                    original_filename TEXT NOT NULL,
                    archived_filename TEXT NOT NULL,

                    -- paths
                    relative_path TEXT NOT NULL,

                    -- dates
                    document_date TEXT NOT NULL,
                    source_created_at TEXT,
                    source_modified_at TEXT,

                    -- technical metadata
                    file_ext TEXT NOT NULL,
                    mime_type TEXT,

                    file_size INTEGER
                        CHECK (file_size IS NULL
                        OR file_size >= 0),

                    checksum TEXT,

                    -- lifecycle
                    archived_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,

                    -- status
                    status TEXT NOT NULL DEFAULT 'active'
                        CHECK (
                            status IN (
                                'active',
                                'deleted',
                                'missing'
                            )
                        ),

                    deleted_at TEXT,

                    UNIQUE (workspace_id, archived_filename),
                    UNIQUE (workspace_id, relative_path),

                    FOREIGN KEY (workspace_id)
                        REFERENCES workspaces(id)
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT,

                    FOREIGN KEY (
                    workspace_id,
                    document_type_id
                    )
                        REFERENCES document_types(
                        workspace_id,
                        id
                        )
                        ON UPDATE CASCADE
                        ON DELETE RESTRICT
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    
                    workspace_id INTEGER NOT NULL,

                    name TEXT NOT NULL COLLATE NOCASE,

                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    UNIQUE (workspace_id, name),

                    FOREIGN KEY (workspace_id)
                        REFERENCES workspaces(id)
                        ON UPDATE CASCADE
                        ON DELETE CASCADE
                );
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS file_tags (
                    file_id INTEGER NOT NULL,
                    tag_id INTEGER NOT NULL,

                    PRIMARY KEY (file_id, tag_id),

                    FOREIGN KEY (file_id)
                        REFERENCES files(id)
                        ON DELETE CASCADE,

                    FOREIGN KEY (tag_id)
                        REFERENCES tags(id)
                        ON DELETE CASCADE
                );
                """
            )

            self._create_indexes(conn)
            conn.commit()

    def _create_indexes(self, conn):
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_status
            ON files(workspace_id, status);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_original_filename
            ON files(workspace_id, original_filename);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_document_type
            ON files(workspace_id, document_type_id);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_document_date
            ON files(workspace_id, document_date);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_archived_at
            ON files(workspace_id, archived_at);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_source_created_at
            ON files(workspace_id, source_created_at);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_file_ext
            ON files(workspace_id, file_ext);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_files_workspace_uploaded_by
            ON files(workspace_id, uploaded_by);
            """
        )

        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_file_tags_tag_file
            ON file_tags(tag_id, file_id);
            """
        )

    def get_document_types(self, workspace_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, name
                FROM document_types
                WHERE workspace_id = ?
                    AND is_active = 1
                    AND deleted_at IS NULL
                ORDER BY sort_order, name COLLATE NOCASE;
                """,
                (workspace_id,),
            ).fetchall()

        return [dict(row) for row in rows]

    @staticmethod
    def _require_text(value, field_name):
        normalized = str(value or "").strip()

        if not normalized:
            raise ValueError(f"{field_name} is required.")
        
        return normalized

    def insert_file_record(self, record):
        file_ext = self._require_text(
            record.get("file_ext"),
            "file_ext",
        ).lower()

        if not file_ext.startswith("."):
            file_ext = f".{file_ext}"

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO files (
                    workspace_id,
                    document_type_id,
                    uploaded_by,
                    original_filename,
                    archived_filename,
                    relative_path,
                    document_date,
                    source_created_at,
                    source_modified_at,
                    file_ext,
                    mime_type,
                    file_size,
                    checksum
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(record["workspace_id"]),
                    int(record["document_type_id"]),
                    self._require_text(
                        record.get("uploaded_by"),
                        "uploaded_by",
                    ),
                    self._require_text(
                        record.get("original_filename"),
                        "original_filename",
                    ),
                    self._require_text(
                        record.get("archived_filename"),
                        "archived_filename",
                    ),
                    self._require_text(
                        record.get("relative_path"),
                        "relative_path",
                    ),
                    self._require_text(
                        record.get("document_date"),
                        "document_date",
                    ),
                    record.get("source_created_at"),
                    record.get("source_modified_at"),
                    file_ext,
                    record.get("mime_type"),
                    record.get("file_size"),
                    record.get("checksum"),
                ),
            )

            return int(cursor.lastrowid)

    def _normalize_statuses(self, statuses):
        if statuses is None:
            return [self.STATUS_ACTIVE]

        normalized = []
        for value in statuses:
            token = str(value or '').strip().lower()
            if token:
                normalized.append(token)
        return normalized or [self.STATUS_ACTIVE]

    def reconcile_file_statuses(self, workspace_id):
        with self._connect() as conn:
            workspace = conn.execute(
                """
                SELECT share_path
                FROM workspaces
                WHERE id = ?
                AND deleted_at IS NULL
                """,
                (workspace_id,),
            ).fetchone()

            if workspace is None:
                raise LookupError("Workspace not found.")

            share_path = Path(workspace["share_path"])

            if not share_path.exists():
                raise ConnectionError(
                    f"The workspace shared folder at "
                    f"'{share_path}' is not currently accessible."
                )

            rows = conn.execute(
                """
                SELECT
                    id,
                    relative_path,
                    status
                FROM files
                WHERE workspace_id = ?
                AND status IN (?, ?)
                """,
                (
                    workspace_id,
                    self.STATUS_ACTIVE,
                    self.STATUS_MISSING,
                ),
            ).fetchall()

            missing_ids = []
            restored_ids = []

            for row in rows:
                full_path = share_path / row["relative_path"]

                try:
                    file_exists = full_path.is_file()
                except OSError:
                    file_exists = False

                current_status = row["status"]
                file_id = int(row["id"])

                if (
                    current_status == self.STATUS_ACTIVE
                    and not file_exists
                ):
                    missing_ids.append(file_id)

                elif (
                    current_status == self.STATUS_MISSING
                    and file_exists
                ):
                    restored_ids.append(file_id)

            if missing_ids:
                placeholders = ",".join("?" for _ in missing_ids)

                conn.execute(
                    f"""
                    UPDATE files
                    SET status = ?
                    WHERE workspace_id = ?
                    AND id IN ({placeholders})
                    """,
                    [
                        self.STATUS_MISSING,
                        workspace_id,
                        *missing_ids,
                    ],
                )

            if restored_ids:
                placeholders = ",".join("?" for _ in restored_ids)

                conn.execute(
                    f"""
                    UPDATE files
                    SET status = ?
                    WHERE workspace_id = ?
                    AND id IN ({placeholders})
                    """,
                    [
                        self.STATUS_ACTIVE,
                        workspace_id,
                        *restored_ids,
                    ],
                )

            return {
                "marked_missing": len(missing_ids),
                "restored_active": len(restored_ids),
                "checked": len(rows),
            }

    def audit_missing_files(self, workspace_id):
        result = self.reconcile_file_statuses(workspace_id)
        return result["marked_missing"]

    def count_files_by_workspace(self, workspace_id):
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT COUNT(*)
                FROM files
                WHERE workspace_id = ?
                AND status = ?
                """,
                (workspace_id, self.STATUS_ACTIVE),
            ).fetchone()

        return int(row[0])

    def get_archived_filenames(self, workspace_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT archived_filename
                FROM files
                WHERE workspace_id = ?
                AND archived_filename != ''
                """,
                (workspace_id,),
            ).fetchall()

        return {
            row["archived_filename"]
            for row in rows
        }

    def mark_files_deleted(self, workspace_id, file_ids):
        normalized_ids = list({
            int(file_id)
            for file_id in file_ids
        })

        if not normalized_ids:
            return 0

        placeholders = ",".join("?" for _ in normalized_ids)

        with self._connect() as conn:
            cursor = conn.execute(
                f"""
                UPDATE files
                SET
                    status = ?,
                    deleted_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ?
                AND status IN (?, ?)
                AND id IN ({placeholders})
                """,
                [
                    self.STATUS_DELETED,
                    workspace_id,
                    self.STATUS_ACTIVE,
                    self.STATUS_MISSING,
                    *normalized_ids,
                ],
            )

            return int(cursor.rowcount or 0)

    @staticmethod
    def _normalize_tag_names(tag_names):
        if tag_names is None:
            return []

        if isinstance(tag_names, str):
            tag_names = [tag_names]

        normalized = []
        seen = set()

        for value in tag_names:
            name = str(value or "").strip()
            key = name.casefold()

            if name and key not in seen:
                normalized.append(name)
                seen.add(key)

        return normalized

    def assign_tags(self, workspace_id, file_id, tag_names):
        normalized_names = self._normalize_tag_names(tag_names)

        with self._connect() as conn:
            file_row = conn.execute(
                """
                SELECT id
                FROM files
                WHERE id = ?
                AND workspace_id = ?
                """,
                (file_id, workspace_id),
            ).fetchone()

            if file_row is None:
                raise LookupError("File not found in workspace.")

            for name in normalized_names:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO tags (
                        workspace_id,
                        name
                    )
                    VALUES (?, ?)
                    """,
                    (workspace_id, name),
                )

                tag_row = conn.execute(
                    """
                    SELECT id
                    FROM tags
                    WHERE workspace_id = ?
                    AND name = ?
                    """,
                    (workspace_id, name),
                ).fetchone()

                conn.execute(
                    """
                    INSERT OR IGNORE INTO file_tags (
                        file_id,
                        tag_id
                    )
                    VALUES (?, ?)
                    """,
                    (file_id, tag_row["id"]),
                )

    def get_workspace_tags(self, workspace_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    id,
                    name,
                    created_at
                FROM tags
                WHERE workspace_id = ?
                ORDER BY name COLLATE NOCASE;
                """,
                (workspace_id,),
            ).fetchall()

        return [dict(row) for row in rows]
    
    def search_workspace_tags(self, workspace_id, search_text, limit=10):
        normalized_text = str(search_text or "").strip()
        normalized_limit = max(1, min(int(limit), 50))

        with self._connect() as conn:
            if normalized_text:
                rows = conn.execute(
                    """
                    SELECT id, name
                    FROM tags
                    WHERE workspace_id = ?
                    AND name LIKE ? COLLATE NOCASE
                    ORDER BY name COLLATE NOCASE
                    LIMIT ?;
                    """,
                    (
                        workspace_id,
                        f"{normalized_text}%",
                        normalized_limit,
                    ),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, name
                    FROM tags
                    WHERE workspace_id = ?
                    ORDER BY name COLLATE NOCASE
                    LIMIT ?;
                    """,
                    (
                        workspace_id,
                        normalized_limit,
                    ),
                ).fetchall()

        return [dict(row) for row in rows]
    
    def get_file_tags(self, workspace_id, file_id):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    tags.id,
                    tags.name
                FROM files
                INNER JOIN file_tags
                    ON file_tags.file_id = files.id
                INNER JOIN tags
                    ON tags.id = file_tags.tag_id
                WHERE files.id = ?
                AND files.workspace_id = ?
                ORDER BY tags.name COLLATE NOCASE;
                """,
                (
                    file_id,
                    workspace_id,
                ),
            ).fetchall()

        return [dict(row) for row in rows]
    
    def replace_file_tags(self, workspace_id, file_id, tag_names):
        normalized_names = self._normalize_tag_names(tag_names)

        with self._connect() as conn:
            file_row = conn.execute(
                """
                SELECT id
                FROM files
                WHERE id = ?
                AND workspace_id = ?;
                """,
                (file_id, workspace_id),
            ).fetchone()

            if file_row is None:
                raise LookupError("File not found in workspace.")

            conn.execute(
                """
                DELETE FROM file_tags
                WHERE file_id = ?;
                """,
                (file_id,),
            )

            for name in normalized_names:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO tags (
                        workspace_id,
                        name
                    )
                    VALUES (?, ?);
                    """,
                    (workspace_id, name),
                )

                tag_row = conn.execute(
                    """
                    SELECT id
                    FROM tags
                    WHERE workspace_id = ?
                    AND name = ?;
                    """,
                    (workspace_id, name),
                ).fetchone()

                conn.execute(
                    """
                    INSERT INTO file_tags (
                        file_id,
                        tag_id
                    )
                    VALUES (?, ?);
                    """,
                    (file_id, tag_row["id"]),
                )