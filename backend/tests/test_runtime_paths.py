import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_data_dir_prefers_explicit_override(self) -> None:
        with patch.dict(os.environ, {"DAILYIQ_DATA_DIR": "~/dailyiq-test"}, clear=False):
            self.assertEqual(runtime_paths.data_dir(), Path("~/dailyiq-test").expanduser())

    def test_default_app_data_dir_windows(self) -> None:
        with patch.object(sys, "platform", "win32"):
            with patch.dict(os.environ, {"APPDATA": r"C:\Users\doggy\AppData\Roaming"}, clear=True):
                self.assertEqual(
                    runtime_paths._default_app_data_dir(),
                    Path(r"C:\Users\doggy\AppData\Roaming") / runtime_paths.APP_ID,
                )

    def test_default_app_data_dir_macos(self) -> None:
        with patch.object(sys, "platform", "darwin"):
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(Path, "home", return_value=Path("/Users/doggy")):
                    self.assertEqual(
                        runtime_paths._default_app_data_dir(),
                        Path("/Users/doggy/Library/Application Support") / runtime_paths.APP_ID,
                    )

    def test_default_app_data_dir_linux_xdg(self) -> None:
        with patch.object(sys, "platform", "linux"):
            with patch.dict(os.environ, {"XDG_DATA_HOME": "/tmp/xdg-data"}, clear=True):
                self.assertEqual(
                    runtime_paths._default_app_data_dir(),
                    Path("/tmp/xdg-data") / runtime_paths.APP_ID,
                )

    def test_default_app_data_dir_linux_fallback(self) -> None:
        with patch.object(sys, "platform", "linux"):
            with patch.dict(os.environ, {}, clear=True):
                with patch.object(Path, "home", return_value=Path("/home/doggy")):
                    self.assertEqual(
                        runtime_paths._default_app_data_dir(),
                        Path("/home/doggy/.local/share") / runtime_paths.APP_ID,
                    )


if __name__ == "__main__":
    unittest.main()
