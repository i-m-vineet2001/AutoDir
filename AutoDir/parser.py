

# import re

# def parse_line(line: str):
#     """Parse a single tree line to extract name, indent level, and folder flag."""
#     i = 0
#     while i < len(line) and (line[i].isspace() or line[i] in '├└│─'):
#         i += 1
#     if i == len(line):
#         return None
#     rest = line[i:].strip()
#     if rest.endswith('/'):
#         name = rest[:-1]
#         is_folder = True
#     else:
#         name = rest
#         is_folder = False
#     indent = i // 4
#     return name, indent, is_folder

# def parse_tree_text(tree_text: str) -> dict:
#     """Parse normalized tree text into a nested dict (folders: {}, files: None)."""
#     structure = {}
#     stack = [structure]
#     lines = [line for line in tree_text.splitlines() if line.strip()]
#     for line in lines:
#         parsed = parse_line(line)
#         if parsed is None:
#             continue
#         name, indent, is_folder = parsed
#         while len(stack) > indent + 1:
#             stack.pop()
#         parent = stack[-1]
#         if is_folder:
#             parent[name] = {}
#             stack.append(parent[name])
#         else:
#             parent[name] = None
#     return structure

# def normalize_tree_text(tree_text: str) -> str:
#     """Clean and standardize tree text (symbols, whitespace)."""
#     tree_text = re.sub(r'[|┃]', '│', tree_text)
#     tree_text = re.sub(r'[-–—]', '─', tree_text)
#     lines = [line.rstrip() for line in tree_text.splitlines() if line.strip()]
#     return '\n'.join(lines)













"""
parser.py — AutoDir v2
Robust tree-text parser that handles:
  - Unicode box-drawing symbols (├ └ │ ─) and ASCII equivalents
  - Mixed spaces/tabs
  - Bare-indent style (no symbols, just spaces)
  - Windows / Unix line endings
  - Deeply nested structures
  - Validation with human-readable error messages
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# ──────────────────────────────────────────────────────────────
# Data structures
# ──────────────────────────────────────────────────────────────


@dataclass
class ParseError:
    line_number: int
    raw_line: str
    message: str

    def __str__(self) -> str:
        return f"Line {self.line_number}: {self.message!r} → {self.raw_line!r}"


@dataclass
class ParseResult:
    structure: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return bool(self.structure) and not self.errors


# ──────────────────────────────────────────────────────────────
# Normalizer
# ──────────────────────────────────────────────────────────────

_PIPE_VARIANTS = re.compile(r"[┃\|╎╏]")
_DASH_VARIANTS = re.compile(r"[─━−‒–—]")
_TEE_VARIANTS = re.compile(r"[├╠╟╞]")
_CORNER_VARIANTS = re.compile(r"[└╚╙╘]")
_FILENAME_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def normalize_tree_text(raw: str) -> str:
    """
    Canonicalise unicode box-drawing chars, normalise line endings,
    strip trailing whitespace, and drop blank lines.
    Returns clean text ready for parse_tree_text().
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = _PIPE_VARIANTS.sub("│", text)
    text = _DASH_VARIANTS.sub("─", text)
    text = _TEE_VARIANTS.sub("├", text)
    text = _CORNER_VARIANTS.sub("└", text)
    text = text.replace("\t", "    ")
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────
# Line-level parser
# ──────────────────────────────────────────────────────────────

_BOX_CHARS = set("│├└─ ")


def _parse_line(line: str):
    """
    Returns (name, depth, is_folder) or None if line is blank/structural-only.
    Depth is zero-based: root items are depth 0.
    """
    if not line.strip():
        return None

    i = 0
    while i < len(line) and line[i] in _BOX_CHARS:
        i += 1

    prefix = line[:i]
    rest = line[i:].strip()

    if not rest:
        return None

    depth = len(prefix.replace("│", " ")) // 4

    is_folder = rest.endswith("/")
    name = rest[:-1] if is_folder else rest
    name = re.sub(r"^[├└─\s]+", "", name).strip()

    if not name:
        return None

    return name, depth, is_folder


# ──────────────────────────────────────────────────────────────
# Tree builder
# ──────────────────────────────────────────────────────────────


def parse_tree_text(tree_text: str) -> ParseResult:
    """
    Parse a normalised tree text into a nested dict.
    Folder => { name: { ... } }   File => { name: None }
    Returns a ParseResult with .structure, .errors, .warnings, .stats.
    """
    result = ParseResult()
    root = {}
    stack = [(-1, root)]

    folder_count = 0
    file_count = 0

    lines = tree_text.splitlines()
    for lineno, raw_line in enumerate(lines, start=1):
        if not raw_line.strip():
            continue

        parsed = _parse_line(raw_line)
        if parsed is None:
            continue

        name, depth, is_folder = parsed

        if _FILENAME_ILLEGAL.search(name):
            result.errors.append(
                ParseError(lineno, raw_line, f"Illegal characters in name '{name}'")
            )
            continue

        if depth > 10:
            result.warnings.append(
                f"Line {lineno}: depth {depth} is unusually deep — check indentation."
            )

        while len(stack) > 1 and stack[-1][0] >= depth:
            stack.pop()

        parent_dict = stack[-1][1]

        if name in parent_dict:
            result.warnings.append(
                f"Line {lineno}: duplicate '{name}' at this level — skipped."
            )
            continue

        if is_folder:
            parent_dict[name] = {}
            stack.append((depth, parent_dict[name]))
            folder_count += 1
        else:
            parent_dict[name] = None
            file_count += 1

    result.structure = root
    result.stats = {
        "folders": folder_count,
        "files": file_count,
        "total": folder_count + file_count,
        "depth": _max_depth(root),
    }
    return result


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _max_depth(d: dict, current: int = 0) -> int:
    if not d:
        return current
    return max(
        _max_depth(v, current + 1) if isinstance(v, dict) else current
        for v in d.values()
    )


def structure_to_tree_text(structure: dict, prefix: str = "") -> str:
    """Convert a parsed structure back to human-readable tree text."""
    lines = []
    items = list(structure.items())
    for idx, (name, content) in enumerate(items):
        is_last = idx == len(items) - 1
        connector = "└── " if is_last else "├── "
        child_pfx = prefix + ("    " if is_last else "│   ")
        if isinstance(content, dict):
            lines.append(f"{prefix}{connector}{name}/")
            lines.append(structure_to_tree_text(content, child_pfx))
        else:
            lines.append(f"{prefix}{connector}{name}")
    return "\n".join(filter(None, lines))