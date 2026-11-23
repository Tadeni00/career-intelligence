"""Regression checks for public-export containment (no private contents opened)."""
import unittest

from check_public_private_exports import LEGACY_BLOBS, private_export_path, violations


class PublicExportContainmentTests(unittest.TestCase):
    def test_known_legacy_paths_are_detected(self):
        for path in LEGACY_BLOBS:
            with self.subTest(path=path):
                self.assertTrue(private_export_path(path))

    def test_new_private_exports_are_blocked(self):
        examples = (
            "cv/another_person.pdf",
            "cv_text_new.txt",
            "val_profile_backup.json",
            "val_extraction_2.json",
            "my_resume.docx",
        )
        for path in examples:
            with self.subTest(path=path):
                self.assertTrue(private_export_path(path))
                self.assertTrue(violations({path: "0" * 40}))

    def test_changed_legacy_export_is_blocked(self):
        path = next(iter(LEGACY_BLOBS))
        self.assertTrue(violations({path: "0" * 40}))

    def test_unchanged_legacy_is_not_mistaken_for_remediation(self):
        self.assertEqual(violations(LEGACY_BLOBS), [])

    def test_ordinary_project_files_allowed(self):
        for path in ("README.md", "docs/PERSONAL_RELEASE.md", "tests/test_cv.py", ".env.example"):
            with self.subTest(path=path):
                self.assertFalse(private_export_path(path))
                self.assertEqual(violations({path: "0" * 40}), [])
