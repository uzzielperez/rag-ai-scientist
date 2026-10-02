import tempfile
import unittest
from pathlib import Path

import yaml

from rag_ai_scientist.project_paths import resolve_project_data_dir


class ResolveProjectDataDirTests(unittest.TestCase):
    def test_defaults_to_vendor_neutral_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(resolve_project_data_dir(root), root / ".rag-ai-scientist")

    def test_uses_configured_relative_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_dir = root / "configs"
            config_dir.mkdir()
            (config_dir / "references.yaml").write_text(
                yaml.safe_dump({"indexing": {"data_dir": "cache/rag"}}),
                encoding="utf-8",
            )
            self.assertEqual(resolve_project_data_dir(root), root / "cache" / "rag")

    def test_preserves_existing_cursor_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy_index = root / ".cursor" / "rag_db"
            legacy_index.mkdir(parents=True)
            self.assertEqual(resolve_project_data_dir(root), root / ".cursor")

    def test_prefers_vendor_neutral_index_if_both_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cursor" / "rag_db").mkdir(parents=True)
            (root / ".rag-ai-scientist" / "rag_db").mkdir(parents=True)
            self.assertEqual(resolve_project_data_dir(root), root / ".rag-ai-scientist")


if __name__ == "__main__":
    unittest.main()