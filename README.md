<div align="center">

# 🗂️ AutoDir v2

**Paste a tree. Generate a real folder structure. Zero friction.**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35%2B-FF4B4B?style=flat-square&logo=streamlit&logoColor=white)](https://streamlit.io)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000?style=flat-square)](https://github.com/psf/black)

[Features](#-features) · [Quick Start](#-quick-start) · [Usage](#-usage) · [Architecture](#-architecture) · [Contributing](#-contributing)

</div>

---

## ✨ Features

| Feature | v1 | v2 |
|---|---|---|
| Parse tree text | ✅ | ✅ (rewritten, 5× more robust) |
| OCR from image | ✅ | ✅ |
| Interactive tree preview | ✅ | ✅ |
| Template library | ❌ | ✅ Python · React · FastAPI · Data Science |
| Dry-run (simulate only) | ❌ | ✅ |
| Conflict handling | ❌ | ✅ skip / overwrite |
| One-click rollback | ❌ | ✅ |
| Session history | ❌ | ✅ |
| Export to JSON | ❌ | ✅ |
| Export to ZIP skeleton | ❌ | ✅ |
| Warnings & parse errors | ❌ | ✅ per-line, human-readable |
| Duplicate-name detection | ❌ | ✅ |
| Dark professional theme | ❌ | ✅ |

---

## 🚀 Quick Start

### Prerequisites

| Dependency | Install |
|---|---|
| Python 3.10+ | [python.org](https://python.org) |
| Tesseract OCR | See below |

**Tesseract installation:**

```bash
# macOS
brew install tesseract

# Ubuntu / Debian
sudo apt-get install tesseract-ocr

# Windows
# Download installer from https://github.com/UB-Mannheim/tesseract/wiki
```

### Install & run

```bash
# 1. Clone
git clone https://github.com/<your-username>/autodir.git
cd autodir

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install streamlit pytesseract Pillow streamlit-tree-select

# 4. Launch
streamlit run app.py
```

App opens at **http://localhost:8501** automatically.

---

## 📖 Usage

AutoDir v2 is a 5-tab workflow:

### Tab 1 — Input
Choose how to bring in your tree structure:
- **Upload file** — `.txt` or an image (PNG/JPG/WEBP). Images are processed with Tesseract OCR.
- **Paste text** — type or paste any tree format directly.
- **Template** — pick from 4 built-in starter layouts (Python project, React app, FastAPI backend, Data science).

### Tab 2 — Edit
Review and edit the tree before parsing. Use the **Normalize** button to auto-fix whitespace and unicode symbols. Hit **Parse & validate** to check for errors, warnings, and duplicates.

### Tab 3 — Preview
An interactive folder tree (click to expand/collapse) alongside the canonical normalized text. Summary stats show total folders, files, and max nesting depth.

### Tab 4 — Create
Set the destination directory and click **Generate**. Options (in the sidebar):
- **Dry-run mode** — simulates every action without touching your disk.
- **On conflict** — `skip` keeps existing items; `overwrite` replaces files.
- **Rollback** — one-click undo that deletes everything created in the last run.

The colour-coded creation log shows each item's status: `CREATED` · `SKIPPED` · `ERROR` · `DRY-RUN`.

### Tab 5 — Export
Download your parsed structure as:
- `structure.json` — machine-readable nested dict
- `structure_tree.txt` — canonical tree text (paste into READMEs)
- `directory_skeleton.zip` — unzip anywhere to scaffold the structure instantly

---

## 🌳 Supported tree formats

AutoDir v2 parses all of these (and mixes between them):

```
# Box-drawing symbols (standard `tree` command output)
project/
├── src/
│   ├── main.py
│   └── utils/
│       └── helpers.py
└── README.md

# Bare indentation (4 spaces per level)
project/
    src/
        main.py
        utils/
            helpers.py
    README.md

# Mixed / messy (from OCR or manual input)
project/
|-- src/
|   |-- main.py
|   +-- utils/
|       \-- helpers.py
+-- README.md
```

---

## 🏗️ Architecture

```
autodir/
├── app.py        # Streamlit UI — 5-tab layout, session state, theming
├── parser.py     # Tree-text parser & normalizer
│                 #   normalize_tree_text()  →  canonical string
│                 #   parse_tree_text()      →  ParseResult (structure + errors + stats)
│                 #   structure_to_tree_text()  →  back to text (export)
├── main.py       # Disk I/O engine
│                 #   create_structure()     →  CreationResult (log + rollback list)
│                 #   rollback()             →  deletes created items
│                 #   structure_to_json()    →  JSON export
└── README.md
```

### Key design decisions

**`parse_tree_text` returns a `ParseResult`, not a raw dict.**  
Errors and warnings are first-class. The UI can surface exactly what went wrong on which line without crashing.

**Two-phase indent detection.**  
Box-drawing symbols and bare spaces are both normalised to a depth integer before building the tree, so the same parser handles both formats without branching logic.

**Rollback list in `CreationResult`.**  
Every item successfully written to disk is appended in creation order. Rollback simply iterates in reverse — no state file, no lock needed for the single-user Streamlit case.

---

## ⚙️ Configuration

All runtime options live in the **sidebar** — no config file required:

| Option | Default | Description |
|---|---|---|
| Dry-run mode | Off | Simulate without writing to disk |
| On conflict | skip | `skip` or `overwrite` existing items |

---

## 🤝 Contributing

Pull requests are welcome. For major changes, open an issue first.

```bash
# Run a quick smoke-test after changes
python -c "
from parser import normalize_tree_text, parse_tree_text
sample = '''
project/
├── src/
│   └── main.py
└── README.md
'''
r = parse_tree_text(normalize_tree_text(sample))
assert r.ok, r.errors
assert r.stats['folders'] == 2
assert r.stats['files']   == 2
print('All checks passed.')
"
```

**Style:**
- `black` for formatting
- Type-annotate all public functions
- New features need a dry-run test path

---

## 🐛 Troubleshooting

| Error | Fix |
|---|---|
| `ModuleNotFoundError` | Activate your venv: `source .venv/bin/activate` |
| `TesseractNotFoundError` | Install Tesseract — see [Prerequisites](#-quick-start) |
| Nothing parsed | Check indentation: 4 spaces per level, folders end with `/` |
| Depth warning | Nesting > 10 levels — verify you haven't accidentally copied extra whitespace |

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">

Built with ❤️ by **Vineet** · [LinkedIn](https://linkedin.com/in/your-handle) · [GitHub](https://github.com/your-username)

</div>