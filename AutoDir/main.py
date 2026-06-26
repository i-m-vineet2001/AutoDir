

# from pathlib import Path
# from typing import Dict, List

# def create_structure(base_path: Path, structure: Dict) -> List[str]:
#     """Recursively create folders/files and return success messages."""
#     messages = []
#     base_path.mkdir(exist_ok=True, parents=True)
#     for name, content in structure.items():
#         item_path = base_path / name
#         if isinstance(content, dict):
#             item_path.mkdir(exist_ok=True, parents=True)
#             messages.append(f"📁 Created folder: {item_path}")
#             messages.extend(create_structure(item_path, content))
#         elif content is None:
#             item_path.touch(exist_ok=True)
#             messages.append(f"📄 Created file: {item_path}")
#     return messages







"""
main.py — AutoDir v2
Directory creation engine: dry-run, conflict handling, rollback.
"""

import json
import shutil
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class CreationEntry:
    path: str
    kind: str  # "folder" | "file"
    status: str  # "created" | "skipped" | "error" | "dry-run"
    message: str = ""

    def icon(self) -> str:
        icons = {
            ("folder", "created"): "📁",
            ("folder", "skipped"): "📂",
            ("folder", "dry-run"): "🗂️",
            ("folder", "error"): "❌",
            ("file", "created"): "📄",
            ("file", "skipped"): "⏩",
            ("file", "dry-run"): "📋",
            ("file", "error"): "❌",
        }
        return icons.get((self.kind, self.status), "•")

    def label(self) -> str:
        tail = f" — {self.message}" if self.message else ""
        return f"{self.icon()} [{self.status.upper()}] {self.path}{tail}"


@dataclass
class CreationResult:
    log: list = field(default_factory=list)
    created_paths: list = field(default_factory=list)
    dry_run: bool = False

    @property
    def counts(self) -> dict:
        from collections import Counter

        return dict(Counter(e.status for e in self.log))

    @property
    def success(self) -> bool:
        return not any(e.status == "error" for e in self.log)


def create_structure(
    base_path: Path,
    structure: dict,
    *,
    dry_run: bool = False,
    on_conflict: str = "skip",
    _result: CreationResult = None,
) -> CreationResult:
    """Recursively create folders/files. Returns a CreationResult."""
    if _result is None:
        _result = CreationResult(dry_run=dry_run)

    if not dry_run:
        try:
            base_path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            _result.log.append(
                CreationEntry(str(base_path), "folder", "error", str(exc))
            )
            return _result

    for name, content in structure.items():
        item_path = base_path / name
        kind = "folder" if isinstance(content, dict) else "file"

        if dry_run:
            _result.log.append(CreationEntry(str(item_path), kind, "dry-run"))
            if kind == "folder":
                create_structure(
                    item_path,
                    content,
                    dry_run=True,
                    on_conflict=on_conflict,
                    _result=_result,
                )
            continue

        if kind == "folder":
            if item_path.exists() and on_conflict == "skip":
                _result.log.append(
                    CreationEntry(str(item_path), "folder", "skipped", "already exists")
                )
            else:
                try:
                    item_path.mkdir(parents=True, exist_ok=True)
                    _result.log.append(
                        CreationEntry(str(item_path), "folder", "created")
                    )
                    _result.created_paths.append(item_path)
                except OSError as exc:
                    _result.log.append(
                        CreationEntry(str(item_path), "folder", "error", str(exc))
                    )
                    continue
            create_structure(
                item_path,
                content,
                dry_run=False,
                on_conflict=on_conflict,
                _result=_result,
            )
        else:
            if item_path.exists():
                if on_conflict == "skip":
                    _result.log.append(
                        CreationEntry(
                            str(item_path), "file", "skipped", "already exists"
                        )
                    )
                    continue
                else:
                    item_path.unlink()
            try:
                item_path.touch()
                _result.log.append(CreationEntry(str(item_path), "file", "created"))
                _result.created_paths.append(item_path)
            except OSError as exc:
                _result.log.append(
                    CreationEntry(str(item_path), "file", "error", str(exc))
                )

    return _result


def rollback(result: CreationResult) -> list:
    """Delete everything created in the last run (newest first)."""
    deleted = []
    for path in reversed(result.created_paths):
        p = Path(path)
        try:
            if p.is_file():
                p.unlink(missing_ok=True)
                deleted.append(str(p))
            elif p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
                deleted.append(str(p))
        except Exception:
            pass
    return deleted


def structure_to_json(structure: dict) -> str:
    return json.dumps(structure, indent=2, default=lambda o: None)