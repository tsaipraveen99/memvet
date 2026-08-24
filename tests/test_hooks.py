import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from memvet.hooks import HookError, install, settings_path, status, uninstall

OTHER = {"hooks": [{"type": "command", "command": "someone-elses-tool"}]}


class HookTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def read(self) -> dict:
        return json.loads(settings_path(self.repo).read_text(encoding="utf-8"))

    def test_install_writes_the_session_start_hook(self) -> None:
        changed, path = install(self.repo)
        self.assertTrue(changed)
        self.assertTrue(path.exists())
        entries = self.read()["hooks"]["SessionStart"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["hooks"][0]["command"], "memvet context")
        self.assertTrue(status(self.repo))

    def test_install_is_idempotent(self) -> None:
        install(self.repo)
        changed, _ = install(self.repo)
        self.assertFalse(changed)
        self.assertEqual(len(self.read()["hooks"]["SessionStart"]), 1)

    def test_install_preserves_unrelated_settings_and_hooks(self) -> None:
        settings_path(self.repo).parent.mkdir(parents=True)
        settings_path(self.repo).write_text(
            json.dumps(
                {
                    "model": "opus",
                    "hooks": {"SessionStart": [OTHER], "Stop": [OTHER]},
                }
            ),
            encoding="utf-8",
        )
        install(self.repo)
        data = self.read()
        self.assertEqual(data["model"], "opus")
        self.assertEqual(data["hooks"]["Stop"], [OTHER])
        self.assertEqual(len(data["hooks"]["SessionStart"]), 2)
        self.assertIn(OTHER, data["hooks"]["SessionStart"])

    def test_uninstall_removes_only_our_entry(self) -> None:
        settings_path(self.repo).parent.mkdir(parents=True)
        settings_path(self.repo).write_text(
            json.dumps({"hooks": {"SessionStart": [OTHER]}}), encoding="utf-8"
        )
        install(self.repo)
        changed, _ = uninstall(self.repo)
        self.assertTrue(changed)
        self.assertEqual(self.read()["hooks"]["SessionStart"], [OTHER])
        self.assertFalse(status(self.repo))

    def test_uninstall_drops_the_event_when_nothing_else_remains(self) -> None:
        install(self.repo)
        uninstall(self.repo)
        self.assertNotIn("hooks", self.read())

    def test_uninstall_on_a_clean_repo_is_not_an_error(self) -> None:
        changed, _ = uninstall(self.repo)
        self.assertFalse(changed)
        self.assertFalse(status(self.repo))

    def test_status_is_false_before_install(self) -> None:
        self.assertFalse(status(self.repo))

    def test_invalid_settings_file_is_reported(self) -> None:
        settings_path(self.repo).parent.mkdir(parents=True)
        settings_path(self.repo).write_text("{not json", encoding="utf-8")
        with self.assertRaises(HookError):
            install(self.repo)


if __name__ == "__main__":
    unittest.main()
