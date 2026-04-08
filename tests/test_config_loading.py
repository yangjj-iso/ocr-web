import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import _load_local_env_file, _mask_secret


class ConfigLoadingTests(unittest.TestCase):
    def test_env_file_overrides_existing_process_variable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("MINIMAX_API_KEY=from-env-file\n", encoding="utf-8")

            with patch.dict(os.environ, {"MINIMAX_API_KEY": "from-process"}, clear=False):
                _load_local_env_file(env_path)
                self.assertEqual(os.environ["MINIMAX_API_KEY"], "from-env-file")

    def test_env_file_does_not_clear_missing_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text("MINIMAX_ENABLED=true\n", encoding="utf-8")

            with patch.dict(os.environ, {"REDIS_URL": "redis://existing"}, clear=False):
                _load_local_env_file(env_path)
                self.assertEqual(os.environ["REDIS_URL"], "redis://existing")
                self.assertEqual(os.environ["MINIMAX_ENABLED"], "true")

    def test_secret_mask_avoids_full_key_logging(self):
        self.assertEqual(_mask_secret(""), "<empty>")
        self.assertEqual(_mask_secret("short-secret"), "********")
        self.assertEqual(_mask_secret("sk-cp-abcdefghijklmnopqrstuvwxyz123456"), "sk-cp-ab...123456")


if __name__ == "__main__":
    unittest.main()
