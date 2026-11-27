"""Entry point for pythonw.exe in Windows Task Scheduler.

Absolute project path setup is required because schtasks defaults to system32.
"""
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from v108.shadow_loop import run_forever

if __name__ == "__main__":
    run_forever()
