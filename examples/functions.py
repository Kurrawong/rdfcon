import subprocess
from datetime import date
from uuid import uuid4


def uuid():
    return uuid4()


def get_genre(category: str) -> str:
    genre_map = {"a": "Arts", "b": "Business", "c": "Culture"}
    letter = category[-1].lower()
    genre = genre_map[letter]
    return genre


def get_current_date() -> str:
    return date.today().isoformat()


def get_short_commit_hash() -> str:
    cmd = "git rev-parse --short HEAD".split()
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    short_hash = result.stdout.strip()
    return short_hash
