"""Offline, cross-platform safety checks for the Windows V1.08.1 updater."""
import importlib.util
import pathlib
import tempfile
import unittest
from unittest.mock import patch


ROOT = pathlib.Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "shadow_updater", ROOT / "upgrade-v1081-shadow.py")
UP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UP)


class UpgradeTests(unittest.TestCase):
    def test_pinned_sane_sources_and_narrow_scope(self):
        self.assertEqual(len(UP.SOURCE_COMMIT), 40)
        self.assertTrue(all(c in "0123456789abcdef" for c in UP.SOURCE_COMMIT))
        self.assertEqual(set(UP.FILES), {
            "v1071/audit_live.py", "v108/shadow_loop.py",
            "v108/status.py", "v108/signal_bridge.py",
            "v108/test_signal_bridge.py",
        })
        for name in UP.FILES:
            self.assertTrue(UP.source_url(name).startswith(
                "https://raw.githubusercontent.com/lishengchen01/ai-daytrade/"
                + UP.SOURCE_COMMIT + "/"))
        with self.assertRaises(ValueError):
            UP.source_url("v1071/push_service.py")

    def test_downloaded_code_must_parse_and_have_version_marker(self):
        for name in UP.FILES:
            marker = UP.MARKERS[name]
            UP.validate_source(name, (marker + " = True\n").encode("utf-8"))
            with self.assertRaises(ValueError):
                UP.validate_source(name, b"bad=\n")
            with self.assertRaises(ValueError):
                UP.validate_source(name, b"short")
            with self.assertRaises(ValueError):
                UP.validate_source(name, b"x=\xff\xfe\n")

    def test_rollback_recovers_existing_files_and_removes_new_file(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            old = base / "v108" / "shadow_loop.py"
            old.parent.mkdir()
            old.write_text("previous-safe-version", encoding="utf-8")
            backup = base / "backup"
            saved = backup / "v108" / "shadow_loop.py"
            saved.parent.mkdir(parents=True)
            saved.write_bytes(old.read_bytes())
            old.write_text("new-code-to-rollback", encoding="utf-8")
            newly_added = base / "v108" / "signal_bridge.py"
            newly_added.write_text("new", encoding="utf-8")
            UP._restore(base, backup, ["v108/shadow_loop.py",
                                       "v108/signal_bridge.py"])
            self.assertEqual(old.read_text(encoding="utf-8"),
                             "previous-safe-version")
            self.assertFalse(newly_added.exists())

    def test_task_path_mismatch_fails_closed_without_modifying_files(self):
        with tempfile.TemporaryDirectory() as td:
            base = pathlib.Path(td)
            with patch.object(UP, "schtasks",
                              return_value=(0, "<Command>another-root/start_hidden.py</Command>")):
                with self.assertRaises(RuntimeError):
                    UP.ensure_same_task(base)

    def test_scope_has_no_production_push_service_or_secrets(self):
        content = (ROOT / "upgrade-v1081-shadow.py").read_text(encoding="utf-8")
        for forbidden in ("WEBPUSH_DERIVED_SIGNAL_ALLOWED=YES",
                          "push_service.deliver(", "fugle-key-v108.dpapi\", \"w"):
            self.assertNotIn(forbidden, content)


if __name__ == "__main__":
    unittest.main()
