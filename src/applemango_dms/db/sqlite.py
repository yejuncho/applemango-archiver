import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
class ArchiveDatabase:
    STATUS_ACTIVE = 'active'
    STATUS_DELETED = 'deleted'
    STATUS_MISSING = 'missing'

    SEARCH_FIELD_ALL = 'all'
    SEARCH_FIELD_ORIGINAL_FILENAME = 'original_filename'
    SEARCH_FIELD_ARCHIVED_FILENAME = 'archived_filename'
    SEARCH_FIELD_DOCUMENT_DATE = 'document_date'
    SEARCH_FIELD_DOCUMENT_TYPE = 'document_type'
    SEARCH_FIELD_UPLOADED_BY = 'uploaded_by'
    SEARCH_FIELD_TAGS = 'tags'
    SEARCH_FIELD_FILE_EXT = 'file_ext'

    ALLOWED_SEARCH_FIELDS = {
        SEARCH_FIELD_ALL,
        SEARCH_FIELD_ORIGINAL_FILENAME,
        SEARCH_FIELD_ARCHIVED_FILENAME,
        SEARCH_FIELD_DOCUMENT_DATE,
        SEARCH_FIELD_DOCUMENT_TYPE,
        SEARCH_FIELD_UPLOADED_BY,
        SEARCH_FIELD_TAGS,
        SEARCH_FIELD_FILE_EXT,
    }

    TAG_MATCH_ALL = "all"
    TAG_MATCH_ANY = "any"

    ALLOWED_TAG_MATCH_MODES = {
        TAG_MATCH_ALL,
        TAG_MATCH_ANY,
    }

    def __init__(self, db_path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(
            self.db_path,
            timeout=10.0,
        )

        try:
            conn.row_factory = sqlite3.Row
            conn.execute(
                "PRAGMA foreign_keys = ON;"
            )
            conn.execute(
                "PRAGMA busy_timeout = 10000;"
            )

            with conn:
                yield conn

        finally:
            conn.close()

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

    @staticmethod
    def _file_row_to_dict(row):
        tags_text = str(row["tags_text"] or "").strip()

        tags = [
            name.strip()
            for name in tags_text.split(",")
            if name.strip()
        ]

        return {
            "file_id": int(row["file_id"]),
            "workspace_id": int(row["workspace_id"]),
            "document_type_id": int(
                row["document_type_id"]
            ),
            "document_type": row["document_type"],
            "document_date": row["document_date"],
            "original_filename": row[
                "original_filename"
            ],
            "archived_filename": row[
                "archived_filename"
            ],
            "relative_path": row["relative_path"],
            "full_path": str(
                Path(row["share_path"])
                / row["relative_path"]
            ),
            "uploaded_by": row["uploaded_by"],
            "tags": tags,
            "tags_text": tags_text,
            "file_ext": row["file_ext"],
            "mime_type": row["mime_type"],
            "file_size": (
                int(row["file_size"])
                if row["file_size"] is not None
                else None
            ),
            "source_created_at": row[
                "source_created_at"
            ],
            "source_modified_at": row[
                "source_modified_at"
            ],
            "archived_at": row["archived_at"],
            "status": row["status"],
            "deleted_at": row["deleted_at"],
            "relevance_score": int(
                row["relevance_score"] or 0
            ),
        }

    def search_files(
        self,
        workspace_id,
        *,
        search_text=None,
        search_field="all",
        filters=None,
        statuses=None,
        limit=200,
        offset=0,
    ):
        """
        Search file records within one workspace.

        Simple search:
            search_text is interpreted according to
            search_field.

        Detailed search:
            values in filters are combined with the simple
            search using AND.

        Defaults:
            active records only;
            all supplied tags must match;
            newest document dates first.

        Returns:
            A list of file dictionaries.
        """
        request = self._normalize_search_request(
            workspace_id,
            search_text=search_text,
            search_field=search_field,
            filters=filters,
            statuses=statuses,
            limit=limit,
            offset=offset,
        )

        normalized_workspace_id = request["workspace_id"]
        normalized_search_text = request["search_text"]
        normalized_search_field = request["search_field"]
        normalized_filters = request["filters"]
        normalized_statuses = request["statuses"]
        normalized_limit = request["limit"]
        normalized_offset = request["offset"]

        (
            relevance_sql,
            relevance_params,
        ) = self._build_relevance_sql(
            normalized_search_text,
            normalized_search_field,
        )

        status_placeholders = ",".join(
            "?" for _ in normalized_statuses
        )

        clauses = [
            "f.workspace_id = ?",
            f"f.status IN ({status_placeholders})",
        ]

        params = [
            normalized_workspace_id,
            *normalized_statuses,
        ]

        if normalized_search_text:
            escaped_text = self._escape_like(
                normalized_search_text
            )
            contains_value = f"%{escaped_text}%"

            if (
                normalized_search_field
                == self.SEARCH_FIELD_ALL
            ):
                clauses.append(
                    """
                    (
                        f.original_filename
                            LIKE ? ESCAPE '\\'
                            COLLATE NOCASE

                        OR f.archived_filename
                            LIKE ? ESCAPE '\\'
                            COLLATE NOCASE

                        OR f.document_date
                            LIKE ? ESCAPE '\\'
                            COLLATE NOCASE

                        OR dt.name
                            LIKE ? ESCAPE '\\'
                            COLLATE NOCASE

                        OR f.uploaded_by
                            LIKE ? ESCAPE '\\'
                            COLLATE NOCASE

                        OR f.file_ext
                            LIKE ? ESCAPE '\\'
                            COLLATE NOCASE

                        OR EXISTS (
                            SELECT 1
                            FROM file_tags simple_ft
                            INNER JOIN tags simple_t
                                ON simple_t.id =
                                    simple_ft.tag_id
                            WHERE simple_ft.file_id = f.id
                              AND simple_t.workspace_id =
                                  f.workspace_id
                              AND simple_t.name
                                  LIKE ? ESCAPE '\\'
                                  COLLATE NOCASE
                        )
                    )
                    """
                )
                params.extend(
                    [
                        contains_value,
                        contains_value,
                        contains_value,
                        contains_value,
                        contains_value,
                        contains_value,
                        contains_value,
                    ]
                )

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_ORIGINAL_FILENAME
            ):
                clauses.append(
                    """
                    f.original_filename
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    """
                )
                params.append(contains_value)

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_ARCHIVED_FILENAME
            ):
                clauses.append(
                    """
                    f.archived_filename
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    """
                )
                params.append(contains_value)

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_DOCUMENT_DATE
            ):
                clauses.append(
                    """
                    f.document_date
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    """
                )
                params.append(f"{escaped_text}%")

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_DOCUMENT_TYPE
            ):
                clauses.append(
                    """
                    dt.name
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    """
                )
                params.append(contains_value)

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_UPLOADED_BY
            ):
                clauses.append(
                    """
                    f.uploaded_by
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    """
                )
                params.append(contains_value)

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_TAGS
            ):
                clauses.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM file_tags simple_ft
                        INNER JOIN tags simple_t
                            ON simple_t.id =
                                simple_ft.tag_id
                        WHERE simple_ft.file_id = f.id
                          AND simple_t.workspace_id =
                              f.workspace_id
                          AND simple_t.name
                              LIKE ? ESCAPE '\\'
                              COLLATE NOCASE
                    )
                    """
                )
                params.append(contains_value)

            elif (
                normalized_search_field
                == self.SEARCH_FIELD_FILE_EXT
            ):
                normalized_search_ext = (
                    self._normalize_file_ext(
                        normalized_search_text
                    )
                )
                clauses.append(
                    "f.file_ext = ? COLLATE NOCASE"
                )
                params.append(normalized_search_ext)

        document_date_from = normalized_filters[
            "document_date_from"
        ]
        if document_date_from:
            clauses.append("f.document_date >= ?")
            params.append(document_date_from)

        document_date_to = normalized_filters[
            "document_date_to"
        ]
        if document_date_to:
            clauses.append("f.document_date <= ?")
            params.append(document_date_to)

        document_type_id = normalized_filters[
            "document_type_id"
        ]
        if document_type_id is not None:
            clauses.append("f.document_type_id = ?")
            params.append(document_type_id)

        uploaded_by = normalized_filters[
            "uploaded_by"
        ]
        if uploaded_by:
            clauses.append(
                "f.uploaded_by = ? COLLATE NOCASE"
            )
            params.append(uploaded_by)

        file_ext = normalized_filters["file_ext"]
        if file_ext:
            clauses.append(
                "f.file_ext = ? COLLATE NOCASE"
            )
            params.append(file_ext)

        file_size_min = normalized_filters[
            "file_size_min"
        ]
        if file_size_min is not None:
            clauses.append("f.file_size >= ?")
            params.append(file_size_min)

        file_size_max = normalized_filters[
            "file_size_max"
        ]
        if file_size_max is not None:
            clauses.append("f.file_size <= ?")
            params.append(file_size_max)

        archived_at_from = normalized_filters[
            "archived_at_from"
        ]
        if archived_at_from:
            clauses.append("f.archived_at >= ?")
            params.append(archived_at_from)

        archived_at_to = normalized_filters[
            "archived_at_to"
        ]
        if archived_at_to:
            clauses.append(
                """
                f.archived_at < datetime(?, '+1 day')
                """
            )
            params.append(archived_at_to)

        tag_names = normalized_filters["tag_names"]
        tag_match = normalized_filters["tag_match"]

        if tag_names and tag_match == self.TAG_MATCH_ALL:
            for tag_name in tag_names:
                clauses.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM file_tags filter_ft
                        INNER JOIN tags filter_t
                            ON filter_t.id =
                                filter_ft.tag_id
                        WHERE filter_ft.file_id = f.id
                          AND filter_t.workspace_id =
                              f.workspace_id
                          AND filter_t.name = ?
                              COLLATE NOCASE
                    )
                    """
                )
                params.append(tag_name)

        elif tag_names and tag_match == self.TAG_MATCH_ANY:
            tag_conditions = " OR ".join(
                "filter_t.name = ? COLLATE NOCASE"
                for _ in tag_names
            )

            clauses.append(
                f"""
                EXISTS (
                    SELECT 1
                    FROM file_tags filter_ft
                    INNER JOIN tags filter_t
                        ON filter_t.id =
                            filter_ft.tag_id
                    WHERE filter_ft.file_id = f.id
                      AND filter_t.workspace_id =
                          f.workspace_id
                      AND (
                          {tag_conditions}
                      )
                )
                """
            )
            params.extend(tag_names)

        where_sql = "\nAND ".join(clauses)

        query_params = [
            *relevance_params,
            *params,
            normalized_limit,
            normalized_offset,
        ]

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                    f.id AS file_id,
                    f.workspace_id,
                    f.document_type_id,
                    dt.name AS document_type,
                    f.document_date,
                    f.original_filename,
                    f.archived_filename,
                    f.relative_path,
                    f.uploaded_by,
                    f.file_ext,
                    f.mime_type,
                    f.file_size,
                    f.source_created_at,
                    f.source_modified_at,
                    f.archived_at,
                    f.status,
                    f.deleted_at,
                    w.share_path,

                    COALESCE(
                        (
                            SELECT GROUP_CONCAT(
                                ordered_tags.name,
                                ', '
                            )
                            FROM (
                                SELECT result_t.name
                                FROM file_tags result_ft
                                INNER JOIN tags result_t
                                    ON result_t.id =
                                        result_ft.tag_id
                                WHERE result_ft.file_id = f.id
                                  AND result_t.workspace_id =
                                      f.workspace_id
                                ORDER BY
                                    result_t.name
                                    COLLATE NOCASE
                            ) AS ordered_tags
                        ),
                        ''
                    ) AS tags_text,

                    ({relevance_sql})
                        AS relevance_score

                FROM files f

                INNER JOIN workspaces w
                    ON w.id = f.workspace_id

                INNER JOIN document_types dt
                    ON dt.id = f.document_type_id
                   AND dt.workspace_id = f.workspace_id

                WHERE {where_sql}

                ORDER BY
                    relevance_score DESC,
                    f.document_date DESC,
                    f.archived_at DESC,
                    f.id DESC

                LIMIT ?
                OFFSET ?
                """,
                query_params,
            ).fetchall()

        return [
            self._file_row_to_dict(row)
            for row in rows
        ]

    def get_file_by_id(
        self,
        workspace_id,
        file_id,
        *,
        statuses=None,
    ):
        """
        Retrieve one file record by ID within one workspace.

        By default, only an active record is returned. Supply
        statuses explicitly when deleted or missing records are
        permitted.

        Returns:
            A file dictionary, or None when no matching record
            exists.
        """
        normalized_workspace_id = (
            self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            )
        )
        normalized_file_id = self._normalize_positive_int(
            file_id,
            "file_id",
        )
        normalized_statuses = self._normalize_statuses(
            statuses
        )

        status_placeholders = ",".join(
            "?" for _ in normalized_statuses
        )

        params = [
            normalized_workspace_id,
            normalized_file_id,
            *normalized_statuses,
        ]

        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT
                    f.id AS file_id,
                    f.workspace_id,
                    f.document_type_id,
                    dt.name AS document_type,
                    f.document_date,
                    f.original_filename,
                    f.archived_filename,
                    f.relative_path,
                    f.uploaded_by,
                    f.file_ext,
                    f.mime_type,
                    f.file_size,
                    f.source_created_at,
                    f.source_modified_at,
                    f.archived_at,
                    f.status,
                    f.deleted_at,
                    w.share_path,

                    COALESCE(
                        (
                            SELECT GROUP_CONCAT(
                                ordered_tags.name,
                                ', '
                            )
                            FROM (
                                SELECT result_t.name
                                FROM file_tags result_ft
                                INNER JOIN tags result_t
                                    ON result_t.id =
                                        result_ft.tag_id
                                WHERE result_ft.file_id = f.id
                                  AND result_t.workspace_id =
                                      f.workspace_id
                                ORDER BY
                                    result_t.name
                                    COLLATE NOCASE
                            ) AS ordered_tags
                        ),
                        ''
                    ) AS tags_text,

                    0 AS relevance_score

                FROM files f

                INNER JOIN workspaces w
                    ON w.id = f.workspace_id

                INNER JOIN document_types dt
                    ON dt.id = f.document_type_id
                   AND dt.workspace_id = f.workspace_id

                WHERE f.workspace_id = ?
                  AND f.id = ?
                  AND f.status IN (
                      {status_placeholders}
                  )

                LIMIT 1
                """,
                params,
            ).fetchone()

        if row is None:
            return None

        return self._file_row_to_dict(row)

    def mark_file_missing(
        self,
        workspace_id,
        file_id,
    ):
        """
        Change one active file record to missing.

        Returns:
            The refreshed missing-file dictionary, or None when
            the record was not active.
        """
        normalized_workspace_id = (
            self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            )
        )
        normalized_file_id = self._normalize_positive_int(
            file_id,
            "file_id",
        )

        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE files
                SET status = ?
                WHERE workspace_id = ?
                  AND id = ?
                  AND status = ?
                """,
                (
                    self.STATUS_MISSING,
                    normalized_workspace_id,
                    normalized_file_id,
                    self.STATUS_ACTIVE,
                ),
            )

            changed = cursor.rowcount == 1

        if not changed:
            return None

        return self.get_file_by_id(
            normalized_workspace_id,
            normalized_file_id,
            statuses=[self.STATUS_MISSING],
        )

    def mark_file_deleted(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
    ):
        """
        Mark one active file deleted after verifying ownership.

        This method changes database state only. Filesystem
        movement must be handled by FileOperationsService.

        Returns:
            The refreshed deleted-file dictionary.
        """
        normalized_workspace_id = (
            self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            )
        )
        normalized_file_id = self._normalize_positive_int(
            file_id,
            "file_id",
        )
        normalized_acting_user = self._require_text(
            acting_user,
            "acting_user",
        )

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    uploaded_by,
                    status
                FROM files
                WHERE workspace_id = ?
                  AND id = ?
                """,
                (
                    normalized_workspace_id,
                    normalized_file_id,
                ),
            ).fetchone()

            if row is None:
                raise LookupError(
                    "File not found in workspace."
                )

            if row["status"] != self.STATUS_ACTIVE:
                raise LookupError(
                    "Only an active file can be deleted."
                )

            stored_uploader = str(
                row["uploaded_by"] or ""
            ).strip()

            if (
                stored_uploader.casefold()
                != normalized_acting_user.casefold()
            ):
                raise PermissionError(
                    "Only the original uploader may delete "
                    "this file."
                )

            cursor = conn.execute(
                """
                UPDATE files
                SET
                    status = ?,
                    deleted_at = CURRENT_TIMESTAMP
                WHERE workspace_id = ?
                  AND id = ?
                  AND status = ?
                """,
                (
                    self.STATUS_DELETED,
                    normalized_workspace_id,
                    normalized_file_id,
                    self.STATUS_ACTIVE,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "File status changed before deletion "
                    "could be completed."
                )

        deleted_record = self.get_file_by_id(
            normalized_workspace_id,
            normalized_file_id,
            statuses=[self.STATUS_DELETED],
        )

        if deleted_record is None:
            raise RuntimeError(
                "Deleted file record could not be retrieved."
            )

        return deleted_record

    def restore_file_record(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
    ):
        """
        Restore one deleted database record to active after
        verifying ownership.

        Filesystem restoration must be completed first by
        FileOperationsService.

        Returns:
            The refreshed active-file dictionary.
        """
        normalized_workspace_id = (
            self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            )
        )
        normalized_file_id = self._normalize_positive_int(
            file_id,
            "file_id",
        )
        normalized_acting_user = self._require_text(
            acting_user,
            "acting_user",
        )

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    uploaded_by,
                    status
                FROM files
                WHERE workspace_id = ?
                  AND id = ?
                """,
                (
                    normalized_workspace_id,
                    normalized_file_id,
                ),
            ).fetchone()

            if row is None:
                raise LookupError(
                    "File not found in workspace."
                )

            if row["status"] != self.STATUS_DELETED:
                raise LookupError(
                    "Only a deleted file can be restored."
                )

            stored_uploader = str(
                row["uploaded_by"] or ""
            ).strip()

            if (
                stored_uploader.casefold()
                != normalized_acting_user.casefold()
            ):
                raise PermissionError(
                    "Only the original uploader may restore "
                    "this file."
                )

            cursor = conn.execute(
                """
                UPDATE files
                SET
                    status = ?,
                    deleted_at = NULL
                WHERE workspace_id = ?
                  AND id = ?
                  AND status = ?
                """,
                (
                    self.STATUS_ACTIVE,
                    normalized_workspace_id,
                    normalized_file_id,
                    self.STATUS_DELETED,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "File status changed before restoration "
                    "could be completed."
                )

        restored_record = self.get_file_by_id(
            normalized_workspace_id,
            normalized_file_id,
        )

        if restored_record is None:
            raise RuntimeError(
                "Restored file record could not be retrieved."
            )

        return restored_record

    def rename_file_record(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
        archived_filename,
        relative_path,
    ):
        """
        Update filename and path metadata after the physical NAS
        file has been renamed.

        Filesystem renaming must be handled first by
        FileOperationsService.
        """
        normalized_workspace_id = (
            self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            )
        )
        normalized_file_id = self._normalize_positive_int(
            file_id,
            "file_id",
        )
        normalized_acting_user = self._require_text(
            acting_user,
            "acting_user",
        )
        normalized_archived_filename = self._require_text(
            archived_filename,
            "archived_filename",
        )
        normalized_relative_path = self._require_text(
            relative_path,
            "relative_path",
        )

        if (
            "/" in normalized_archived_filename
            or "\\" in normalized_archived_filename
            or Path(normalized_archived_filename).name
                != normalized_archived_filename
        ):
            raise ValueError(
                "archived_filename must contain a filename "
                "only."
            )

        relative = Path(normalized_relative_path)

        if (
            relative.is_absolute()
            or relative.anchor
            or relative.drive
            or relative.root
            or ".." in relative.parts
        ):
            raise ValueError(
                "relative_path must remain inside the "
                "workspace."
            )

        if relative.name != normalized_archived_filename:
            raise ValueError(
                "relative_path must end with "
                "archived_filename."
            )

        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    uploaded_by,
                    status
                FROM files
                WHERE workspace_id = ?
                  AND id = ?
                """,
                (
                    normalized_workspace_id,
                    normalized_file_id,
                ),
            ).fetchone()

            if row is None:
                raise LookupError(
                    "File not found in workspace."
                )

            if row["status"] != self.STATUS_ACTIVE:
                raise LookupError(
                    "Only an active file can be renamed."
                )

            stored_uploader = str(
                row["uploaded_by"] or ""
            ).strip()

            if (
                stored_uploader.casefold()
                != normalized_acting_user.casefold()
            ):
                raise PermissionError(
                    "Only the original uploader may rename "
                    "this file."
                )

            collision = conn.execute(
                """
                SELECT id
                FROM files
                WHERE workspace_id = ?
                  AND id != ?
                  AND (
                      archived_filename = ?
                      OR relative_path = ?
                  )
                LIMIT 1
                """,
                (
                    normalized_workspace_id,
                    normalized_file_id,
                    normalized_archived_filename,
                    normalized_relative_path,
                ),
            ).fetchone()

            if collision is not None:
                raise FileExistsError(
                    "Another database record already uses "
                    "the requested filename or path."
                )

            cursor = conn.execute(
                """
                UPDATE files
                SET
                    archived_filename = ?,
                    relative_path = ?
                WHERE workspace_id = ?
                  AND id = ?
                  AND status = ?
                """,
                (
                    normalized_archived_filename,
                    normalized_relative_path,
                    normalized_workspace_id,
                    normalized_file_id,
                    self.STATUS_ACTIVE,
                ),
            )

            if cursor.rowcount != 1:
                raise RuntimeError(
                    "File status changed before renaming "
                    "could be completed."
                )

        renamed_record = self.get_file_by_id(
            normalized_workspace_id,
            normalized_file_id,
        )

        if renamed_record is None:
            raise RuntimeError(
                "Renamed file record could not be retrieved."
            )

        return renamed_record

    def update_file_metadata(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
        document_date=None,
        document_type_id=None,
        tag_names=None,
    ):
        """
        Update editable metadata for one active file.

        Permission is granted only when acting_user matches the
        file's uploaded_by value using a case-insensitive exact
        comparison.

        Passing None means that field is unchanged. For tags,
        passing an empty list removes all tags.

        Returns:
            The refreshed file dictionary.

        Raises:
            LookupError:
                The active file or document type does not exist.

            PermissionError:
                acting_user is not the original uploader.

            ValueError:
                No updates were supplied or an input is invalid.
        """
        normalized_workspace_id = (
            self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            )
        )
        normalized_file_id = self._normalize_positive_int(
            file_id,
            "file_id",
        )
        normalized_acting_user = self._require_text(
            acting_user,
            "acting_user",
        )

        change_document_date = document_date is not None
        change_document_type = document_type_id is not None
        change_tags = tag_names is not None

        if not any(
            (
                change_document_date,
                change_document_type,
                change_tags,
            )
        ):
            raise ValueError(
                "At least one metadata change is required."
            )

        normalized_document_date = None
        if change_document_date:
            normalized_document_date = (
                self._normalize_optional_iso_date(
                    document_date,
                    "document_date",
                )
            )

            if normalized_document_date is None:
                raise ValueError(
                    "document_date cannot be empty."
                )

        normalized_document_type_id = None
        if change_document_type:
            normalized_document_type_id = (
                self._normalize_positive_int(
                    document_type_id,
                    "document_type_id",
                )
            )

        normalized_tag_names = None
        if change_tags:
            normalized_tag_names = (
                self._normalize_tag_names(tag_names)
            )

        with self._connect() as conn:
            file_row = conn.execute(
                """
                SELECT
                    id,
                    uploaded_by
                FROM files
                WHERE workspace_id = ?
                  AND id = ?
                  AND status = ?
                """,
                (
                    normalized_workspace_id,
                    normalized_file_id,
                    self.STATUS_ACTIVE,
                ),
            ).fetchone()

            if file_row is None:
                raise LookupError(
                    "Active file not found in workspace."
                )

            stored_uploader = str(
                file_row["uploaded_by"] or ""
            ).strip()

            if (
                stored_uploader.casefold()
                != normalized_acting_user.casefold()
            ):
                raise PermissionError(
                    "Only the original uploader may edit "
                    "this file's metadata."
                )

            if change_document_type:
                document_type_row = conn.execute(
                    """
                    SELECT id
                    FROM document_types
                    WHERE workspace_id = ?
                      AND id = ?
                      AND is_active = 1
                      AND deleted_at IS NULL
                    """,
                    (
                        normalized_workspace_id,
                        normalized_document_type_id,
                    ),
                ).fetchone()

                if document_type_row is None:
                    raise LookupError(
                        "Active document type not found "
                        "in workspace."
                    )

            update_fields = []
            update_params = []

            if change_document_date:
                update_fields.append(
                    "document_date = ?"
                )
                update_params.append(
                    normalized_document_date
                )

            if change_document_type:
                update_fields.append(
                    "document_type_id = ?"
                )
                update_params.append(
                    normalized_document_type_id
                )

            if update_fields:
                update_params.extend(
                    [
                        normalized_workspace_id,
                        normalized_file_id,
                        self.STATUS_ACTIVE,
                    ]
                )

                cursor = conn.execute(
                    f"""
                    UPDATE files
                    SET {", ".join(update_fields)}
                    WHERE workspace_id = ?
                      AND id = ?
                      AND status = ?
                    """,
                    update_params,
                )

                if cursor.rowcount != 1:
                    raise RuntimeError(
                        "File metadata update did not affect "
                        "exactly one record."
                    )

            if change_tags:
                conn.execute(
                    """
                    DELETE FROM file_tags
                    WHERE file_id = ?
                    """,
                    (normalized_file_id,),
                )

                self._assign_tags_with_conn(
                    conn,
                    normalized_workspace_id,
                    normalized_file_id,
                    normalized_tag_names,
                    verify_file_exists=False,
                )

        refreshed = self.get_file_by_id(
            normalized_workspace_id,
            normalized_file_id,
        )

        if refreshed is None:
            raise RuntimeError(
                "Updated file could not be retrieved."
            )

        return refreshed

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

    @staticmethod
    def _normalize_optional_text(value):
        normalized = str(value or "").strip()
        return normalized or None

    @staticmethod
    def _normalize_positive_int(value, field_name):
        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be an integer."
            ) from exc

        if normalized <= 0:
            raise ValueError(
                f"{field_name} must be greater than zero."
            )

        return normalized

    @classmethod
    def _normalize_optional_positive_int(
        cls,
        value,
        field_name,
    ):
        if value is None or str(value).strip() == "":
            return None

        return cls._normalize_positive_int(
            value,
            field_name,
        )

    @staticmethod
    def _normalize_optional_nonnegative_int(
        value,
        field_name,
    ):
        if value is None or str(value).strip() == "":
            return None

        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"{field_name} must be an integer."
            ) from exc

        if normalized < 0:
            raise ValueError(
                f"{field_name} cannot be negative."
            )

        return normalized

    @staticmethod
    def _normalize_file_ext(value):
        file_ext = str(value or "").strip().lower()

        if file_ext and not file_ext.startswith("."):
            file_ext = f".{file_ext}"

        return file_ext

    @staticmethod
    def _escape_like(value):
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace("%", "\\%")
            .replace("_", "\\_")
        )

    def _build_relevance_sql(
        self,
        search_text,
        search_field,
    ):
        if not search_text:
            return "0", []

        escaped_text = self._escape_like(search_text)
        starts_value = f"{escaped_text}%"
        contains_value = f"%{escaped_text}%"

        if search_field == self.SEARCH_FIELD_ALL:
            return (
                """
                CASE
                    WHEN f.original_filename = ?
                        COLLATE NOCASE
                    THEN 100

                    WHEN f.archived_filename = ?
                        COLLATE NOCASE
                    THEN 95

                    WHEN f.original_filename
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 85

                    WHEN f.archived_filename
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 80

                    WHEN EXISTS (
                        SELECT 1
                        FROM file_tags score_ft
                        INNER JOIN tags score_t
                            ON score_t.id = score_ft.tag_id
                        WHERE score_ft.file_id = f.id
                          AND score_t.workspace_id =
                              f.workspace_id
                          AND score_t.name = ?
                              COLLATE NOCASE
                    )
                    THEN 75

                    WHEN dt.name = ? COLLATE NOCASE
                    THEN 70

                    WHEN f.original_filename
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 60

                    WHEN f.archived_filename
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 58

                    WHEN f.uploaded_by = ?
                        COLLATE NOCASE
                    THEN 55

                    WHEN EXISTS (
                        SELECT 1
                        FROM file_tags score_ft
                        INNER JOIN tags score_t
                            ON score_t.id = score_ft.tag_id
                        WHERE score_ft.file_id = f.id
                          AND score_t.workspace_id =
                              f.workspace_id
                          AND score_t.name
                              LIKE ? ESCAPE '\\'
                              COLLATE NOCASE
                    )
                    THEN 50

                    WHEN f.document_date = ?
                    THEN 45

                    WHEN f.document_date
                        LIKE ? ESCAPE '\\'
                    THEN 40

                    WHEN f.file_ext = ?
                        COLLATE NOCASE
                    THEN 35

                    WHEN dt.name
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 30

                    WHEN f.uploaded_by
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 25

                    ELSE 1
                END
                """,
                [
                    search_text,
                    search_text,
                    starts_value,
                    starts_value,
                    search_text,
                    search_text,
                    contains_value,
                    contains_value,
                    search_text,
                    contains_value,
                    search_text,
                    starts_value,
                    self._normalize_file_ext(search_text),
                    contains_value,
                    contains_value,
                ],
            )

        if search_field in {
            self.SEARCH_FIELD_ORIGINAL_FILENAME,
            self.SEARCH_FIELD_ARCHIVED_FILENAME,
        }:
            column = {
                self.SEARCH_FIELD_ORIGINAL_FILENAME:
                    "f.original_filename",
                self.SEARCH_FIELD_ARCHIVED_FILENAME:
                    "f.archived_filename",
            }[search_field]

            return (
                f"""
                CASE
                    WHEN {column} = ? COLLATE NOCASE
                    THEN 100

                    WHEN {column}
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 80

                    WHEN {column}
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 60

                    ELSE 1
                END
                """,
                [
                    search_text,
                    starts_value,
                    contains_value,
                ],
            )

        if search_field == self.SEARCH_FIELD_DOCUMENT_DATE:
            return (
                """
                CASE
                    WHEN f.document_date = ?
                    THEN 100

                    WHEN f.document_date
                        LIKE ? ESCAPE '\\'
                    THEN 70

                    ELSE 1
                END
                """,
                [
                    search_text,
                    starts_value,
                ],
            )

        if search_field == self.SEARCH_FIELD_DOCUMENT_TYPE:
            return (
                """
                CASE
                    WHEN dt.name = ? COLLATE NOCASE
                    THEN 100

                    WHEN dt.name
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 70

                    ELSE 1
                END
                """,
                [
                    search_text,
                    contains_value,
                ],
            )

        if search_field == self.SEARCH_FIELD_UPLOADED_BY:
            return (
                """
                CASE
                    WHEN f.uploaded_by = ?
                        COLLATE NOCASE
                    THEN 100

                    WHEN f.uploaded_by
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 80

                    WHEN f.uploaded_by
                        LIKE ? ESCAPE '\\'
                        COLLATE NOCASE
                    THEN 60

                    ELSE 1
                END
                """,
                [
                    search_text,
                    starts_value,
                    contains_value,
                ],
            )

        if search_field == self.SEARCH_FIELD_TAGS:
            return (
                """
                CASE
                    WHEN EXISTS (
                        SELECT 1
                        FROM file_tags score_ft
                        INNER JOIN tags score_t
                            ON score_t.id = score_ft.tag_id
                        WHERE score_ft.file_id = f.id
                          AND score_t.workspace_id =
                              f.workspace_id
                          AND score_t.name = ?
                              COLLATE NOCASE
                    )
                    THEN 100

                    WHEN EXISTS (
                        SELECT 1
                        FROM file_tags score_ft
                        INNER JOIN tags score_t
                            ON score_t.id = score_ft.tag_id
                        WHERE score_ft.file_id = f.id
                          AND score_t.workspace_id =
                              f.workspace_id
                          AND score_t.name
                              LIKE ? ESCAPE '\\'
                              COLLATE NOCASE
                    )
                    THEN 70

                    ELSE 1
                END
                """,
                [
                    search_text,
                    contains_value,
                ],
            )

        if search_field == self.SEARCH_FIELD_FILE_EXT:
            return (
                """
                CASE
                    WHEN f.file_ext = ?
                        COLLATE NOCASE
                    THEN 100

                    ELSE 1
                END
                """,
                [
                    self._normalize_file_ext(search_text),
                ],
            )

        return "0", []

    @classmethod
    def _normalize_search_field(cls, value):
        normalized = str(value or cls.SEARCH_FIELD_ALL).strip().lower()

        if normalized not in cls.ALLOWED_SEARCH_FIELDS:
            raise ValueError(
                f"Unsupported search field: {normalized}"
            )

        return normalized

    def _normalize_statuses(self, statuses):
        if statuses is None:
            return [self.STATUS_ACTIVE]

        if isinstance(statuses, str):
            statuses = [statuses]

        allowed_statuses = {
            self.STATUS_ACTIVE,
            self.STATUS_DELETED,
            self.STATUS_MISSING,
        }

        try:
            values = iter(statuses)
        except TypeError as exc:
            raise ValueError(
                "statuses must be a status string or an iterable "
                "of status strings."
            ) from exc

        normalized = []
        seen = set()

        for value in values:
            status = str(value or "").strip().lower()

            if not status:
                continue

            if status not in allowed_statuses:
                raise ValueError(
                    f"Unsupported file status: {status}"
                )

            if status not in seen:
                normalized.append(status)
                seen.add(status)

        return normalized or [self.STATUS_ACTIVE]

    @staticmethod
    def _normalize_optional_iso_date(value, field_name):
        normalized = str(value or "").strip()

        if not normalized:
            return None

        try:
            parsed = datetime.strptime(
                normalized,
                "%Y-%m-%d",
            )
        except ValueError as exc:
            raise ValueError(
                f"{field_name} must use YYYY-MM-DD format."
            ) from exc

        return parsed.strftime("%Y-%m-%d")

    @classmethod
    def _normalize_date_range(
        cls,
        date_from,
        date_to,
        *,
        from_field,
        to_field,
    ):
        normalized_from = cls._normalize_optional_iso_date(
            date_from,
            from_field,
        )
        normalized_to = cls._normalize_optional_iso_date(
            date_to,
            to_field,
        )

        if (
            normalized_from is not None
            and normalized_to is not None
            and normalized_from > normalized_to
        ):
            raise ValueError(
                f"{from_field} cannot be later than {to_field}."
            )

        return normalized_from, normalized_to

    @classmethod
    def _normalize_numeric_range(
        cls,
        minimum,
        maximum,
        *,
        minimum_field,
        maximum_field,
    ):
        normalized_minimum = (
            cls._normalize_optional_nonnegative_int(
                minimum,
                minimum_field,
            )
        )
        normalized_maximum = (
            cls._normalize_optional_nonnegative_int(
                maximum,
                maximum_field,
            )
        )

        if (
            normalized_minimum is not None
            and normalized_maximum is not None
            and normalized_minimum > normalized_maximum
        ):
            raise ValueError(
                f"{minimum_field} cannot be greater than "
                f"{maximum_field}."
            )

        return normalized_minimum, normalized_maximum

    @classmethod
    def _normalize_tag_match_mode(cls, value):
        normalized = str(
            value or cls.TAG_MATCH_ALL
        ).strip().lower()

        if normalized not in cls.ALLOWED_TAG_MATCH_MODES:
            raise ValueError(
                f"Unsupported tag match mode: {normalized}"
            )

        return normalized

    @staticmethod
    def _normalize_tag_names(tag_names):
        if tag_names is None:
            return []

        if isinstance(tag_names, str):
            tag_names = (
                tag_names
                .replace(";", ",")
                .split(",")
            )

        normalized = []
        seen = set()

        for value in tag_names:
            name = str(value or "").strip()
            key = name.casefold()

            if name and key not in seen:
                normalized.append(name)
                seen.add(key)

        return normalized

    @staticmethod
    def _normalize_search_limit(
        value,
        default=200,
        maximum=1000,
    ):
        if value is None:
            return default

        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "limit must be a positive integer."
            ) from exc

        if normalized <= 0:
            raise ValueError(
                "limit must be a positive integer."
            )

        return min(normalized, maximum)

    @staticmethod
    def _normalize_search_offset(value):
        if value is None:
            return 0

        try:
            normalized = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "offset must be a non-negative integer."
            ) from exc

        if normalized < 0:
            raise ValueError(
                "offset must be a non-negative integer."
            )

        return normalized

    def _normalize_search_filters(self, filters):
        if filters is None:
            filters = {}

        if not isinstance(filters, dict):
            raise TypeError(
                "filters must be a dictionary or None."
            )

        allowed_keys = {
            "document_date_from",
            "document_date_to",
            "document_type_id",
            "tag_names",
            "tag_match",
            "uploaded_by",
            "file_ext",
            "file_size_min",
            "file_size_max",
            "archived_at_from",
            "archived_at_to",
        }

        unknown_keys = set(filters) - allowed_keys

        if unknown_keys:
            names = ", ".join(sorted(unknown_keys))
            raise ValueError(
                f"Unsupported search filter keys: {names}"
            )

        (
            document_date_from,
            document_date_to,
        ) = self._normalize_date_range(
            filters.get("document_date_from"),
            filters.get("document_date_to"),
            from_field="document_date_from",
            to_field="document_date_to",
        )

        (
            archived_at_from,
            archived_at_to,
        ) = self._normalize_date_range(
            filters.get("archived_at_from"),
            filters.get("archived_at_to"),
            from_field="archived_at_from",
            to_field="archived_at_to",
        )

        (
            file_size_min,
            file_size_max,
        ) = self._normalize_numeric_range(
            filters.get("file_size_min"),
            filters.get("file_size_max"),
            minimum_field="file_size_min",
            maximum_field="file_size_max",
        )

        return {
            "document_date_from": document_date_from,
            "document_date_to": document_date_to,
            "document_type_id": (
                self._normalize_optional_positive_int(
                    filters.get("document_type_id"),
                    "document_type_id",
                )
            ),
            "tag_names": self._normalize_tag_names(
                filters.get("tag_names")
            ),
            "tag_match": self._normalize_tag_match_mode(
                filters.get("tag_match")
            ),
            "uploaded_by": self._normalize_optional_text(
                filters.get("uploaded_by")
            ),
            "file_ext": (
                self._normalize_file_ext(
                    filters.get("file_ext")
                )
                or None
            ),
            "file_size_min": file_size_min,
            "file_size_max": file_size_max,
            "archived_at_from": archived_at_from,
            "archived_at_to": archived_at_to,
        }

    def _normalize_search_request(
        self,
        workspace_id,
        *,
        search_text=None,
        search_field=None,
        filters=None,
        statuses=None,
        limit=200,
        offset=0,
    ):
        return {
            "workspace_id": self._normalize_positive_int(
                workspace_id,
                "workspace_id",
            ),
            "search_text": self._normalize_optional_text(
                search_text
            ),
            "search_field": self._normalize_search_field(
                search_field
            ),
            "filters": self._normalize_search_filters(
                filters
            ),
            "statuses": self._normalize_statuses(
                statuses
            ),
            "limit": self._normalize_search_limit(
                limit
            ),
            "offset": self._normalize_search_offset(
                offset
            ),
        }

    def _insert_file_record_with_conn(self, conn, record):
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
                self._normalize_file_ext(record.get("file_ext")),
                record.get("mime_type"),
                record.get("file_size"),
                record.get("checksum"),
            ),
        )

        return int(cursor.lastrowid)

    def _assign_tags_with_conn(
        self,
        conn,
        workspace_id,
        file_id,
        normalized_names,
        verify_file_exists=True,
    ):
        workspace_id = int(workspace_id)
        file_id = int(file_id)

        if verify_file_exists:
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

    def assign_tags(self, workspace_id, file_id, tag_names):
        normalized_names = self._normalize_tag_names(tag_names)

        with self._connect() as conn:
            self._assign_tags_with_conn(
                conn,
                workspace_id,
                file_id,
                normalized_names,
                verify_file_exists=True,
            )

    def create_file_with_tags(self, record, tag_names):
        normalized_names = self._normalize_tag_names(tag_names)

        with self._connect() as conn:
            file_id = self._insert_file_record_with_conn(conn, record)
            self._assign_tags_with_conn(
                conn,
                record["workspace_id"],
                file_id,
                normalized_names,
                verify_file_exists=False,
            )

        return file_id

    def insert_file_record(self, record):
        with self._connect() as conn:
            return self._insert_file_record_with_conn(conn, record)

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