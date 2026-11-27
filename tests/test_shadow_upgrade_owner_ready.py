"""Windows owner-only push readiness updater safety tests; no live network."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "owner_push_upgrader", ROOT / "upgrade-v1082-owner-ready.py"
)
UP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(UP)


class OwnerReadyUpgradeTests(unittest.TestCase):
    def test_pinned_sources_exact_and_no_secrets_touched(self):
        self.assertEqual(UP.SOURCE_COMMIT,
                         "9cd7c55b62246c33964bfe194e9a085b5153256c")
        self.assertEqual(set(UP.FILES), {
            "v1071/scanner.py", "v1071/push_service.py",
            "v1071/test_backend.py", "v108/local_dispatch.py",
            "v108/preflight_private_push.py", "v108/manage_private_alerts.py",
            "v108/test_local_dispatch.py", "v108/test_manage_private_alerts.py",
        })
        forbidden = {
            "v108/key_store.py", "v1071/fugle.py", "v1071/start_windows.py",
            "v108/install_shadow.py", "v1071/serve.py",
            "v108/shadow_loop.py", "v108/signal_bridge.py",
        }
        self.assertFalse(forbidden.intersection(UP.FILES))
        for name in UP.FILES:
            self.assertEqual(UP.source_url(name),
                             "https://raw.githubusercontent.com/"
                             "lishengchen01/ai-daytrade/" + UP.SOURCE_COMMIT +
                             "/" + name)
        for name in forbidden:
            with self.assertRaises(ValueError):
                UP.source_url(name)
        code = (ROOT / "upgrade-v1082-owner-ready.py").read_text(
            encoding="utf-8")
        self.assertNotIn("WEBPUSH_DERIVED_SIGNAL_ALLOWED=YES", code)
        self.assertNotIn("v1082-private-notify.json", code)
        self.assertNotIn("pairing-token.txt", code)
        self.assertNotIn("vapid-private.pem", code)

    def test_version_marker_and_python_syntax_required(self):
        for name in UP.FILES:
            marker = UP.MARKERS[name]
            valid = ("# " + marker + "\n" + "test_value=True\n" +
                     ("# padding\n" * 8)).encode("utf-8")
            UP.validate_source(name, valid)
            for broken in (b"no=\n", b"short", b"\xff\xfe"):
                with self.assertRaises(ValueError):
                    UP.validate_source(name, broken)

    def test_backup_recovery_replaces_previous_file_and_removes_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            old = base / "v108" / "local_dispatch.py"
            old.parent.mkdir()
            old.write_text("working V1.08.2", encoding="utf-8")
            backup = base / "backup"
            saved = backup / "v108" / "local_dispatch.py"
            saved.parent.mkdir(parents=True)
            saved.write_bytes(old.read_bytes())
            old.write_text("new changed code", encoding="utf-8")
            new = base / "v108" / "manage_private_alerts.py"
            new.write_text("new file", encoding="utf-8")
            UP._restore(base, backup, [
                "v108/local_dispatch.py", "v108/manage_private_alerts.py"
            ])
            self.assertEqual(old.read_text(encoding="utf-8"),
                             "working V1.08.2")
            self.assertFalse(new.exists())

    def test_wrong_scheduled_task_path_blocks_upgrade(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(UP, "schtasks", return_value=(
                0, "<Command>C:/wrong/start_hidden.py</Command>"
            )):
                with self.assertRaises(RuntimeError):
                    UP.ensure_same_task(Path(tmp))


if __name__ == "__main__":
    unittest.main()
