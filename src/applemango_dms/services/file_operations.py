import os
import re
import shutil
import tempfile
from pathlib import Path


class FileOperationConsistencyError(RuntimeError):
    """
    Raised when a filesystem/database operation fails and its
    rollback also fails.
    """


class FileOperationsService:
    """
    Coordinate safe read-only operations on archived files.

    This service uses file_id as the record identity and retrieves
    current path information from the database immediately before
    each filesystem operation.
    """

    _invalid_filename_chars = re.compile(
        r'[<>:"/\\|?*\x00-\x1f]'
    )

    _reserved_windows_names = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{number}" for number in range(1, 10)),
        *(f"LPT{number}" for number in range(1, 10)),
    }

    _maximum_filename_length = 220

    def __init__(self, database):
        self.database = database

    @staticmethod
    def _validate_relative_path(value):
        normalized = str(value or "").strip()

        if not normalized:
            raise ValueError(
                "The file record has no relative path."
            )

        relative_path = Path(normalized)

        if (
            relative_path.is_absolute()
            or relative_path.anchor
            or relative_path.drive
            or relative_path.root
        ):
            raise ValueError(
                "The stored relative path cannot be absolute "
                "or rooted."
            )

        if not relative_path.parts:
            raise ValueError(
                "The stored relative path is invalid."
            )

        if ".." in relative_path.parts:
            raise ValueError(
                "The stored relative path cannot leave "
                "the workspace."
            )

        return relative_path

    @classmethod
    def _normalize_renamed_filename(
        cls,
        value,
        expected_extension,
    ):
        filename = str(value or "").strip()

        if not filename:
            raise ValueError(
                "The new filename is required."
            )

        if cls._invalid_filename_chars.search(filename):
            raise ValueError(
                "The new filename contains invalid "
                "characters."
            )

        if filename.endswith((" ", ".")):
            raise ValueError(
                "The new filename cannot end with a space "
                "or period."
            )

        if len(filename) > cls._maximum_filename_length:
            raise ValueError(
                "The new filename is too long."
            )

        filename_path = Path(filename)

        if filename_path.name != filename:
            raise ValueError(
                "The new value must contain a filename only."
            )

        expected_extension = str(
            expected_extension or ""
        ).lower()

        supplied_extension = filename_path.suffix.lower()

        if not supplied_extension and expected_extension:
            filename = f"{filename}{expected_extension}"
            filename_path = Path(filename)
            supplied_extension = expected_extension

        if supplied_extension != expected_extension:
            raise ValueError(
                "Renaming cannot change the file extension."
            )

        reserved_stem = filename_path.stem.upper()

        if reserved_stem in cls._reserved_windows_names:
            raise ValueError(
                "The requested filename is reserved by "
                "Windows."
            )

        if len(filename) > cls._maximum_filename_length:
            raise ValueError(
                "The new filename is too long."
            )

        return filename

    def _get_active_record(
        self,
        workspace_id,
        file_id,
    ):
        record = self.database.get_file_by_id(
            workspace_id,
            file_id,
        )

        if record is None:
            raise LookupError(
                "Active file not found in workspace."
            )

        self._validate_relative_path(
            record["relative_path"]
        )

        return record

    def _get_existing_file_path(self, record):
        relative_path = self._validate_relative_path(
            record["relative_path"]
        )
        full_path = Path(record["full_path"])

        workspace_path = full_path

        for _part in relative_path.parts:
            workspace_path = workspace_path.parent

        try:
            workspace_available = (
                workspace_path.exists()
                and workspace_path.is_dir()
            )
        except OSError as exc:
            raise ConnectionError(
                f"The workspace is not accessible: "
                f"{workspace_path}"
            ) from exc

        if not workspace_available:
            raise ConnectionError(
                f"The workspace is not accessible: "
                f"{workspace_path}"
            )

        try:
            is_file = full_path.is_file()
        except OSError as exc:
            raise FileNotFoundError(
                f"The archived file is not accessible: "
                f"{full_path}"
            ) from exc

        if not is_file:
            self.database.mark_file_missing(
                record["workspace_id"],
                record["file_id"],
            )

            raise FileNotFoundError(
                f"The archived file does not exist: "
                f"{full_path}"
            )

        return full_path

    def get_openable_path(
        self,
        workspace_id,
        file_id,
    ):
        """
        Return a verified path suitable for opening.

        This method does not launch an external application.
        """
        record = self._get_active_record(
            workspace_id,
            file_id,
        )

        return self._get_existing_file_path(record)

    def open_file(
        self,
        workspace_id,
        file_id,
    ):
        """
        Open an archived file with the operating system's default
        application.

        Returns the verified path after launching it.
        """
        full_path = self.get_openable_path(
            workspace_id,
            file_id,
        )

        if not hasattr(os, "startfile"):
            raise NotImplementedError(
                "Opening files is currently supported only "
                "on Windows."
            )

        os.startfile(str(full_path))
        return full_path

    def copy_file_to(
        self,
        workspace_id,
        file_id,
        destination,
        *,
        overwrite=False,
    ):
        """
        Copy an archived file to a selected local destination.

        The NAS source remains unchanged. The database is not
        modified.

        If destination is an existing directory, the original
        filename is used inside that directory.

        Returns the completed destination path.
        """
        record = self._get_active_record(
            workspace_id,
            file_id,
        )
        source_path = self._get_existing_file_path(
            record
        )

        destination_path = Path(destination)

        if destination_path.exists():
            if destination_path.is_dir():
                destination_path = (
                    destination_path
                    / record["original_filename"]
                )
            elif not overwrite:
                raise FileExistsError(
                    f"The destination already exists: "
                    f"{destination_path}"
                )

        destination_parent = destination_path.parent

        if not destination_parent.exists():
            raise FileNotFoundError(
                f"The destination folder does not exist: "
                f"{destination_parent}"
            )

        if not destination_parent.is_dir():
            raise NotADirectoryError(
                f"The destination parent is not a folder: "
                f"{destination_parent}"
            )

        if destination_path.exists() and not overwrite:
            raise FileExistsError(
                f"The destination already exists: "
                f"{destination_path}"
            )

        try:
            same_file = (
                source_path.resolve()
                == destination_path.resolve()
            )
        except OSError:
            same_file = False

        if same_file:
            raise ValueError(
                "The source and destination cannot be "
                "the same file."
            )

        if overwrite:
            temporary_path = None

            try:
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{destination_path.name}.",
                    suffix=".copying",
                    dir=destination_parent,
                )
                os.close(descriptor)
                temporary_path = Path(temporary_name)

                shutil.copy2(
                    source_path,
                    temporary_path,
                )

                os.replace(
                    temporary_path,
                    destination_path,
                )
                temporary_path = None

            finally:
                if temporary_path is not None:
                    try:
                        temporary_path.unlink(
                            missing_ok=True
                        )
                    except OSError:
                        pass

        else:
            destination_was_created = False

            try:
                with source_path.open("rb") as source_stream:
                    with destination_path.open(
                        "xb"
                    ) as destination_stream:
                        destination_was_created = True

                        shutil.copyfileobj(
                            source_stream,
                            destination_stream,
                        )

                shutil.copystat(
                    source_path,
                    destination_path,
                )

            except Exception:
                if destination_was_created:
                    try:
                        destination_path.unlink(
                            missing_ok=True
                        )
                    except OSError:
                        pass

                raise

        return destination_path

    def soft_delete_file(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
    ):
        """
        Move one active NAS file into managed workspace trash,
        then mark its database record deleted.

        The original relative path remains in SQLite so a future
        restore operation knows where the file belongs.

        Returns:
            A dictionary containing the deleted database record
            and physical trash path.
        """
        normalized_acting_user = str(
            acting_user or ""
        ).strip()

        if not normalized_acting_user:
            raise ValueError(
                "acting_user is required."
            )

        record = self._get_active_record(
            workspace_id,
            file_id,
        )

        stored_uploader = str(
            record["uploaded_by"] or ""
        ).strip()

        if (
            stored_uploader.casefold()
            != normalized_acting_user.casefold()
        ):
            raise PermissionError(
                "Only the original uploader may delete "
                "this file."
            )

        relative_path = self._validate_relative_path(
            record["relative_path"]
        )
        source_path = self._get_existing_file_path(
            record
        )

        workspace_path = source_path

        for _part in relative_path.parts:
            workspace_path = workspace_path.parent

        trash_directory = (
            workspace_path
            / ".applemango_trash"
            / str(record["file_id"])
        )
        trash_path = (
            trash_directory
            / source_path.name
        )

        if trash_directory.exists():
            raise FileExistsError(
                "A trash entry already exists for this file: "
                f"{trash_directory}"
            )

        moved_to_trash = False

        try:
            trash_directory.mkdir(
                parents=True,
                exist_ok=False,
            )

            os.replace(
                source_path,
                trash_path,
            )
            moved_to_trash = True

        except Exception:
            if not moved_to_trash:
                try:
                    trash_directory.rmdir()
                except OSError:
                    pass

            raise

        try:
            deleted_record = (
                self.database.mark_file_deleted(
                    record["workspace_id"],
                    record["file_id"],
                    acting_user=normalized_acting_user,
                )
            )

        except Exception as database_error:
            try:
                os.replace(
                    trash_path,
                    source_path,
                )

                try:
                    trash_directory.rmdir()
                except OSError:
                    pass

            except Exception as rollback_error:
                raise FileOperationConsistencyError(
                    "The file was moved into trash, the "
                    "database update failed, and the file "
                    "could not be moved back. "
                    f"Database error: {database_error}. "
                    f"Rollback error: {rollback_error}."
                ) from rollback_error

            raise

        return {
            "record": deleted_record,
            "trash_path": trash_path,
        }

    def restore_file(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
    ):
        """
        Move a soft-deleted file from managed trash back to its
        original NAS location, then restore its database record.

        Returns:
            The restored database record and physical path.
        """
        normalized_acting_user = str(
            acting_user or ""
        ).strip()

        if not normalized_acting_user:
            raise ValueError(
                "acting_user is required."
            )

        record = self.database.get_file_by_id(
            workspace_id,
            file_id,
            statuses=["deleted"],
        )

        if record is None:
            raise LookupError(
                "Deleted file not found in workspace."
            )

        stored_uploader = str(
            record["uploaded_by"] or ""
        ).strip()

        if (
            stored_uploader.casefold()
            != normalized_acting_user.casefold()
        ):
            raise PermissionError(
                "Only the original uploader may restore "
                "this file."
            )

        relative_path = self._validate_relative_path(
            record["relative_path"]
        )
        original_path = Path(record["full_path"])

        workspace_path = original_path

        for _part in relative_path.parts:
            workspace_path = workspace_path.parent

        try:
            workspace_available = (
                workspace_path.exists()
                and workspace_path.is_dir()
            )
        except OSError as exc:
            raise ConnectionError(
                f"The workspace is not accessible: "
                f"{workspace_path}"
            ) from exc

        if not workspace_available:
            raise ConnectionError(
                f"The workspace is not accessible: "
                f"{workspace_path}"
            )

        trash_directory = (
            workspace_path
            / ".applemango_trash"
            / str(record["file_id"])
        )
        trash_path = (
            trash_directory
            / original_path.name
        )

        try:
            trash_file_exists = trash_path.is_file()
        except OSError as exc:
            raise FileNotFoundError(
                f"The trashed file is not accessible: "
                f"{trash_path}"
            ) from exc

        if not trash_file_exists:
            raise FileNotFoundError(
                f"The trashed file does not exist: "
                f"{trash_path}"
            )

        if original_path.exists():
            raise FileExistsError(
                "The original destination is already occupied: "
                f"{original_path}"
            )

        original_parent = original_path.parent

        if not original_parent.exists():
            original_parent.mkdir(
                parents=True,
                exist_ok=True,
            )

        moved_from_trash = False

        try:
            os.replace(
                trash_path,
                original_path,
            )
            moved_from_trash = True

        except Exception:
            raise

        try:
            restored_record = (
                self.database.restore_file_record(
                    record["workspace_id"],
                    record["file_id"],
                    acting_user=normalized_acting_user,
                )
            )

        except Exception as database_error:
            if moved_from_trash:
                try:
                    os.replace(
                        original_path,
                        trash_path,
                    )

                except Exception as rollback_error:
                    raise FileOperationConsistencyError(
                        "The file was restored physically, the "
                        "database update failed, and the file "
                        "could not be returned to trash. "
                        f"Database error: {database_error}. "
                        f"Rollback error: {rollback_error}."
                    ) from rollback_error

            raise

        try:
            trash_directory.rmdir()
        except OSError:
            pass

        trash_root = workspace_path / ".applemango_trash"

        try:
            trash_root.rmdir()
        except OSError:
            pass

        return {
            "record": restored_record,
            "restored_path": original_path,
        }

    def rename_file(
        self,
        workspace_id,
        file_id,
        *,
        acting_user,
        new_filename,
    ):
        """
        Rename one active physical NAS file and update its SQLite
        filename/path metadata.

        The extension cannot be changed.

        Returns:
            The refreshed record and renamed physical path.
        """
        normalized_acting_user = str(
            acting_user or ""
        ).strip()

        if not normalized_acting_user:
            raise ValueError(
                "acting_user is required."
            )

        record = self._get_active_record(
            workspace_id,
            file_id,
        )

        stored_uploader = str(
            record["uploaded_by"] or ""
        ).strip()

        if (
            stored_uploader.casefold()
            != normalized_acting_user.casefold()
        ):
            raise PermissionError(
                "Only the original uploader may rename "
                "this file."
            )

        normalized_filename = (
            self._normalize_renamed_filename(
                new_filename,
                record["file_ext"],
            )
        )

        source_path = self._get_existing_file_path(
            record
        )

        if (
            source_path.name.casefold()
            == normalized_filename.casefold()
        ):
            raise ValueError(
                "The new filename is the same as the "
                "current filename."
            )

        destination_path = (
            source_path.parent
            / normalized_filename
        )

        if destination_path.exists():
            raise FileExistsError(
                f"The destination already exists: "
                f"{destination_path}"
            )

        old_relative_path = self._validate_relative_path(
            record["relative_path"]
        )
        new_relative_path = (
            old_relative_path.parent
            / normalized_filename
        )

        moved_to_destination = False

        try:
            os.replace(
                source_path,
                destination_path,
            )
            moved_to_destination = True

        except Exception:
            raise

        try:
            renamed_record = (
                self.database.rename_file_record(
                    record["workspace_id"],
                    record["file_id"],
                    acting_user=normalized_acting_user,
                    archived_filename=normalized_filename,
                    relative_path=str(new_relative_path),
                )
            )

        except Exception as database_error:
            if moved_to_destination:
                try:
                    os.replace(
                        destination_path,
                        source_path,
                    )

                except Exception as rollback_error:
                    raise FileOperationConsistencyError(
                        "The NAS file was renamed, the "
                        "database update failed, and the "
                        "physical rename could not be rolled "
                        "back. "
                        f"Database error: {database_error}. "
                        f"Rollback error: {rollback_error}."
                    ) from rollback_error

            raise

        return {
            "record": renamed_record,
            "renamed_path": destination_path,
        }
