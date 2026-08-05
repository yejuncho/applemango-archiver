from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

ProgressCallback = Callable[[dict], None]


class WorkspaceReconciliationService:
    """
    Workspace inventory and database reconciliation service.

    Scanning is read-only. Database writes occur only through the
    explicit apply methods.
    """

    WORKFLOW_PREVIEW = "preview"
    WORKFLOW_APPLIED = "applied"
    WORKFLOW_COMPLETED_WITH_ERRORS = (
        "completed_with_errors"
    )

    def __init__(self, database):
        if database is None:
            raise ValueError("database is required.")

        required_methods = (
            "get_workspace_file_index",
            "insert_discovered_file_record",
        )

        missing_methods = [
            method_name
            for method_name in required_methods
            if not callable(
                getattr(
                    database,
                    method_name,
                    None,
                )
            )
        ]

        if missing_methods:
            missing_text = ", ".join(
                f"{name}()"
                for name in missing_methods
            )

            raise TypeError(
                "database must provide "
                f"{missing_text}."
            )

        self.database = database

    def reconcile_workspace(
        self,
        workspace_id,
        workspace_root,
        *,
        apply_changes=False,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Run a complete workspace reconciliation workflow.

        When apply_changes is False, return a read-only preview.

        When apply_changes is True:
            1. scan the workspace;
            2. insert discovered records;
            3. scan again to verify the resulting state.
        """
        normalized_workspace_id = (
            self._normalize_workspace_id(
                workspace_id
            )
        )

        root_path = self._normalize_workspace_root(
            workspace_root
        )

        if not isinstance(apply_changes, bool):
            raise TypeError(
                "apply_changes must be a boolean."
            )

        workflow = {
            "workspace_id":
                normalized_workspace_id,
            "workspace_root": str(root_path),
            "started_at":
                self._current_timestamp(),
            "completed_at": None,
            "apply_changes": apply_changes,
            "status": "running",
            "initial_scan": None,
            "apply_result": None,
            "verification_scan": None,
            "summary": {
                "files_scanned": 0,
                "database_records_checked": 0,
                "initial_matched_count": 0,
                "initial_unindexed_count": 0,
                "initial_missing_count": 0,
                "inserted_count": 0,
                "skipped_count": 0,
                "failed_count": 0,
                "remaining_unindexed_count": 0,
                "remaining_missing_count": 0,
                "scan_error_count": 0,
                "verification_error_count": 0,
            },
        }

        self._emit_progress(
            progress_callback,
            {
                "event": "workflow_started",
                "workspace_id":
                    normalized_workspace_id,
                "workspace_root":
                    str(root_path),
                "apply_changes":
                    apply_changes,
            },
        )

        initial_scan = self.scan_workspace(
            normalized_workspace_id,
            root_path,
            progress_callback=progress_callback,
        )

        workflow["initial_scan"] = initial_scan

        workflow["summary"].update(
            {
                "files_scanned":
                    initial_scan["files_scanned"],
                "database_records_checked":
                    initial_scan[
                        "database_records_checked"
                    ],
                "initial_matched_count": len(
                    initial_scan["matched_files"]
                ),
                "initial_unindexed_count": len(
                    initial_scan["unindexed_files"]
                ),
                "initial_missing_count": len(
                    initial_scan[
                        "missing_from_storage"
                    ]
                ),
                "scan_error_count": len(
                    initial_scan["errors"]
                ),
            }
        )

        if not apply_changes:
            workflow["completed_at"] = (
                self._current_timestamp()
            )

            workflow["status"] = (
                self.WORKFLOW_COMPLETED_WITH_ERRORS
                if initial_scan["errors"]
                else self.WORKFLOW_PREVIEW
            )

            workflow["summary"][
                "remaining_unindexed_count"
            ] = len(
                initial_scan["unindexed_files"]
            )

            workflow["summary"][
                "remaining_missing_count"
            ] = len(
                initial_scan["missing_from_storage"]
            )

            self._emit_progress(
                progress_callback,
                {
                    "event": "workflow_completed",
                    "workspace_id":
                        normalized_workspace_id,
                    "apply_changes": False,
                    "status":
                        workflow["status"],
                    **workflow["summary"],
                },
            )

            return workflow

        apply_result = self.apply_unindexed_files(
            normalized_workspace_id,
            initial_scan,
            progress_callback=progress_callback,
        )

        workflow["apply_result"] = apply_result

        workflow["summary"].update(
            {
                "inserted_count":
                    apply_result["inserted_count"],
                "skipped_count":
                    apply_result["skipped_count"],
                "failed_count":
                    apply_result["failed_count"],
            }
        )

        verification_scan = self.scan_workspace(
            normalized_workspace_id,
            root_path,
            progress_callback=progress_callback,
        )

        workflow[
            "verification_scan"
        ] = verification_scan

        workflow["summary"].update(
            {
                "remaining_unindexed_count": len(
                    verification_scan[
                        "unindexed_files"
                    ]
                ),
                "remaining_missing_count": len(
                    verification_scan[
                        "missing_from_storage"
                    ]
                ),
                "verification_error_count": len(
                    verification_scan["errors"]
                ),
            }
        )

        has_errors = any(
            (
                initial_scan["errors"],
                apply_result["failed_count"],
                verification_scan["errors"],
            )
        )

        workflow["status"] = (
            self.WORKFLOW_COMPLETED_WITH_ERRORS
            if has_errors
            else self.WORKFLOW_APPLIED
        )

        workflow["completed_at"] = (
            self._current_timestamp()
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "workflow_completed",
                "workspace_id":
                    normalized_workspace_id,
                "apply_changes": True,
                "status": workflow["status"],
                **workflow["summary"],
            },
        )

        return workflow

    def scan_workspace(
        self,
        workspace_id,
        workspace_root,
        *,
        progress_callback: Optional[ProgressCallback] = None,
    ):
        normalized_workspace_id = self._normalize_workspace_id(workspace_id)
        root_path = self._normalize_workspace_root(workspace_root)

        report = {
            "workspace_id": normalized_workspace_id,
            "workspace_root": str(root_path),
            "started_at": self._current_timestamp(),
            "completed_at": None,
            "status": "running",
            "files_scanned": 0,
            "directories_scanned": 0,
            "total_size": 0,
            "database_records_checked": 0,
            "files": [],
            "matched_files": [],
            "unindexed_files": [],
            "missing_from_storage": [],
            "errors": [],
        }

        database_index = self.database.get_workspace_file_index(
            normalized_workspace_id
        )

        report["database_records_checked"] = len(database_index)

        unmatched_database_paths = set(database_index)

        directory_stack = [root_path]

        while directory_stack:
            current_directory = directory_stack.pop()

            try:
                with os.scandir(current_directory) as entries:
                    report["directories_scanned"] += 1

                    for entry in entries:
                        try:
                            if entry.is_dir(follow_symlinks=False):
                                directory_stack.append(Path(entry.path))
                                continue

                            if not entry.is_file(follow_symlinks=False):
                                continue

                            file_record = self._build_file_record(
                                root_path,
                                entry,
                            )

                            normalized_relative_path = (
                                self._normalize_relative_path(
                                    file_record["relative_path"]
                                )
                            )

                            report["files"].append(file_record)
                            report["files_scanned"] += 1
                            report["total_size"] += file_record["file_size"]

                            database_record = database_index.get(
                                normalized_relative_path
                            )

                            if database_record is None:
                                report["unindexed_files"].append(
                                    dict(file_record)
                                )

                                comparison_event = "unindexed_file"

                            else:
                                unmatched_database_paths.discard(
                                    normalized_relative_path
                                )

                                report["matched_files"].append(
                                    {
                                        "file": dict(file_record),
                                        "database_record": dict(
                                            database_record
                                        ),
                                    }
                                )

                                comparison_event = "matched_file"

                            self._emit_progress(
                                progress_callback,
                                {
                                    "event": comparison_event,
                                    "workspace_id": normalized_workspace_id,
                                    "relative_path": file_record["relative_path"],
                                    "matched_count": len(
                                        report["matched_files"]
                                    ),
                                    "unindexed_count": len(
                                        report["unindexed_files"]
                                    ),
                                },
                            )

                            self._emit_progress(
                                progress_callback,
                                {
                                    "event": "file_scanned",
                                    "workspace_id": normalized_workspace_id,
                                    "files_scanned": report["files_scanned"],
                                    "directories_scanned": report[
                                        "directories_scanned"
                                    ],
                                    "current_path": file_record["relative_path"],
                                },
                            )

                        except (OSError, ValueError) as exc:
                            error = self._build_error(
                                entry.path,
                                exc,
                            )
                            report["errors"].append(error)

                            self._emit_progress(
                                progress_callback,
                                {
                                    "event": "file_error",
                                    "workspace_id": normalized_workspace_id,
                                    "path": str(entry.path),
                                    "error": str(exc),
                                },
                            )

            except OSError as exc:
                error = self._build_error(
                    current_directory,
                    exc,
                )
                report["errors"].append(error)

                self._emit_progress(
                    progress_callback,
                    {
                        "event": "directory_error",
                        "workspace_id": normalized_workspace_id,
                        "path": str(current_directory),
                        "error": str(exc),
                    },
                )

        for normalized_path in sorted(
            unmatched_database_paths
        ):
            database_record = database_index[
                normalized_path
            ]

            report["missing_from_storage"].append(
                dict(database_record)
            )

        report["completed_at"] = self._current_timestamp()
        report["status"] = (
            "completed_with_errors" if report["errors"] else "completed"
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "scan_completed",
                "workspace_id": normalized_workspace_id,
                "files_scanned": report["files_scanned"],
                "directories_scanned": report["directories_scanned"],
                "total_size": report["total_size"],
                "database_records_checked": report[
                    "database_records_checked"
                ],
                "matched_count": len(report["matched_files"]),
                "unindexed_count": len(report["unindexed_files"]),
                "missing_from_storage_count": len(
                    report["missing_from_storage"]
                ),
                "error_count": len(report["errors"]),
                "status": report["status"],
            },
        )

        return report

    def apply_unindexed_files(
        self,
        workspace_id,
        scan_report,
        *,
        progress_callback: Optional[
            ProgressCallback
        ] = None,
    ):
        """
        Insert unindexed filesystem records from a completed scan.

        Individual file failures are collected and do not stop the
        remaining records from being processed.
        """
        normalized_workspace_id = (
            self._normalize_workspace_id(
                workspace_id
            )
        )

        if not isinstance(scan_report, dict):
            raise TypeError(
                "scan_report must be a dictionary."
            )

        report_workspace_id = (
            scan_report.get("workspace_id")
        )

        if report_workspace_id is None:
            raise ValueError(
                "scan_report is missing workspace_id."
            )

        normalized_report_workspace_id = (
            self._normalize_workspace_id(
                report_workspace_id
            )
        )

        if (
            normalized_report_workspace_id
            != normalized_workspace_id
        ):
            raise ValueError(
                "scan_report belongs to a different "
                "workspace."
            )

        scan_status = str(
            scan_report.get("status") or ""
        ).strip().lower()

        if scan_status not in {
            "completed",
            "completed_with_errors",
        }:
            raise ValueError(
                "Only a completed scan report can be "
                "applied."
            )

        unindexed_files = scan_report.get(
            "unindexed_files"
        )

        if not isinstance(unindexed_files, list):
            raise TypeError(
                "scan_report unindexed_files must be "
                "a list."
            )

        result = {
            "workspace_id":
                normalized_workspace_id,
            "started_at":
                self._current_timestamp(),
            "completed_at": None,
            "status": "running",
            "requested": len(unindexed_files),
            "inserted_count": 0,
            "skipped_count": 0,
            "failed_count": 0,
            "inserted": [],
            "skipped": [],
            "failed": [],
        }

        for index, file_record in enumerate(
            unindexed_files,
            start=1,
        ):
            relative_path = ""

            if isinstance(file_record, dict):
                relative_path = str(
                    file_record.get(
                        "relative_path"
                    )
                    or ""
                ).strip()

            self._emit_progress(
                progress_callback,
                {
                    "event": "apply_file_started",
                    "workspace_id":
                        normalized_workspace_id,
                    "index": index,
                    "total": len(
                        unindexed_files
                    ),
                    "relative_path":
                        relative_path,
                },
            )

            try:
                database_result = (
                    self.database
                    .insert_discovered_file_record(
                        normalized_workspace_id,
                        file_record,
                    )
                )

                applied_record = {
                    "file_id": int(
                        database_result["file_id"]
                    ),
                    "relative_path": str(
                        database_result[
                            "relative_path"
                        ]
                    ),
                }

                if database_result["inserted"]:
                    result["inserted"].append(
                        applied_record
                    )
                    result["inserted_count"] += 1
                    event_name = "apply_file_inserted"

                else:
                    result["skipped"].append(
                        applied_record
                    )
                    result["skipped_count"] += 1
                    event_name = "apply_file_skipped"

                self._emit_progress(
                    progress_callback,
                    {
                        "event": event_name,
                        "workspace_id":
                            normalized_workspace_id,
                        "index": index,
                        "total": len(
                            unindexed_files
                        ),
                        "file_id":
                            applied_record["file_id"],
                        "relative_path":
                            applied_record[
                                "relative_path"
                            ],
                        "inserted_count":
                            result[
                                "inserted_count"
                            ],
                        "skipped_count":
                            result[
                                "skipped_count"
                            ],
                        "failed_count":
                            result[
                                "failed_count"
                            ],
                    },
                )

            except Exception as exc:
                failure = {
                    "relative_path":
                        relative_path,
                    "error_type":
                        type(exc).__name__,
                    "message": str(exc),
                }

                result["failed"].append(failure)
                result["failed_count"] += 1

                self._emit_progress(
                    progress_callback,
                    {
                        "event": "apply_file_failed",
                        "workspace_id":
                            normalized_workspace_id,
                        "index": index,
                        "total": len(
                            unindexed_files
                        ),
                        "relative_path":
                            relative_path,
                        "error_type":
                            failure["error_type"],
                        "message":
                            failure["message"],
                        "inserted_count":
                            result[
                                "inserted_count"
                            ],
                        "skipped_count":
                            result[
                                "skipped_count"
                            ],
                        "failed_count":
                            result[
                                "failed_count"
                            ],
                    },
                )

        result["completed_at"] = (
            self._current_timestamp()
        )

        result["status"] = (
            "completed_with_errors"
            if result["failed_count"]
            else "completed"
        )

        self._emit_progress(
            progress_callback,
            {
                "event": "apply_completed",
                "workspace_id":
                    normalized_workspace_id,
                "requested":
                    result["requested"],
                "inserted_count":
                    result["inserted_count"],
                "skipped_count":
                    result["skipped_count"],
                "failed_count":
                    result["failed_count"],
                "status": result["status"],
            },
        )

        return result

    @staticmethod
    def _build_file_record(root_path, directory_entry):
        stat_result = directory_entry.stat(follow_symlinks=False)

        full_path = Path(directory_entry.path)
        relative_path = full_path.relative_to(root_path)

        return {
            "original_filename": full_path.name,
            "archived_filename": full_path.name,
            "relative_path": str(relative_path),
            "file_ext": full_path.suffix.lower(),
            "file_size": int(stat_result.st_size),
            "source_created_at": WorkspaceReconciliationService._timestamp_from_epoch(
                stat_result.st_ctime
            ),
            "source_modified_at": WorkspaceReconciliationService._timestamp_from_epoch(
                stat_result.st_mtime
            ),
        }

    @staticmethod
    def _normalize_workspace_id(workspace_id):
        try:
            normalized = int(workspace_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("workspace_id must be an integer.") from exc

        if normalized <= 0:
            raise ValueError("workspace_id must be greater than zero.")

        return normalized

    @staticmethod
    def _normalize_workspace_root(workspace_root):
        if workspace_root is None:
            raise ValueError("workspace_root is required.")

        root_path = Path(workspace_root)

        if not root_path.exists():
            raise FileNotFoundError(f"Workspace path does not exist: {root_path}")

        if not root_path.is_dir():
            raise NotADirectoryError(
                f"Workspace path is not a directory: {root_path}"
            )

        return root_path

    @staticmethod
    def _normalize_relative_path(relative_path):
        normalized = str(relative_path or "").strip()

        if not normalized:
            raise ValueError("relative_path is required.")

        path = Path(normalized)

        if (
            path.is_absolute()
            or path.anchor
            or path.drive
            or path.root
            or ".." in path.parts
        ):
            raise ValueError(
                "relative_path must remain inside "
                "the workspace."
            )

        return path.as_posix().casefold()

    @staticmethod
    def _timestamp_from_epoch(epoch_value):
        return datetime.fromtimestamp(epoch_value).isoformat(
            sep=" ",
            timespec="seconds",
        )

    @staticmethod
    def _current_timestamp():
        return datetime.now().isoformat(
            sep=" ",
            timespec="seconds",
        )

    @staticmethod
    def _build_error(path, exception):
        return {
            "path": str(path),
            "error_type": type(exception).__name__,
            "message": str(exception),
        }

    @staticmethod
    def _emit_progress(callback, event):
        if callback is None:
            return

        try:
            callback(dict(event))
        except Exception:
            # UI progress callbacks must never stop the scan.
            pass