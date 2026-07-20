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

    def ensure_workspace(self, workspace_name, share_path, default_document_types):
        normalized_name = self._require_text(workspace_name, "workspace_name")
        normalized_share_path = self._require_text(str(share_path), "share_path")

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id
                FROM workspaces
                WHERE name = ?
                """,
                (normalized_name,),
            ).fetchone()

            if row is None:
                cursor = conn.execute(
                    """
                    INSERT INTO workspaces (
                        name,
                        share_path,
                        is_active,
                        deleted_at
                    )
                    VALUES (?, ?, 1, NULL)
                    """,
                    (normalized_name, normalized_share_path),
                )
                workspace_id = int(cursor.lastrowid)
            else:
                workspace_id = int(row["id"])
                conn.execute(
                    """
                    UPDATE workspaces
                    SET
                        share_path = ?,
                        is_active = 1,
                        deleted_at = NULL
                    WHERE id = ?
                    """,
                    (normalized_share_path, workspace_id),
                )

            for idx, doc_type in enumerate(default_document_types):
                name = self._require_text(doc_type, "document_type")
                existing = conn.execute(
                    """
                    SELECT id
                    FROM document_types
                    WHERE workspace_id = ?
                    AND name = ?
                    """,
                    (workspace_id, name),
                ).fetchone()

                if existing is None:
                    conn.execute(
                        """
                        INSERT INTO document_types (
                            workspace_id,
                            name,
                            is_active,
                            sort_order,
                            deleted_at
                        )
                        VALUES (?, ?, 1, ?, NULL)
                        """,
                        (workspace_id, name, idx),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE document_types
                        SET
                            is_active = 1,
                            sort_order = ?,
                            deleted_at = NULL
                        WHERE id = ?
                        """,
                        (idx, int(existing["id"])),
                    )

        return workspace_id

    def search_files(self, workspace_id, date_prefix=None, document_type="전체", tags="", free_text=""):
        clauses = [
            "f.workspace_id = ?",
            "f.status = ?",
        ]
        params = [int(workspace_id), self.STATUS_ACTIVE]

        normalized_date_prefix = str(date_prefix or "").strip()
        if normalized_date_prefix:
            clauses.append("f.document_date LIKE ?")
            params.append(f"{normalized_date_prefix}%")

        normalized_document_type = str(document_type or "").strip()
        if normalized_document_type and normalized_document_type != "전체":
            clauses.append("dt.name = ?")
            params.append(normalized_document_type)

        normalized_tags = [
            token.strip()
            for token in str(tags or "").replace(";", ",").split(",")
            if token.strip()
        ]
        for token in normalized_tags:
            clauses.append(
                """
                EXISTS (
                    SELECT 1
                    FROM file_tags ft2
                    INNER JOIN tags t2
                        ON t2.id = ft2.tag_id
                    WHERE ft2.file_id = f.id
                    AND t2.name LIKE ? COLLATE NOCASE
                )
                """
            )
            params.append(f"%{token}%")

        normalized_free_text = str(free_text or "").strip()
        if normalized_free_text:
            clauses.append(
                """
                (
                    f.original_filename LIKE ? COLLATE NOCASE
                    OR f.archived_filename LIKE ? COLLATE NOCASE
                    OR f.uploaded_by LIKE ? COLLATE NOCASE
                    OR f.relative_path LIKE ? COLLATE NOCASE
                    OR EXISTS (
                        SELECT 1
                        FROM file_tags ft3
                        INNER JOIN tags t3
                            ON t3.id = ft3.tag_id
                        WHERE ft3.file_id = f.id
                        AND t3.name LIKE ? COLLATE NOCASE
                    )
                )
                """
            )
            free_like = f"%{normalized_free_text}%"
            params.extend([free_like, free_like, free_like, free_like, free_like])

        where_sql = " AND ".join(clauses)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    f.document_date AS archive_date,
                    dt.name AS document_type,
                    COALESCE(
                        GROUP_CONCAT(DISTINCT t.name),
                        ''
                    ) AS tags,
                    f.archived_filename,
                    f.uploaded_by,
                    COALESCE(f.file_size, 0) AS file_size,
                    w.share_path,
                    f.relative_path
                FROM files f
                INNER JOIN workspaces w
                    ON w.id = f.workspace_id
                INNER JOIN document_types dt
                    ON dt.id = f.document_type_id
                    AND dt.workspace_id = f.workspace_id
                LEFT JOIN file_tags ft
                    ON ft.file_id = f.id
                LEFT JOIN tags t
                    ON t.id = ft.tag_id
                WHERE {where_sql}
                GROUP BY f.id
                ORDER BY f.document_date DESC, f.archived_at DESC
                """,
                params,
            ).fetchall()

        results = []
        for row in rows:
            full_path = str(Path(row["share_path"]) / row["relative_path"])
            results.append(
                (
                    row["archive_date"],
                    row["document_type"],
                    row["tags"],
                    row["archived_filename"],
                    row["uploaded_by"],
                    int(row["file_size"] or 0),
                    full_path,
                )
            )

        return results

    def mark_files_deleted_by_paths(self, workspace_id, full_paths):
        normalized_paths = [
            str(Path(path))
            for path in (full_paths or [])
            if str(path or "").strip()
        ]
        if not normalized_paths:
            return 0

        workspace_id = int(workspace_id)
        with self._connect() as conn:
            workspace = conn.execute(
                """
                SELECT share_path
                FROM workspaces
                WHERE id = ?
                """,
                (workspace_id,),
            ).fetchone()

            if workspace is None:
                return 0

            share_path = Path(workspace["share_path"])
            relative_paths = []

            for value in normalized_paths:
                full_path = Path(value)
                relative = None
                try:
                    relative = full_path.relative_to(share_path)
                except ValueError:
                    full_text = str(full_path).replace("/", "\\").lower()
                    share_text = str(share_path).replace("/", "\\").rstrip("\\").lower()
                    prefix = f"{share_text}\\"
                    if full_text.startswith(prefix):
                        relative = Path(full_text[len(prefix):])

                if relative is not None:
                    relative_paths.append(str(relative).replace("/", "\\"))

            if not relative_paths:
                return 0

            placeholders = ",".join("?" for _ in relative_paths)
            cursor = conn.execute(
                f"""
                UPDATE files
                SET
                    status = ?,
                    deleted_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ?
                AND status IN (?, ?)
                AND relative_path IN ({placeholders})
                """,
                [
                    self.STATUS_DELETED,
                    workspace_id,
                    self.STATUS_ACTIVE,
                    self.STATUS_MISSING,
                    *relative_paths,
                ],
            )

            return int(cursor.rowcount or 0)

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