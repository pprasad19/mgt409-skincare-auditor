"""Locate and load the .env file.

Search order, nearest first:

  1. the repo folder
  2. one folder above the repo
  3. two folders above

The course requires 1 and 2. Step 3 exists because during development this
repo sits two levels below the class folder that holds the key, and copying a
secret around to satisfy a search path is worse than widening the search.
Graders placing .env one level up hit step 2 and never reach it.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent

SEARCH_PATHS = [
    REPO_ROOT / ".env",
    REPO_ROOT.parent / ".env",
    REPO_ROOT.parent.parent / ".env",
]

_loaded: Path | None = None


def load_env() -> Path | None:
    """Load the first .env found. Idempotent; returns the file used."""
    global _loaded
    if _loaded is not None:
        return _loaded

    for candidate in SEARCH_PATHS:
        if candidate.is_file():
            load_dotenv(candidate)
            _loaded = candidate
            return _loaded
    return None


def require(name: str) -> str:
    """Return an environment variable or fail with a message that says what to do."""
    load_env()
    value = os.environ.get(name)
    if not value:
        searched = "\n  ".join(str(p) for p in SEARCH_PATHS)
        raise RuntimeError(
            f"{name} is not set.\n"
            f"Put it in a .env file at one of:\n  {searched}\n"
            f"See .env.example for the format."
        )
    return value
