import io
import json
import zipfile
import datetime
from pathlib import Path

import streamlit as st
import pytesseract
from PIL import Image
from streamlit_tree_select import tree_select

from parser import normalize_tree_text, parse_tree_text, structure_to_tree_text
from main import create_structure, rollback, structure_to_json

import os

IS_CLOUD = os.path.exists("/mount/src")

# ══════════════════════════════════════════════════════════════════
# Page config & theme injection
# ══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="AutoDir:2",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background: #0f1117;
    color: #e2e8f0;
    font-family: 'Inter', 'Segoe UI', sans-serif;
}
[data-testid="stSidebar"] {
    background: #161b27 !important;
    border-right: 1px solid #2d3748;
}
/* ── Tabs ── */
[data-testid="stTabs"] [role="tab"] {
    font-size: 0.85rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: #718096;
    padding: 0.5rem 1.2rem;
    border-radius: 6px 6px 0 0;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #63b3ed;
    border-bottom: 2px solid #63b3ed;
    background: #1a202c;
}
/* ── Buttons ── */
.stButton > button {
    background: #2b6cb0;
    color: #fff;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    padding: 0.5rem 1.4rem;
    transition: background 0.2s;
}
.stButton > button:hover { background: #3182ce; }
/* ── Code/text areas ── */
.stTextArea textarea {
    background: #1a202c !important;
    color: #e2e8f0 !important;
    border: 1px solid #2d3748 !important;
    border-radius: 8px;
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.82rem;
}
/* ── Cards ── */
.metric-card {
    background: #1a202c;
    border: 1px solid #2d3748;
    border-radius: 10px;
    padding: 1rem 1.4rem;
    text-align: center;
}
.metric-val { font-size: 2rem; font-weight: 700; color: #63b3ed; }
.metric-lbl { font-size: 0.72rem; color: #718096; text-transform: uppercase; letter-spacing: .06em; }
/* ── Log rows ── */
.log-created { color: #68d391; }
.log-skipped { color: #f6e05e; }
.log-error   { color: #fc8181; }
.log-dryrun  { color: #76e4f7; }
/* ── Banner ── */
.app-banner {
    background: linear-gradient(135deg, #1a365d 0%, #2a4365 100%);
    border: 1px solid #2c5282;
    border-radius: 12px;
    padding: 1.6rem 2rem;
    margin-bottom: 1.4rem;
}
.app-banner h1 { margin: 0; font-size: 1.8rem; color: #bee3f8; }
.app-banner p  { margin: 0.3rem 0 0; color: #90cdf4; font-size: 0.9rem; }
</style>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════
# Session state initialisation
# ══════════════════════════════════════════════════════════════════


def _init():
    defaults = {
        "raw_text": "",
        "edited_text": "",
        "parse_result": None,
        "creation_result": None,
        "history": [],  # list of {ts, structure, log}
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init()


# ══════════════════════════════════════════════════════════════════
# Sidebar — settings & history
# ══════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Settings")
    dry_run_mode = st.toggle(
        "Dry-run mode (simulate only)",
        value=False,
        help="Preview what would be created without touching your disk.",
    )
    conflict_mode = st.radio(
        "On conflict",
        ["skip", "overwrite"],
        help="What to do when a file or folder already exists.",
    )
    st.divider()
    st.markdown("## 📜 Session History")
    if st.session_state.history:
        for i, h in enumerate(reversed(st.session_state.history[-5:])):
            with st.expander(f"Run {len(st.session_state.history) - i} — {h['ts']}"):
                st.caption(
                    f"Folders: {h['stats'].get('folders', 0)}  Files: {h['stats'].get('files', 0)}"
                )
    else:
        st.caption("No runs yet this session.")
    st.divider()
    st.caption("AutoDir v2 · Built by Vineet")


# ══════════════════════════════════════════════════════════════════
# Banner
# ══════════════════════════════════════════════════════════════════

st.markdown(
    """
<div class="app-banner">
  <h1>🗂️ AutoDir v2</h1>
  <p>Paste a tree structure, drop an image, or upload a .txt — generate a real folder hierarchy in seconds.</p>
</div>
""",
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════
# Tabs
# ══════════════════════════════════════════════════════════════════

tab_input, tab_edit, tab_preview, tab_create, tab_export = st.tabs(
    ["1 · Input", "2 · Edit", "3 · Preview", "4 · Create", "5 · Export"]
)


# ──────────────────────────────────────────────────────────────
# TAB 1 — Input
# ──────────────────────────────────────────────────────────────

with tab_input:
    st.subheader("Import your tree structure")

    input_mode = st.radio(
        "Source", ["Upload file", "Paste text", "Use template"], horizontal=True
    )

    TEMPLATES = {
        "Python project": """\
my_project/
├── src/
│   ├── __init__.py
│   ├── main.py
│   └── utils/
│       ├── __init__.py
│       └── helpers.py
├── tests/
│   ├── __init__.py
│   └── test_main.py
├── docs/
│   └── index.md
├── requirements.txt
├── setup.py
└── README.md""",
        "React app": """\
my-app/
├── public/
│   ├── index.html
│   └── favicon.ico
├── src/
│   ├── components/
│   │   └── App.jsx
│   ├── pages/
│   │   └── Home.jsx
│   ├── hooks/
│   │   └── useFetch.js
│   ├── styles/
│   │   └── globals.css
│   └── index.js
├── package.json
└── README.md""",
        "FastAPI backend": """\
backend/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── routers/
│   │   ├── __init__.py
│   │   └── users.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas/
│   │   └── user.py
│   └── database.py
├── tests/
│   └── test_users.py
├── .env.example
├── requirements.txt
└── Dockerfile""",
        "Data science": """\
ds_project/
├── data/
│   ├── raw/
│   ├── processed/
│   └── external/
├── notebooks/
│   ├── 01_eda.ipynb
│   └── 02_modelling.ipynb
├── src/
│   ├── __init__.py
│   ├── features.py
│   ├── train.py
│   └── evaluate.py
├── models/
├── reports/
│   └── figures/
├── requirements.txt
└── README.md""",
    }

    raw_text = ""

    if input_mode == "Upload file":
        uploaded = st.file_uploader(
            "Drop a TXT or image file",
            type=["txt", "png", "jpg", "jpeg", "webp"],
            help="Images are processed with Tesseract OCR.",
        )
        if uploaded:
            if uploaded.type.startswith("image/"):
                img = Image.open(uploaded)
                st.image(img, caption="Uploaded image", use_container_width=True)
                with st.spinner("Running OCR…"):
                    raw_text = pytesseract.image_to_string(img)
                st.success(
                    f"OCR complete — {len(raw_text.splitlines())} lines extracted."
                )
            else:
                raw_text = uploaded.read().decode("utf-8", errors="replace")
                st.success(f"Loaded — {len(raw_text.splitlines())} lines.")

    elif input_mode == "Paste text":
        raw_text = st.text_area(
            "Paste your tree here",
            height=300,
            placeholder="project/\n├── src/\n│   └── main.py\n└── README.md",
        )

    else:  # Template
        chosen = st.selectbox("Choose a starter template", list(TEMPLATES.keys()))
        raw_text = TEMPLATES[chosen]
        st.text_area(
            "Template preview (read-only)", raw_text, height=280, disabled=True
        )

    if raw_text.strip():
        st.session_state.raw_text = raw_text
        st.session_state.edited_text = raw_text
        st.info("Input ready. Head to **2 · Edit** to review before parsing.")


# ──────────────────────────────────────────────────────────────
# TAB 2 — Edit
# ──────────────────────────────────────────────────────────────

with tab_edit:
    st.subheader("Edit tree structure")
    st.caption(
        "Folders end with `/`. Indent each level with 4 spaces (or use tree symbols)."
    )

    col_edit, col_help = st.columns([3, 1])

    with col_edit:
        edited = st.text_area(
            "Tree editor",
            value=st.session_state.edited_text,
            height=360,
            key="tree_editor",
            placeholder="project/\n├── src/\n│   └── main.py\n└── README.md",
        )
        st.session_state.edited_text = edited

    with col_help:
        st.markdown("**Quick guide**")
        st.markdown("""
- `folder/` → directory  
- `file.ext` → empty file  
- Indent = 4 spaces per level  
- Box chars `├ └ │` are optional  
- Duplicate names at same level are skipped  
- Max depth: 10 levels  
        """)

    col_b1, col_b2 = st.columns([2, 1])
    with col_b1:
        parse_clicked = st.button(
            "🔍 Parse & validate", type="primary", use_container_width=True
        )
    with col_b2:
        if st.button("🧹 Normalize whitespace", use_container_width=True):
            st.session_state.edited_text = normalize_tree_text(
                st.session_state.edited_text
            )
            st.rerun()

    if parse_clicked:
        text = normalize_tree_text(st.session_state.edited_text)
        result = parse_tree_text(text)
        st.session_state.parse_result = result

        if result.errors:
            for e in result.errors:
                st.error(str(e))
        if result.warnings:
            for w in result.warnings:
                st.warning(w)
        if result.ok:
            st.success(
                f"Parsed successfully — "
                f"{result.stats['folders']} folders, {result.stats['files']} files, "
                f"max depth {result.stats['depth']}."
            )
            st.info("Go to **3 · Preview** to inspect the tree.")
        elif not result.errors:
            st.error("Nothing was parsed — check your formatting.")


# ──────────────────────────────────────────────────────────────
# TAB 3 — Preview
# ──────────────────────────────────────────────────────────────

with tab_preview:
    result = st.session_state.parse_result

    if result is None or not result.ok:
        st.info("Parse your tree in **2 · Edit** first.")
    else:
        st.subheader("Structure preview")

        # Stats row
        s = result.stats
        c1, c2, c3, c4 = st.columns(4)
        for col, val, lbl in [
            (c1, s["folders"], "Folders"),
            (c2, s["files"], "Files"),
            (c3, s["total"], "Total items"),
            (c4, s["depth"], "Max depth"),
        ]:
            col.markdown(
                f'<div class="metric-card"><div class="metric-val">{val}</div>'
                f'<div class="metric-lbl">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        col_tree, col_raw = st.columns([1, 1])

        with col_tree:
            st.markdown("**Interactive tree**")

            def _to_nodes(d: dict, prefix: str = "") -> list:
                nodes = []
                for idx, (k, v) in enumerate(d.items()):
                    nid = f"{prefix}/{k}/{idx}"
                    if isinstance(v, dict):
                        nodes.append(
                            {
                                "label": f"📁 {k}",
                                "value": nid,
                                "children": _to_nodes(v, nid),
                            }
                        )
                    else:
                        nodes.append({"label": f"📄 {k}", "value": nid})
                return nodes

            root_nodes = _to_nodes(result.structure)
            try:
                tree_select(root_nodes, key="preview_tree")
            except TypeError:
                tree_select(root_nodes, key="preview_tree_fb")

        with col_raw:
            st.markdown("**Normalised text (canonical form)**")
            canonical = structure_to_tree_text(result.structure)
            st.text_area("", canonical, height=350, disabled=True, key="canonical_view")

        if result.warnings:
            with st.expander(f"⚠️ {len(result.warnings)} warning(s)"):
                for w in result.warnings:
                    st.caption(w)


# ──────────────────────────────────────────────────────────────
# TAB 4 — Create
# ──────────────────────────────────────────────────────────────

with tab_create:
    result = st.session_state.parse_result

    if result is None or not result.ok:
        st.info("Parse your tree in **2 · Edit** first.")

    elif IS_CLOUD:
        # ── Cloud mode: can't write to user's machine, offer ZIP instead ──
        st.subheader("Download your structure")
        st.info(
            "**You're on the cloud version** — files can't be created directly on your machine.\n\n"
            "Download the ZIP skeleton below, then unzip it anywhere on your computer to scaffold the structure instantly."
        )

        s = result.stats
        c1, c2, c3 = st.columns(3)
        for col, val, lbl in [
            (c1, s["folders"], "Folders"),
            (c2, s["files"], "Files"),
            (c3, s["total"], "Total items"),
        ]:
            col.markdown(
                f'<div class="metric-card"><div class="metric-val">{val}</div>'
                f'<div class="metric-lbl">{lbl}</div></div>',
                unsafe_allow_html=True,
            )

        st.divider()

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:

            def _zip_add_create(zf, d: dict, prefix: str):
                for name, content in d.items():
                    path = f"{prefix}/{name}" if prefix else name
                    if isinstance(content, dict):
                        zf.mkdir(path) if hasattr(zf, "mkdir") else zf.writestr(
                            path + "/.keep", ""
                        )
                        _zip_add_create(zf, content, path)
                    else:
                        zf.writestr(path, "")

            _zip_add_create(zf, result.structure, "")
        buf.seek(0)

        st.download_button(
            "⬇️ Download ZIP skeleton",
            data=buf,
            file_name="directory_skeleton.zip",
            mime="application/zip",
            use_container_width=True,
            type="primary",
        )
        st.caption(
            "Unzip anywhere on your machine — all folders and empty files are ready to go."
        )

        st.divider()
        st.markdown("**Want full local file creation?**")
        st.code(
            "git clone https://github.com/i-m-vineet2001/autodir.git\ncd autodir\npip install -r requirements.txt\nstreamlit run AutoDir/app.py",
            language="bash",
        )
        st.caption(
            "Run locally to create folders directly on your machine with dry-run, rollback, and conflict handling."
        )

    else:
        # ── Local mode: full disk creation ──
        st.subheader("Create on disk")

        if dry_run_mode:
            st.warning("**Dry-run mode is ON** — nothing will be written to disk.")

        base_path_str = st.text_input(
            "Base directory",
            value=str(Path.cwd()),
            help="The structure will be created inside this directory.",
        )

        col_go, col_rb = st.columns([2, 1])

        with col_go:
            go = st.button(
                "🚀 Simulate" if dry_run_mode else "🚀 Generate",
                type="primary",
                use_container_width=True,
            )
        with col_rb:
            rollback_btn = st.button(
                "↩️ Rollback last run",
                use_container_width=True,
                disabled=st.session_state.creation_result is None,
            )

        if go:
            base = Path(base_path_str)
            if not dry_run_mode and not base.exists():
                st.error(
                    "That directory does not exist. Create it first, or enable dry-run."
                )
            else:
                with st.spinner("Working…"):
                    root_name = next(iter(result.structure))
                    root_body = result.structure[root_name]
                    cr = create_structure(
                        base / root_name,
                        root_body,
                        dry_run=dry_run_mode,
                        on_conflict=conflict_mode,
                    )
                st.session_state.creation_result = cr

                st.session_state.history.append(
                    {
                        "ts": datetime.datetime.now().strftime("%H:%M:%S"),
                        "stats": result.stats,
                        "log": [e.label() for e in cr.log],
                    }
                )

                counts = cr.counts
                if dry_run_mode:
                    st.info(
                        f"Dry-run complete — {counts.get('dry-run', 0)} items simulated."
                    )
                elif cr.success:
                    st.balloons()
                    st.success(
                        f"Done! Created {counts.get('created', 0)} items, "
                        f"skipped {counts.get('skipped', 0)}."
                    )
                else:
                    st.error("Some items failed — see log below.")

        if rollback_btn and st.session_state.creation_result:
            deleted = rollback(st.session_state.creation_result)
            st.session_state.creation_result = None
            st.success(f"Rolled back {len(deleted)} item(s).")

        cr = st.session_state.creation_result
        if cr:
            st.divider()
            st.markdown(f"**Creation log** — {len(cr.log)} entries")
            css_map = {
                "created": "log-created",
                "skipped": "log-skipped",
                "error": "log-error",
                "dry-run": "log-dryrun",
            }
            log_html = (
                "<div style='font-family:monospace;font-size:0.78rem;line-height:1.8'>"
            )
            for entry in cr.log:
                css = css_map.get(entry.status, "")
                log_html += f'<div class="{css}">{entry.label()}</div>'
            log_html += "</div>"
            st.markdown(log_html, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# TAB 5 — Export
# ──────────────────────────────────────────────────────────────

with tab_export:
    result = st.session_state.parse_result

    if result is None or not result.ok:
        st.info("Parse your tree in **2 · Edit** first.")
    else:
        st.subheader("Export")
        st.caption("Download your structure in different formats.")

        col_j, col_t, col_z = st.columns(3)

        # JSON export
        with col_j:
            json_str = structure_to_json(result.structure)
            st.download_button(
                "⬇️ Download JSON",
                data=json_str,
                file_name="structure.json",
                mime="application/json",
                use_container_width=True,
            )
            st.caption("Machine-readable nested dict — pipe into other tools.")

        # Tree text export
        with col_t:
            tree_txt = structure_to_tree_text(result.structure)
            st.download_button(
                "⬇️ Download tree.txt",
                data=tree_txt,
                file_name="structure_tree.txt",
                mime="text/plain",
                use_container_width=True,
            )
            st.caption("Canonical tree text — copy into your README or docs.")

        # ZIP of empty structure
        with col_z:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:

                def _zip_add(zf, d: dict, prefix: str):
                    for name, content in d.items():
                        path = f"{prefix}/{name}" if prefix else name
                        if isinstance(content, dict):
                            zf.mkdir(path) if hasattr(zf, "mkdir") else zf.writestr(
                                path + "/.keep", ""
                            )
                            _zip_add(zf, content, path)
                        else:
                            zf.writestr(path, "")

                _zip_add(zf, result.structure, "")
            buf.seek(0)
            st.download_button(
                "⬇️ Download ZIP skeleton",
                data=buf,
                file_name="directory_skeleton.zip",
                mime="application/zip",
                use_container_width=True,
            )
            st.caption("Empty file/folder skeleton — unzip anywhere.")

        st.divider()
        st.markdown("**Structure JSON preview**")
        st.json(result.structure, expanded=2)
