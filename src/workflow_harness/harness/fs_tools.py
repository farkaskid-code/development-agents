"""
Filesystem access scoped to a single root directory.

This is the actual enforcement of the "Architect never touches src/" rule —
not a prompt instruction, a structural one. ScopedFS refuses, at the code
level, to read or write anything outside the directory it was constructed
with, regardless of what the model requests (`../src/main.py`, absolute
paths, symlink tricks, etc. are all rejected the same way).
"""

from pathlib import Path


class PathEscapeError(ValueError):
    pass


class ScopedFS:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, rel_path: str) -> Path:
        # Reject absolute paths outright — everything is relative to root.
        candidate = (self.root / rel_path).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            raise PathEscapeError(
                f"Path '{rel_path}' resolves outside the allowed directory "
                f"({self.root}). Refusing."
            )
        return candidate

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        if not target.exists():
            raise FileNotFoundError(f"{path} does not exist in {self.root}")
        return target.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> None:
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def exists(self, path: str) -> bool:
        try:
            return self._resolve(path).exists()
        except PathEscapeError:
            return False
