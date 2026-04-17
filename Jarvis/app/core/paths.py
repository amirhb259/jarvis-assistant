from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
APP_DIR = ROOT_DIR / "app"
CONFIG_DIR = ROOT_DIR / "config"
DATA_DIR = ROOT_DIR / "data"
LOG_DIR = ROOT_DIR / "logs"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
APP_INDEX_FILE = DATA_DIR / "app_index.json"


def ensure_runtime_dirs() -> None:
    for directory in (CONFIG_DIR, DATA_DIR, LOG_DIR, SCREENSHOT_DIR):
        directory.mkdir(parents=True, exist_ok=True)
