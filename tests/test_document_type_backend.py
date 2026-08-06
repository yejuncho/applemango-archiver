import tempfile
import unittest
from pathlib import Path

from applemango_dms.db.sqlite import ArchiveDatabase


class DocumentTypeBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)

        self.share_path = self.root / "share"
        self.share_path.mkdir(parents=True, exist_ok=True)

        self.database = ArchiveDatabase(
            self.root / "archive.db"
        )
        workspace_row = self.database.designate_workspace(
            "Workspace A",
            self.share_path,
        )
        self.workspace_id = int(workspace_row["id"])

    def tearDown(self):
        self.database = None
        self.temp_directory.cleanup()

    def _active_rows(self):
        return self.database.list_document_types(
            self.workspace_id,
            include_inactive=False,
        )

    def _all_rows(self):
        return self.database.list_document_types(
            self.workspace_id,
            include_inactive=True,
        )

    def _active_names(self):
        return [
            row["name"]
            for row in self._active_rows()
        ]

    def _inactive_names(self):
        return [
            row["name"]
            for row in self._all_rows()
            if not row["is_active"]
        ]

    def _id_by_name(self):
        return {
            row["name"]: int(row["id"])
            for row in self._all_rows()
        }

    def _insert_active_file(
        self,
        *,
        document_type_id,
        archived_filename="used-by-active-file.pdf",
    ):
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
                    int(document_type_id),
                    "Tester",
                    archived_filename,
                    archived_filename,
                    str(Path("archive") / archived_filename),
                    "2026-08-06",
                    ".pdf",
                    100,
                    "active",
                ),
            )

            return int(cursor.lastrowid)

    def test_a_new_workspace_lists_only_fallback(self):
        self.assertEqual(
            self._active_names(),
            ["기타"],
        )

    def test_b_create_types_appends_after_fallback(self):
        self.database.create_document_type(
            self.workspace_id,
            "Invoices",
        )
        self.database.create_document_type(
            self.workspace_id,
            "Reports",
        )
        self.database.create_document_type(
            self.workspace_id,
            "Contracts",
        )

        self.assertEqual(
            self._active_names(),
            [
                "기타",
                "Invoices",
                "Reports",
                "Contracts",
            ],
        )

    def test_c_rename_preserves_id_and_file_references(self):
        created = self.database.create_document_type(
            self.workspace_id,
            "Reports",
        )
        report_id = int(created["id"])

        file_id = self._insert_active_file(
            document_type_id=report_id,
            archived_filename="report-linked.pdf",
        )

        renamed = self.database.rename_document_type(
            self.workspace_id,
            report_id,
            "Meeting Reports",
        )

        self.assertEqual(
            int(renamed["id"]),
            report_id,
        )

        record = self.database.get_file_by_id(
            self.workspace_id,
            file_id,
        )

        self.assertIsNotNone(record)
        self.assertEqual(
            record["document_type"],
            "Meeting Reports",
        )

    def test_d_deactivate_moves_type_to_inactive_list(self):
        self.database.create_document_type(
            self.workspace_id,
            "Invoices",
        )
        self.database.create_document_type(
            self.workspace_id,
            "Reports",
        )
        contracts = self.database.create_document_type(
            self.workspace_id,
            "Contracts",
        )

        self.database.deactivate_document_type(
            self.workspace_id,
            int(contracts["id"]),
        )

        self.assertNotIn(
            "Contracts",
            self._active_names(),
        )
        self.assertIn(
            "Contracts",
            self._inactive_names(),
        )

    def test_e_reactivate_preserves_id_and_sort_order(self):
        contracts = self.database.create_document_type(
            self.workspace_id,
            "Contracts",
        )

        deactivated = self.database.deactivate_document_type(
            self.workspace_id,
            int(contracts["id"]),
        )

        reactivated = self.database.reactivate_document_type(
            self.workspace_id,
            int(contracts["id"]),
        )

        self.assertEqual(
            int(reactivated["id"]),
            int(deactivated["id"]),
        )
        self.assertEqual(
            int(reactivated["sort_order"]),
            int(deactivated["sort_order"]),
        )

    def test_f_deactivate_fallback_fails(self):
        fallback = self._active_rows()[0]

        with self.assertRaises(ValueError):
            self.database.deactivate_document_type(
                self.workspace_id,
                int(fallback["id"]),
            )

    def test_g_deactivate_fails_when_active_file_references_type(self):
        contracts = self.database.create_document_type(
            self.workspace_id,
            "Contracts",
        )

        self._insert_active_file(
            document_type_id=int(contracts["id"]),
            archived_filename="contracts-active-ref.pdf",
        )

        with self.assertRaisesRegex(
            ValueError,
            "^Document type is still used by active files\\.$",
        ):
            self.database.deactivate_document_type(
                self.workspace_id,
                int(contracts["id"]),
            )

    def test_h_reorder_persists_requested_order(self):
        self.database.create_document_type(
            self.workspace_id,
            "Invoices",
        )
        reports = self.database.create_document_type(
            self.workspace_id,
            "Reports",
        )
        self.database.create_document_type(
            self.workspace_id,
            "Contracts",
        )

        self.database.rename_document_type(
            self.workspace_id,
            int(reports["id"]),
            "Meeting Reports",
        )

        ids = self._id_by_name()

        reordered_rows = self.database.reorder_document_types(
            self.workspace_id,
            [
                int(ids["Contracts"]),
                int(ids["Invoices"]),
                int(ids["Meeting Reports"]),
                int(ids["기타"]),
            ],
        )

        self.assertEqual(
            [row["name"] for row in reordered_rows],
            [
                "Contracts",
                "Invoices",
                "Meeting Reports",
                "기타",
            ],
        )

        # Re-query to confirm persisted order after reload.
        self.assertEqual(
            self._active_names(),
            [
                "Contracts",
                "Invoices",
                "Meeting Reports",
                "기타",
            ],
        )

    def test_reserved_names_cannot_be_created_manually(self):
        with self.assertRaises(ValueError):
            self.database.create_document_type(
                self.workspace_id,
                "기타",
            )

        with self.assertRaises(ValueError):
            self.database.create_document_type(
                self.workspace_id,
                "미분류",
            )

    def test_i_move_up_and_down_persists_for_active_list(self):
        self.database.create_document_type(
            self.workspace_id,
            "Invoices",
        )
        reports = self.database.create_document_type(
            self.workspace_id,
            "Reports",
        )
        self.database.create_document_type(
            self.workspace_id,
            "Contracts",
        )
        dormant_one = self.database.create_document_type(
            self.workspace_id,
            "Dormant 1",
        )
        dormant_two = self.database.create_document_type(
            self.workspace_id,
            "Dormant 2",
        )

        self.database.deactivate_document_type(
            self.workspace_id,
            int(dormant_one["id"]),
        )
        self.database.deactivate_document_type(
            self.workspace_id,
            int(dormant_two["id"]),
        )

        reports_id = int(reports["id"])
        ids_before = self._id_by_name()
        inactive_before = self._inactive_names()

        moved_up = self.database.move_document_type_up(
            self.workspace_id,
            reports_id,
        )

        self.assertEqual(
            int(moved_up["id"]),
            reports_id,
        )

        self.assertEqual(
            self._active_names(),
            [
                "기타",
                "Reports",
                "Invoices",
                "Contracts",
            ],
        )
        self.assertEqual(
            self._inactive_names(),
            inactive_before,
        )

        moved_down = self.database.move_document_type_down(
            self.workspace_id,
            reports_id,
        )

        self.assertEqual(
            int(moved_down["id"]),
            reports_id,
        )

        self.assertEqual(
            self._active_names(),
            [
                "기타",
                "Invoices",
                "Reports",
                "Contracts",
            ],
        )
        self.assertEqual(
            self._inactive_names(),
            inactive_before,
        )
        self.assertEqual(
            self._id_by_name(),
            ids_before,
        )

    def test_j_inactive_move_does_not_change_active_order(self):
        self.database.create_document_type(
            self.workspace_id,
            "A",
        )
        b_row = self.database.create_document_type(
            self.workspace_id,
            "B",
        )
        c_row = self.database.create_document_type(
            self.workspace_id,
            "C",
        )

        self.database.deactivate_document_type(
            self.workspace_id,
            int(b_row["id"]),
        )
        self.database.deactivate_document_type(
            self.workspace_id,
            int(c_row["id"]),
        )

        self.assertEqual(
            self._inactive_names(),
            ["B", "C"],
        )

        active_before = self._active_names()
        ids_before = self._id_by_name()

        moved = self.database.move_document_type_down(
            self.workspace_id,
            int(b_row["id"]),
        )

        self.assertEqual(
            int(moved["id"]),
            int(b_row["id"]),
        )

        self.assertEqual(
            self._inactive_names(),
            ["C", "B"],
        )
        self.assertEqual(
            self._active_names(),
            active_before,
        )
        self.assertEqual(
            self._id_by_name(),
            ids_before,
        )

    def test_k_move_boundaries_are_noop_for_active_and_inactive(self):
        active_row = self.database.create_document_type(
            self.workspace_id,
            "A",
        )
        b_row = self.database.create_document_type(
            self.workspace_id,
            "B",
        )
        c_row = self.database.create_document_type(
            self.workspace_id,
            "C",
        )

        self.database.deactivate_document_type(
            self.workspace_id,
            int(b_row["id"]),
        )
        self.database.deactivate_document_type(
            self.workspace_id,
            int(c_row["id"]),
        )

        active_before = self._active_names()
        inactive_before = self._inactive_names()

        active_top_id = self._active_rows()[0]["id"]
        active_bottom_id = self._active_rows()[-1]["id"]
        inactive_top_id = [
            row["id"]
            for row in self._all_rows()
            if not row["is_active"]
        ][0]
        inactive_bottom_id = [
            row["id"]
            for row in self._all_rows()
            if not row["is_active"]
        ][-1]

        no_op_top_active = self.database.move_document_type_up(
            self.workspace_id,
            int(active_top_id),
        )
        no_op_bottom_active = self.database.move_document_type_down(
            self.workspace_id,
            int(active_bottom_id),
        )
        no_op_top_inactive = self.database.move_document_type_up(
            self.workspace_id,
            int(inactive_top_id),
        )
        no_op_bottom_inactive = self.database.move_document_type_down(
            self.workspace_id,
            int(inactive_bottom_id),
        )

        self.assertEqual(
            int(no_op_top_active["id"]),
            int(active_top_id),
        )
        self.assertEqual(
            int(no_op_bottom_active["id"]),
            int(active_bottom_id),
        )
        self.assertEqual(
            int(no_op_top_inactive["id"]),
            int(inactive_top_id),
        )
        self.assertEqual(
            int(no_op_bottom_inactive["id"]),
            int(inactive_bottom_id),
        )

        self.assertEqual(
            self._active_names(),
            active_before,
        )
        self.assertEqual(
            self._inactive_names(),
            inactive_before,
        )
        self.assertEqual(
            int(active_row["id"]),
            self._id_by_name()["A"],
        )


if __name__ == "__main__":
    unittest.main()
