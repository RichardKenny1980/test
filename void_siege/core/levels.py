"""The campaign: level order, and the stars the player has earned, saved between sessions."""
import json
import os

from .data import load

LEVELS = ("map01", "map02", "map03", "map04", "map05", "map06")
KIND_LABELS = {"pads": "BUILD PADS", "open": "OPEN GROUND", "maze": "BUILD THE MAZE"}


def info(index):
    m = load(LEVELS[index])
    return {"id": LEVELS[index], "name": m["name"], "kind": m.get("kind", "pads"), "waves": len(m["waves"])}


def save_dir():
    """Where progress is kept: the app's private storage on Android, a dot folder elsewhere."""
    return (os.environ.get("VOID_SIEGE_SAVE_DIR") or os.environ.get("ANDROID_PRIVATE")
            or os.path.join(os.path.expanduser("~"), ".void_siege"))


class Progress:
    """Best stars per level. Level 1 is always open; clearing a level opens the next."""

    def __init__(self, path=None):
        self.path = path or os.path.join(save_dir(), "progress.json")
        self.stars = {}
        try:
            with open(self.path, encoding="utf-8") as f:
                self.stars = {k: int(v) for k, v in json.load(f).get("stars", {}).items()}
        except (OSError, ValueError, AttributeError):
            pass  # no save yet, or an unreadable one: start fresh

    def best(self, index):
        return self.stars.get(LEVELS[index], 0)

    def unlocked(self, index):
        return index == 0 or self.best(index - 1) > 0

    def record(self, index, stars):
        if stars <= self.best(index):
            return
        self.stars[LEVELS[index]] = stars
        try:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump({"stars": self.stars}, f)
        except OSError:
            pass  # read-only storage (some browsers): progress lasts for this session only
