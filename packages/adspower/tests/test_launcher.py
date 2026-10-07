import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mrfactory.adspower import launcher


class TestLauncher(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        startfile = mock.patch("mrfactory.adspower.launcher.os.startfile", create=True)
        self.startfile = startfile.start()
        self.addCleanup(startfile.stop)

    def _install_at(self, root: Path) -> Path:
        exe = root / launcher.ADSPOWER_EXE
        exe.parent.mkdir(parents=True)
        exe.touch()
        return exe

    def test_finds_per_machine_install(self):
        exe = self._install_at(self.root)
        with mock.patch.dict(os.environ, {"ProgramFiles": str(self.root)}):
            self.assertEqual(launcher.open_adspower(), exe)
        self.startfile.assert_called_once_with(exe)

    def test_finds_per_user_install(self):
        exe = self._install_at(self.root / "Programs")
        env = {"ProgramFiles": str(self.root / "none"), "LOCALAPPDATA": str(self.root)}
        with mock.patch.dict(os.environ, env):
            self.assertEqual(launcher.find_adspower(), exe)

    def test_explicit_path_wins(self):
        exe = self.root / "custom.exe"
        exe.touch()
        self.assertEqual(launcher.open_adspower(exe), exe)

    def test_missing_raises_and_does_not_launch(self):
        env = {"ProgramFiles": str(self.root), "ProgramFiles(x86)": str(self.root), "LOCALAPPDATA": str(self.root)}
        with mock.patch.dict(os.environ, env), self.assertRaises(FileNotFoundError):
            launcher.open_adspower()
        self.startfile.assert_not_called()


if __name__ == "__main__":
    unittest.main()
