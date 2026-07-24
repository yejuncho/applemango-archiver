import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from applemango_dms.db.sqlite import ArchiveDatabase
from applemango_dms.services.file_operations import (
    FileOperationsService,
)


class FileOperationsTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)

        self.share_path = self.root / "share"
        self.archive_path = self.share_path / "archive"
        self.archive_path.mkdir(parents=True)

        self.database = ArchiveDatabase(
            self.root / "archive.db"
        )
        self.workspace_id = (
            self.database.ensure_workspace(
                "Test Workspace",
                self.share_path,
                ["Invoice"],
            )
        )
        self.document_type_id = (
            self.database.get_document_types(
                self.workspace_id
            )[0]["id"]
        )

        self.service = FileOperationsService(
            self.database
        )

    def tearDown(self):
        self.service = None
        self.database = None
        self.temp_directory.cleanup()

    def add_file(
        self,
        filename,
        *,
        content=b"test content",
        create_physical_file=True,
        status="active",
        uploaded_by="Daniel",
    ):
        relative_path = Path("archive") / filename
        full_path = self.share_path / relative_path

        if create_physical_file:
            full_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            full_path.write_bytes(content)

        with self.database._connect() as conn:
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
                    file_ext,
                    file_size,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    self.workspace_id,
                    self.document_type_id,
                    uploaded_by,
                    f"original-{filename}",
                    filename,
                    str(relative_path),
                    "2026-07-24",
                    Path(filename).suffix.lower(),
                    len(content),
                    status,
                ),
            )

            file_id = int(cursor.lastrowid)

        return file_id, full_path

    def get_record(self, file_id):
        return self.database.get_file_by_id(
            self.workspace_id,
            file_id,
            statuses=[
                "active",
                "missing",
                "deleted",
            ],
        )

    def test_relative_path_validation(self):
        invalid_values = [
            "",
            ".",
            "..",
            "../escape.pdf",
            r"..\escape.pdf",
            r"\rooted.pdf",
            r"C:\absolute.pdf",
        ]

        for value in invalid_values:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    self.service._validate_relative_path(
                        value
                    )

        valid = self.service._validate_relative_path(
            r"archive\valid.pdf"
        )

        self.assertEqual(
            valid,
            Path("archive") / "valid.pdf",
        )

    def test_get_openable_path(self):
        file_id, full_path = self.add_file(
            "openable.pdf"
        )

        result = self.service.get_openable_path(
            self.workspace_id,
            file_id,
        )

        self.assertEqual(result, full_path)
        self.assertTrue(result.is_file())

    def test_missing_file_is_marked_missing(self):
        file_id, full_path = self.add_file(
            "missing.pdf",
            create_physical_file=False,
        )

        with self.assertRaises(FileNotFoundError):
            self.service.get_openable_path(
                self.workspace_id,
                file_id,
            )

        record = self.get_record(file_id)

        self.assertFalse(full_path.exists())
        self.assertEqual(record["status"], "missing")
        self.assertIsNone(record["deleted_at"])

    def test_unavailable_workspace_stays_active(self):
        file_id, _full_path = self.add_file(
            "offline.pdf",
            create_physical_file=False,
        )

        offline_path = self.root / "share-offline"
        self.share_path.rename(offline_path)

        try:
            with self.assertRaises(ConnectionError):
                self.service.get_openable_path(
                    self.workspace_id,
                    file_id,
                )

            record = self.get_record(file_id)

            self.assertEqual(record["status"], "active")

        finally:
            offline_path.rename(self.share_path)

    def test_copy_preserves_source_and_handles_collision(
        self,
    ):
        content = b"NAS source data"

        file_id, source_path = self.add_file(
            "copy.pdf",
            content=content,
        )
        destination = self.root / "local-copy.pdf"

        result = self.service.copy_file_to(
            self.workspace_id,
            file_id,
            destination,
        )

        self.assertEqual(result, destination)
        self.assertEqual(destination.read_bytes(), content)
        self.assertEqual(source_path.read_bytes(), content)

        with self.assertRaises(FileExistsError):
            self.service.copy_file_to(
                self.workspace_id,
                file_id,
                destination,
            )

        destination.write_bytes(b"old")

        self.service.copy_file_to(
            self.workspace_id,
            file_id,
            destination,
            overwrite=True,
        )

        self.assertEqual(destination.read_bytes(), content)
        self.assertEqual(source_path.read_bytes(), content)

    def test_failed_overwrite_preserves_destination(self):
        file_id, _source_path = self.add_file(
            "overwrite.pdf",
            content=b"new data",
        )
        destination = self.root / "destination.pdf"
        destination.write_bytes(b"existing data")

        def fail_copy(_source, temporary_path):
            Path(temporary_path).write_bytes(
                b"partial data"
            )
            raise OSError("Forced copy failure")

        with patch(
            "applemango_dms.services.file_operations."
            "shutil.copy2",
            side_effect=fail_copy,
        ):
            with self.assertRaises(OSError):
                self.service.copy_file_to(
                    self.workspace_id,
                    file_id,
                    destination,
                    overwrite=True,
                )

        self.assertEqual(
            destination.read_bytes(),
            b"existing data",
        )

        leftovers = list(
            destination.parent.glob(
                f".{destination.name}.*.copying"
            )
        )
        self.assertEqual(leftovers, [])

    def test_soft_delete_and_restore_cycle(self):
        content = b"recoverable data"

        file_id, original_path = self.add_file(
            "cycle.pdf",
            content=content,
        )

        deleted = self.service.soft_delete_file(
            self.workspace_id,
            file_id,
            acting_user="daniel",
        )

        trash_path = deleted["trash_path"]
        deleted_record = self.get_record(file_id)

        self.assertFalse(original_path.exists())
        self.assertTrue(trash_path.is_file())
        self.assertEqual(trash_path.read_bytes(), content)
        self.assertEqual(
            deleted_record["status"],
            "deleted",
        )
        self.assertIsNotNone(
            deleted_record["deleted_at"]
        )

        restored = self.service.restore_file(
            self.workspace_id,
            file_id,
            acting_user="DANIEL",
        )

        restored_record = self.get_record(file_id)

        self.assertEqual(
            restored["restored_path"],
            original_path,
        )
        self.assertTrue(original_path.is_file())
        self.assertEqual(original_path.read_bytes(), content)
        self.assertFalse(trash_path.exists())
        self.assertEqual(
            restored_record["status"],
            "active",
        )
        self.assertIsNone(
            restored_record["deleted_at"]
        )

    def test_delete_requires_original_uploader(self):
        file_id, original_path = self.add_file(
            "protected.pdf"
        )

        with self.assertRaises(PermissionError):
            self.service.soft_delete_file(
                self.workspace_id,
                file_id,
                acting_user="Alice",
            )

        self.assertTrue(original_path.is_file())
        self.assertEqual(
            self.get_record(file_id)["status"],
            "active",
        )

    def test_delete_database_failure_rolls_back_file(
        self,
    ):
        content = b"rollback data"

        file_id, original_path = self.add_file(
            "delete-rollback.pdf",
            content=content,
        )

        with patch.object(
            self.database,
            "mark_file_deleted",
            side_effect=RuntimeError(
                "Forced database failure"
            ),
        ):
            with self.assertRaises(RuntimeError):
                self.service.soft_delete_file(
                    self.workspace_id,
                    file_id,
                    acting_user="Daniel",
                )

        self.assertTrue(original_path.is_file())
        self.assertEqual(
            original_path.read_bytes(),
            content,
        )
        self.assertEqual(
            self.get_record(file_id)["status"],
            "active",
        )

        trash_directory = (
            self.share_path
            / ".applemango_trash"
            / str(file_id)
        )
        self.assertFalse(trash_directory.exists())

    def test_restore_rejects_occupied_destination(self):
        file_id, original_path = self.add_file(
            "occupied.pdf",
            content=b"archived data",
        )

        deleted = self.service.soft_delete_file(
            self.workspace_id,
            file_id,
            acting_user="Daniel",
        )

        original_path.write_bytes(b"occupying data")

        with self.assertRaises(FileExistsError):
            self.service.restore_file(
                self.workspace_id,
                file_id,
                acting_user="Daniel",
            )

        self.assertEqual(
            original_path.read_bytes(),
            b"occupying data",
        )
        self.assertTrue(
            deleted["trash_path"].is_file()
        )
        self.assertEqual(
            self.get_record(file_id)["status"],
            "deleted",
        )

    def test_restore_database_failure_returns_file_to_trash(
        self,
    ):
        content = b"restore rollback"

        file_id, original_path = self.add_file(
            "restore-rollback.pdf",
            content=content,
        )

        deleted = self.service.soft_delete_file(
            self.workspace_id,
            file_id,
            acting_user="Daniel",
        )
        trash_path = deleted["trash_path"]

        with patch.object(
            self.database,
            "restore_file_record",
            side_effect=RuntimeError(
                "Forced restore database failure"
            ),
        ):
            with self.assertRaises(RuntimeError):
                self.service.restore_file(
                    self.workspace_id,
                    file_id,
                    acting_user="Daniel",
                )

        self.assertFalse(original_path.exists())
        self.assertTrue(trash_path.is_file())
        self.assertEqual(trash_path.read_bytes(), content)
        self.assertEqual(
            self.get_record(file_id)["status"],
            "deleted",
        )

    def test_rename_updates_file_and_database(self):
        content = b"rename data"

        file_id, old_path = self.add_file(
            "old-name.pdf",
            content=content,
        )
        original_filename = self.get_record(
            file_id
        )["original_filename"]

        result = self.service.rename_file(
            self.workspace_id,
            file_id,
            acting_user="daniel",
            new_filename="new-name",
        )

        new_path = old_path.parent / "new-name.pdf"
        record = self.get_record(file_id)

        self.assertFalse(old_path.exists())
        self.assertTrue(new_path.is_file())
        self.assertEqual(new_path.read_bytes(), content)
        self.assertEqual(
            result["renamed_path"],
            new_path,
        )
        self.assertEqual(
            record["archived_filename"],
            "new-name.pdf",
        )
        self.assertEqual(
            Path(record["relative_path"]).name,
            "new-name.pdf",
        )
        self.assertEqual(
            record["original_filename"],
            original_filename,
        )

    def test_rename_validation_and_authorization(self):
        file_id, original_path = self.add_file(
            "validation.pdf"
        )

        invalid_names = [
            "changed.docx",
            "CON.pdf",
            "bad/name.pdf",
            "bad?.pdf",
            "trailing.",
            "VALIDATION.PDF",
        ]

        for new_name in invalid_names:
            with self.subTest(new_name=new_name):
                with self.assertRaises(ValueError):
                    self.service.rename_file(
                        self.workspace_id,
                        file_id,
                        acting_user="Daniel",
                        new_filename=new_name,
                    )

        with self.assertRaises(PermissionError):
            self.service.rename_file(
                self.workspace_id,
                file_id,
                acting_user="Alice",
                new_filename="allowed.pdf",
            )

        self.assertTrue(original_path.is_file())
        self.assertEqual(
            self.get_record(file_id)[
                "archived_filename"
            ],
            "validation.pdf",
        )

    def test_rename_database_failure_rolls_back_file(
        self,
    ):
        content = b"rename rollback"

        file_id, original_path = self.add_file(
            "rename-rollback.pdf",
            content=content,
        )
        attempted_path = (
            original_path.parent
            / "temporary-name.pdf"
        )

        with patch.object(
            self.database,
            "rename_file_record",
            side_effect=RuntimeError(
                "Forced rename database failure"
            ),
        ):
            with self.assertRaises(RuntimeError):
                self.service.rename_file(
                    self.workspace_id,
                    file_id,
                    acting_user="Daniel",
                    new_filename="temporary-name.pdf",
                )

        self.assertTrue(original_path.is_file())
        self.assertEqual(
            original_path.read_bytes(),
            content,
        )
        self.assertFalse(attempted_path.exists())
        self.assertEqual(
            self.get_record(file_id)[
                "archived_filename"
            ],
            "rename-rollback.pdf",
        )


if __name__ == "__main__":
    unittest.main()
