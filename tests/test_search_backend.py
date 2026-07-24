import tempfile
import unittest
from pathlib import Path

from applemango_dms.db.sqlite import ArchiveDatabase


class SearchBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)

        self.share_one = self.root / "share-one"
        self.share_two = self.root / "share-two"
        self.share_one.mkdir()
        self.share_two.mkdir()

        self.database = ArchiveDatabase(
            self.root / "archive.db"
        )

        self.workspace_one = self.database.ensure_workspace(
            "Workspace One",
            self.share_one,
            ["Invoice", "Report"],
        )
        self.workspace_two = self.database.ensure_workspace(
            "Workspace Two",
            self.share_two,
            ["Invoice"],
        )

        self.types_one = {
            row["name"]: row["id"]
            for row in self.database.get_document_types(
                self.workspace_one
            )
        }
        self.types_two = {
            row["name"]: row["id"]
            for row in self.database.get_document_types(
                self.workspace_two
            )
        }

    def tearDown(self):
        self.database = None
        self.temp_directory.cleanup()

    def add_file(
        self,
        *,
        workspace_id=None,
        document_type_id=None,
        filename,
        document_date="2026-07-24",
        uploaded_by="Daniel",
        file_ext=None,
        file_size=1000,
        tags=None,
        status="active",
        archived_at="2026-07-24 12:00:00",
    ):
        if workspace_id is None:
            workspace_id = self.workspace_one

        if document_type_id is None:
            document_type_id = self.types_one["Invoice"]

        if file_ext is None:
            file_ext = Path(filename).suffix.lower()

        relative_path = str(
            Path("archive") / filename
        )

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
                    archived_at,
                    status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    workspace_id,
                    document_type_id,
                    uploaded_by,
                    filename,
                    filename,
                    relative_path,
                    document_date,
                    file_ext,
                    file_size,
                    archived_at,
                    status,
                ),
            )

            file_id = int(cursor.lastrowid)

            self.database._assign_tags_with_conn(
                conn,
                workspace_id,
                file_id,
                self.database._normalize_tag_names(tags),
                verify_file_exists=False,
            )

        return file_id

    def test_default_search_is_active_and_workspace_scoped(
        self,
    ):
        active_id = self.add_file(
            filename="active.pdf",
        )
        self.add_file(
            filename="deleted.pdf",
            status="deleted",
        )
        self.add_file(
            filename="missing.pdf",
            status="missing",
        )
        self.add_file(
            workspace_id=self.workspace_two,
            document_type_id=self.types_two["Invoice"],
            filename="other-workspace.pdf",
        )

        results = self.database.search_files(
            self.workspace_one
        )

        self.assertEqual(
            [row["file_id"] for row in results],
            [active_id],
        )
        self.assertEqual(results[0]["status"], "active")

    def test_all_metadata_relevance_order(self):
        exact_id = self.add_file(
            filename="invoice",
            document_date="2024-01-01",
            file_ext="",
        )
        starts_id = self.add_file(
            filename="invoice-start.pdf",
            document_date="2025-01-01",
        )
        contains_id = self.add_file(
            filename="my-invoice-note.pdf",
            document_date="2026-01-01",
            document_type_id=self.types_one["Report"],
        )
        tag_id = self.add_file(
            filename="tagged.pdf",
            document_date="2026-02-01",
            tags=["invoice"],
        )
        type_id = self.add_file(
            filename="typed.pdf",
            document_date="2026-03-01",
            document_type_id=self.types_one["Invoice"],
        )
        uploader_id = self.add_file(
            filename="uploaded.pdf",
            document_date="2026-04-01",
            uploaded_by="invoice",
            document_type_id=self.types_one["Report"],
        )

        results = self.database.search_files(
            self.workspace_one,
            search_text="invoice",
            search_field="all",
        )

        result_ids = [
            row["file_id"]
            for row in results
        ]

        self.assertLess(
            result_ids.index(exact_id),
            result_ids.index(starts_id),
        )
        self.assertLess(
            result_ids.index(starts_id),
            result_ids.index(tag_id),
        )
        self.assertLess(
            result_ids.index(tag_id),
            result_ids.index(contains_id),
        )
        self.assertLess(
            result_ids.index(contains_id),
            result_ids.index(uploader_id),
        )

        scores = {
            row["file_id"]: row["relevance_score"]
            for row in results
        }

        self.assertEqual(scores[exact_id], 100)
        self.assertEqual(scores[starts_id], 85)
        self.assertEqual(scores[tag_id], 75)
        self.assertEqual(scores[contains_id], 60)
        self.assertEqual(scores[uploader_id], 55)

        self.assertIn(type_id, result_ids)

    def test_literal_like_characters_are_escaped(self):
        expected_id = self.add_file(
            filename="invoice_100%.pdf",
        )
        self.add_file(
            filename="invoice_1000.pdf",
        )

        results = self.database.search_files(
            self.workspace_one,
            search_text="100%",
            search_field="original_filename",
        )

        self.assertEqual(
            [row["file_id"] for row in results],
            [expected_id],
        )

    def test_document_date_prefix_search(self):
        july_id = self.add_file(
            filename="july.pdf",
            document_date="2026-07-24",
        )
        self.add_file(
            filename="june.pdf",
            document_date="2026-06-24",
        )

        results = self.database.search_files(
            self.workspace_one,
            search_text="2026-07",
            search_field="document_date",
        )

        self.assertEqual(
            [row["file_id"] for row in results],
            [july_id],
        )

    def test_detailed_tag_all_and_any(self):
        both_id = self.add_file(
            filename="both.pdf",
            tags=["Finance", "Urgent"],
        )
        finance_id = self.add_file(
            filename="finance.pdf",
            tags=["Finance"],
        )
        self.add_file(
            filename="unrelated.pdf",
            tags=["Legal"],
        )

        all_results = self.database.search_files(
            self.workspace_one,
            filters={
                "tag_names": ["finance", "urgent"],
                "tag_match": "all",
            },
        )

        self.assertEqual(
            [row["file_id"] for row in all_results],
            [both_id],
        )

        any_results = self.database.search_files(
            self.workspace_one,
            filters={
                "tag_names": ["urgent", "legal"],
                "tag_match": "any",
            },
        )

        any_ids = {
            row["file_id"]
            for row in any_results
        }

        self.assertIn(both_id, any_ids)
        self.assertNotIn(finance_id, any_ids)

    def test_detailed_ranges_and_exact_filters(self):
        expected_id = self.add_file(
            filename="expected.pdf",
            document_date="2026-06-15",
            uploaded_by="Daniel",
            file_size=2500,
            tags=["Finance"],
        )
        self.add_file(
            filename="too-small.pdf",
            document_date="2026-06-15",
            uploaded_by="Daniel",
            file_size=100,
            tags=["Finance"],
        )

        results = self.database.search_files(
            self.workspace_one,
            filters={
                "document_date_from": "2026-01-01",
                "document_date_to": "2026-12-31",
                "document_type_id":
                    self.types_one["Invoice"],
                "uploaded_by": "daniel",
                "file_ext": "PDF",
                "file_size_min": 1000,
                "file_size_max": 5000,
                "tag_names": ["finance"],
            },
        )

        self.assertEqual(
            [row["file_id"] for row in results],
            [expected_id],
        )

    def test_archive_date_upper_boundary_includes_whole_day(
        self,
    ):
        expected_id = self.add_file(
            filename="same-day.pdf",
            archived_at="2026-07-24 23:59:59",
        )
        self.add_file(
            filename="next-day.pdf",
            archived_at="2026-07-25 00:00:00",
        )

        results = self.database.search_files(
            self.workspace_one,
            filters={
                "archived_at_from": "2026-07-24",
                "archived_at_to": "2026-07-24",
            },
        )

        self.assertEqual(
            [row["file_id"] for row in results],
            [expected_id],
        )

    def test_pagination_is_stable(self):
        for number in range(5):
            self.add_file(
                filename=f"page-{number}.pdf",
                document_date=f"2026-07-{number + 1:02d}",
            )

        first_page = self.database.search_files(
            self.workspace_one,
            limit=2,
            offset=0,
        )
        second_page = self.database.search_files(
            self.workspace_one,
            limit=2,
            offset=2,
        )

        first_ids = {
            row["file_id"]
            for row in first_page
        }
        second_ids = {
            row["file_id"]
            for row in second_page
        }

        self.assertEqual(len(first_page), 2)
        self.assertEqual(len(second_page), 2)
        self.assertTrue(first_ids.isdisjoint(second_ids))

    def test_get_file_by_id_respects_workspace_and_status(
        self,
    ):
        active_id = self.add_file(
            filename="active-id.pdf",
            tags=["Finance"],
        )
        missing_id = self.add_file(
            filename="missing-id.pdf",
            status="missing",
        )

        active = self.database.get_file_by_id(
            self.workspace_one,
            active_id,
        )
        missing_default = self.database.get_file_by_id(
            self.workspace_one,
            missing_id,
        )
        missing_explicit = self.database.get_file_by_id(
            self.workspace_one,
            missing_id,
            statuses=["missing"],
        )
        wrong_workspace = self.database.get_file_by_id(
            self.workspace_two,
            active_id,
        )

        self.assertEqual(active["tags"], ["Finance"])
        self.assertIsNone(missing_default)
        self.assertEqual(
            missing_explicit["status"],
            "missing",
        )
        self.assertIsNone(wrong_workspace)

    def test_metadata_update_enforces_owner(self):
        file_id = self.add_file(
            filename="editable.pdf",
            tags=["Old"],
        )

        with self.assertRaises(PermissionError):
            self.database.update_file_metadata(
                self.workspace_one,
                file_id,
                acting_user="Alice",
                document_date="2026-08-01",
            )

        updated = self.database.update_file_metadata(
            self.workspace_one,
            file_id,
            acting_user="daniel",
            document_date="2026-08-01",
            document_type_id=self.types_one["Report"],
            tag_names=["Finance", "Reviewed"],
        )

        self.assertEqual(
            updated["document_date"],
            "2026-08-01",
        )
        self.assertEqual(
            updated["document_type"],
            "Report",
        )
        self.assertEqual(
            updated["tags"],
            ["Finance", "Reviewed"],
        )


if __name__ == "__main__":
    unittest.main()
