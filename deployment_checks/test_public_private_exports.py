"""The active branch must contain no private CV/profile exports."""
import unittest

from check_public_private_exports import private_export_path, violations


class PublicExportContainmentTests(unittest.TestCase):
    def test_former_private_exports_are_now_prohibited(self):
        for path in (
            "cv/sample_private.pdf",
            "cv_text.txt",
            "val_extraction.json",
            "val_profile.json",
            "val_profile_fixed.json",
        ):
            with self.subTest(path=path):
                self.assertTrue(private_export_path(path))
                self.assertEqual(len(violations({path: "0" * 40})), 1)

    def test_new_private_exports_are_blocked(self):
        for path in (
            "cv/another_person.pdf",
            "cv_text_new.txt",
            "val_profile_backup.json",
            "val_extraction_2.json",
            "my_resume.docx",
        ):
            with self.subTest(path=path):
                self.assertTrue(private_export_path(path))
                self.assertTrue(violations({path: "0" * 40}))

    def test_regular_files_are_allowed(self):
        for path in ("README.md", "LICENSE", "tests/test_cv.py", ".env.example"):
            with self.subTest(path=path):
                self.assertFalse(private_export_path(path))
                self.assertEqual(violations({path: "0" * 40}), [])

    def test_empty_tree_is_clean(self):
        self.assertEqual(violations({}), [])
