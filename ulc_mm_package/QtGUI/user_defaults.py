"""Persist user choices (e.g. the last selected study) between runs of the GUI."""

import json
from pathlib import Path

# Stored next to this file (not the cwd) so it's found regardless of where the GUI is launched from.
# JSON rather than shelve, since shelve's dbm backend differs between macOS, Windows, and Raspbian.
USER_DEFAULTS_FILE = Path(__file__).resolve().parent / ".gui_defaults.json"
STUDY_SELECTION_KEY = "default_study"


def load_user_defaults() -> dict:
    try:
        with open(USER_DEFAULTS_FILE, "r") as f:
            defaults = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return defaults if isinstance(defaults, dict) else {}


def save_user_defaults(defaults: dict) -> None:
    with open(USER_DEFAULTS_FILE, "w") as f:
        json.dump(defaults, f, indent=2)


def save_user_default(key: str, value) -> None:
    defaults = load_user_defaults()
    defaults[key] = value
    save_user_defaults(defaults)
