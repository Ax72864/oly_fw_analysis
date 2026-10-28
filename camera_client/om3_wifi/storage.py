"""Minimal run logging for OM-3 discovery; no Linux flock dependency."""
from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def save_json(path, obj):
    path = Path(path)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + "\n")


class Run:
    def __init__(self, root, command):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.path = Path(tempfile.mkdtemp(prefix=f"{stamp}-{command}-", dir=root))
        self.log = (self.path / "transcript.jsonl").open("x", encoding="utf-8")

    def record(self, event):
        self.log.write(json.dumps({"time": now(), **event}, allow_nan=False) + "\n")
        self.log.flush()

    def save(self, name, obj):
        save_json(self.path / name, obj)

    def close(self):
        self.log.close()
