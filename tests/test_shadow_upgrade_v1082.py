"""Offline Windows upgrade safety regression: V1.08.1 -> V1.08.2."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "shadow_updater_v1082", ROOT / "upgrade-v1082-shadow.py"
)
UP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UP)


class UpgradeV1082Tests(unittest.TestCase):
    def test_exact_pinned_sources(self):
        self.assertEqual(len(UP.SOURCE_COMMIT), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in UP.SOURCE_COMMIT))
        self.assertEqual(set(UP.FILES), {
            "v108/shadow_loop.py", "v108/status.py",
            "v108/local_dispatch.py", "v108/test_local_dispatch.py",
            "v108/preflight_private_push.py",
        })
        for name in UP.FILES:
            self.assertIn("/" + UP.SOURCE_COMMIT + "/", UP.source_url(name))
        for forbidden in ("v1071/push_service.py", "v108/key_store.py",
                          "v1071/fugle.py", "v108/install_shadow.py"):
            with self.assertRaises(ValueError):
                UP.source_url(forbidden)

    def test_source_syntax_and_version_marker_required(self):
        for name in UP.FILES:
            marker = UP.MARKERS[name]
            valid = ("safe_fixture=True\n# " + marker +
                     "\n" + ("# padding line\n" * 8)).encode("utf-8")
            UP.validate_source(name, valid)
            for broken in (b"not-python=\n", b"missing-marker", b"\xff\xfe"):
                with self.assertRaises(ValueError):
                    UP.validate_source(name, broken)

    def test_restore_replaces_old_and_removes_new(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            old = root / "v108" / "shadow_loop.py"
            old.parent.mkdir()
            old.write_text("previous verified", encoding="utf-8")
            backup = root / "backup"
            saved = backup / "v108" / "shadow_loop.py"
            saved.parent.mkdir(parents=True)
            saved.write_bytes(old.read_bytes())
            old.write_text("new changed", encoding="utf-8")
            new = root / "v108" / "local_dispatch.py"
            new.write_text("new file", encoding="utf-8")
            UP._restore(root, backup, [
                "v108/shadow_loop.py", "v108/local_dispatch.py",
            ])
            self.assertEqual(old.read_text(encoding="utf-8"), "previous verified")
            self.assertFalse(new.exists())

    def test_wrong_scheduled_task_path_fails_closed(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(UP, "schtasks", return_value=(
                0, "<Command>C:/other/start_hidden.py</Command>"
            )):
                with self.assertRaises(RuntimeError):
                    UP.ensure_same_task(pathlib.Path(td))

    def test_updater_does_not_opt_in_live_push(self):
        source = (ROOT / "upgrade-v1082-shadow.py").read_text(encoding="utf-8")
        self.assertNotIn('WEBPUSH_DERIVED_SIGNAL_ALLOWED"] = "YES"', source)
        self.assertNotIn("push_service.deliver(", source)
        self.assertNotIn("vapid-private.pem", source)
        self.assertNotIn("v1082-private-notify.json", source)


if __name__ == "__main__":
    unittest.main()
