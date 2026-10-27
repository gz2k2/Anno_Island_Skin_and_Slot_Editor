from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
APP_CODE_DIR = ROOT_DIR / "app"

if str(APP_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(APP_CODE_DIR))

from main import App


if __name__ == "__main__":
    App().mainloop()
