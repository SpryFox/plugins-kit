#!/usr/bin/env python3
"""claude-explorer: browsable HTML view of ~/.claude/ + project.

Two phases:
  crawl  -- walk roots, compute deterministic summary projections, write index.json.
  serve  -- local HTTP server (127.0.0.1) serving the SPA + index + file endpoint.
  run    -- crawl, then serve, then open browser.

Read-only v1. LLM-generated summaries (Haiku via `claude -p`) are stubbed; the
hook exists but is disabled by default. See SKILL.md for the design rationale.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import http.server
import json
import os
import pathlib
import re
import socketserver
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from typing import Any

try:
    import yaml  # PyYAML
    HAVE_YAML = True
except ImportError:
    HAVE_YAML = False


HOME = pathlib.Path.home()
CLAUDE_DIR = HOME / ".claude"
DATA_DIR = CLAUDE_DIR / ".local-data" / "awesome-kit" / "claude-explorer"
INDEX_PATH = DATA_DIR / "index.json"
CACHE_DIR = DATA_DIR / "cache"
DEFAULT_PORT = 8923


# ----------------------------------------------------------------------------
# Hashing + cache
# ----------------------------------------------------------------------------

def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def safe_read_bytes(p: pathlib.Path, limit: int = 2_000_000) -> bytes | None:
    try:
        return p.read_bytes()[:limit]
    except (OSError, PermissionError):
        return None


def safe_read_text(p: pathlib.Path, limit: int = 2_000_000) -> str | None:
    b = safe_read_bytes(p, limit)
    if b is None:
        return None
    try:
        return b.decode("utf-8", errors="replace")
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Frontmatter and structured extraction
# ----------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.+?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text: str) -> dict:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    raw = m.group(1)
    if HAVE_YAML:
        try:
            data = yaml.safe_load(raw)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    # fallback: line-by-line key: value
    out = {}
    for line in raw.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def first_heading(text: str) -> str | None:
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def first_lines(text: str, n: int = 2) -> str:
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip() and not ln.startswith("---")]
    return "\n".join(lines[:n])


def count_tokens_approx(text: str) -> int:
    # cheap approximation: words * 1.3
    return int(len(text.split()) * 1.3)


# ----------------------------------------------------------------------------
# Per-primitive summary projections (deterministic)
# ----------------------------------------------------------------------------

def project_skill_md(p: pathlib.Path) -> dict:
    text = safe_read_text(p) or ""
    fm = parse_frontmatter(text)
    body_after = FRONTMATTER_RE.sub("", text, count=1)
    return {
        "kind": "skill_md",
        "name": fm.get("name"),
        "description": fm.get("description"),
        "skill_type": fm.get("skill-type"),
        "author": fm.get("author"),
        "body_lines": body_after.count("\n") + 1 if body_after else 0,
        "body_tokens": count_tokens_approx(body_after),
    }


def project_claude_md(p: pathlib.Path) -> dict:
    text = safe_read_text(p) or ""
    h1 = first_heading(text)
    # try to detect structured scope block
    scope_dir = None
    scope_covers = []
    m = re.search(r"^\s*scope:\s*\n((?:^[ \t]+.*\n?)+)", text, re.MULTILINE)
    if m and HAVE_YAML:
        try:
            scope = yaml.safe_load("scope:\n" + m.group(1))
            scope = scope.get("scope") if isinstance(scope, dict) else None
            if isinstance(scope, dict):
                scope_dir = scope.get("directory")
                covers = scope.get("covers", [])
                if isinstance(covers, list):
                    scope_covers = covers[:5]
        except Exception:
            pass
    return {
        "kind": "claude_md",
        "first_heading": h1,
        "scope_directory": scope_dir,
        "scope_covers": scope_covers,
        "lines": text.count("\n") + 1 if text else 0,
    }


def project_reference_doc(p: pathlib.Path) -> dict:
    text = safe_read_text(p) or ""
    return {
        "kind": "reference_doc",
        "filename": p.name,
        "first_heading": first_heading(text),
        "first_lines": first_lines(text, 2),
        "lines": text.count("\n") + 1 if text else 0,
    }


def project_plain_md(p: pathlib.Path) -> dict:
    text = safe_read_text(p) or ""
    return {
        "kind": "plain_md",
        "filename": p.name,
        "first_heading": first_heading(text),
        "lines": text.count("\n") + 1 if text else 0,
    }


def project_plugin_manifest(p: pathlib.Path) -> dict:
    try:
        data = json.loads(safe_read_text(p) or "{}")
    except Exception:
        data = {}
    return {
        "kind": "plugin_manifest",
        "name": data.get("name"),
        "version": data.get("version"),
        "description": data.get("description"),
        "razor": data.get("razor"),
    }


def project_marketplace_manifest(p: pathlib.Path) -> dict:
    try:
        data = json.loads(safe_read_text(p) or "{}")
    except Exception:
        data = {}
    plugins = data.get("plugins") or []
    return {
        "kind": "marketplace_manifest",
        "name": data.get("name"),
        "plugin_count": len(plugins) if isinstance(plugins, list) else 0,
    }


def project_bootstrap_manifest(p: pathlib.Path) -> dict:
    try:
        data = json.loads(safe_read_text(p) or "{}")
    except Exception:
        data = {}
    venv = data.get("venv") or {}
    imports = venv.get("check_imports") or []
    tools = data.get("tools") or []
    return {
        "kind": "bootstrap_manifest",
        "check_imports": imports if isinstance(imports, list) else [],
        "tool_count": len(tools) if isinstance(tools, list) else 0,
    }


def project_script(p: pathlib.Path) -> dict:
    text = safe_read_text(p, limit=20_000) or ""
    docstring = None
    if p.suffix == ".py":
        m = re.match(r'\A(?:#![^\n]*\n)?(?:from __future__[^\n]*\n)?\s*"""(.*?)"""', text, re.DOTALL)
        if m:
            docstring = m.group(1).strip().splitlines()[0].strip()
    elif p.suffix in (".sh", ".bash"):
        for line in text.splitlines()[:10]:
            s = line.strip()
            if s.startswith("#") and not s.startswith("#!"):
                docstring = s.lstrip("#").strip()
                break
    return {
        "kind": "script",
        "filename": p.name,
        "language": p.suffix.lstrip("."),
        "leading_doc": docstring,
        "lines": text.count("\n") + 1 if text else 0,
    }


# ----------------------------------------------------------------------------
# Composition detection
# ----------------------------------------------------------------------------

def detect_composition(d: pathlib.Path) -> str:
    """Return composition id for a directory."""
    if (d / ".claude-plugin" / "marketplace.json").exists():
        return "marketplace"
    if (d / ".claude-plugin" / "plugin.json").exists():
        return "plugin"
    if (d / "SKILL.md").exists():
        return "skill"
    return "directory"


# ----------------------------------------------------------------------------
# Crawl
# ----------------------------------------------------------------------------

IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", "dist", "build"}
MAX_DEPTH = 12


def walk(root: pathlib.Path, max_depth: int = MAX_DEPTH) -> dict:
    """Walk a root composition tree. Returns a tree node dict."""
    if not root.exists():
        return {"kind": "missing", "path": str(root)}
    return _walk_dir(root, depth=0, max_depth=max_depth)


def _walk_dir(d: pathlib.Path, depth: int, max_depth: int) -> dict:
    composition = detect_composition(d)
    node: dict[str, Any] = {
        "kind": composition,
        "path": str(d),
        "name": d.name,
        "children": [],
        "files": [],
    }
    # composition-level projections
    if composition == "marketplace":
        node["projection"] = project_marketplace_manifest(d / ".claude-plugin" / "marketplace.json")
    elif composition == "plugin":
        node["projection"] = project_plugin_manifest(d / ".claude-plugin" / "plugin.json")
        bs = d / "bootstrap.json"
        if bs.exists():
            node["bootstrap"] = project_bootstrap_manifest(bs)
    elif composition == "skill":
        node["projection"] = project_skill_md(d / "SKILL.md")
    if depth >= max_depth:
        return node
    try:
        entries = sorted(d.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    except (PermissionError, OSError):
        return node
    for child in entries:
        if child.name.startswith(".") and child.name not in {".claude", ".claude-plugin"}:
            continue
        if child.name in IGNORE_DIRS:
            continue
        if child.is_dir():
            child_node = _walk_dir(child, depth + 1, max_depth)
            # Skip plain directories with no compositional value at deeper levels
            if child_node["kind"] == "directory" and not child_node["children"] and not child_node["files"]:
                continue
            node["children"].append(child_node)
        elif child.is_file():
            file_node = _project_file(child)
            if file_node:
                node["files"].append(file_node)
    return node


def _project_file(p: pathlib.Path) -> dict | None:
    name = p.name
    suffix = p.suffix.lower()
    rel_kind = None
    proj: dict = {}
    if name == "SKILL.md":
        # SKILL.md is part of its parent skill composition's projection, not a separate file node
        return None
    if name == "CLAUDE.md":
        proj = project_claude_md(p)
        rel_kind = "claude_md"
    elif name == "plugin.json" and p.parent.name == ".claude-plugin":
        return None  # part of plugin composition
    elif name == "marketplace.json" and p.parent.name == ".claude-plugin":
        return None  # part of marketplace composition
    elif name == "bootstrap.json":
        return None  # part of plugin's bootstrap field
    elif suffix == ".md":
        # if we're inside a skill's references/, classify as reference_doc; otherwise plain
        parents = [par.name for par in p.parents]
        if "references" in parents:
            proj = project_reference_doc(p)
            rel_kind = "reference_doc"
        else:
            proj = project_plain_md(p)
            rel_kind = "plain_md"
    elif suffix in (".py", ".sh", ".bash", ".ps1", ".bat"):
        proj = project_script(p)
        rel_kind = "script"
    elif suffix == ".json":
        proj = {"kind": "json", "filename": name}
        rel_kind = "json"
    elif suffix in (".yaml", ".yml"):
        proj = {"kind": "yaml", "filename": name}
        rel_kind = "yaml"
    else:
        return None  # skip unknown file types in v1
    return {
        "kind": rel_kind,
        "path": str(p),
        "name": name,
        "projection": proj,
    }


def crawl(project_root: pathlib.Path | None) -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    roots = []
    # Claude user dir root
    if CLAUDE_DIR.exists():
        user_root = walk(CLAUDE_DIR / "plugins" / "marketplaces") if (CLAUDE_DIR / "plugins" / "marketplaces").exists() else {"kind": "missing", "path": str(CLAUDE_DIR / "plugins" / "marketplaces")}
        user_skills = walk(CLAUDE_DIR / "skills") if (CLAUDE_DIR / "skills").exists() else None
        roots.append({
            "kind": "claude_user_dir",
            "name": "Claude user directory",
            "path": str(CLAUDE_DIR),
            "marketplaces": user_root,
            "user_skills": user_skills,
        })
    # Project root
    if project_root and project_root.exists():
        roots.append({
            "kind": "project",
            "name": project_root.name,
            "path": str(project_root),
            "tree": walk(project_root),
        })
    index = {
        "version": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "roots": roots,
    }
    INDEX_PATH.write_text(json.dumps(index, indent=2), encoding="utf-8")
    return index


# ----------------------------------------------------------------------------
# Serve
# ----------------------------------------------------------------------------

ALLOWED_ROOTS: list[pathlib.Path] = []


class Handler(http.server.SimpleHTTPRequestHandler):
    project_root: pathlib.Path | None = None

    def log_message(self, format, *args):
        pass  # quiet

    def _send(self, status: int, body: bytes, content_type: str = "text/html; charset=utf-8"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/":
            self._send(200, HTML.encode("utf-8"))
        elif parsed.path == "/index.json":
            if INDEX_PATH.exists():
                self._send(200, INDEX_PATH.read_bytes(), "application/json")
            else:
                self._send(404, b'{"error":"no index; run crawl"}', "application/json")
        elif parsed.path == "/file":
            self._serve_file(urllib.parse.parse_qs(parsed.query))
        elif parsed.path == "/refresh":
            try:
                crawl(self.project_root)
                self._send(200, b'{"ok":true}', "application/json")
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def _serve_file(self, qs: dict):
        paths = qs.get("path", [])
        if not paths:
            self._send(400, b'{"error":"missing path"}', "application/json")
            return
        requested = pathlib.Path(paths[0]).resolve()
        # path-traversal guard: requested must be within ALLOWED_ROOTS
        ok = False
        for root in ALLOWED_ROOTS:
            try:
                requested.relative_to(root.resolve())
                ok = True
                break
            except ValueError:
                continue
        if not ok or not requested.exists() or not requested.is_file():
            self._send(403, b'{"error":"forbidden or not found"}', "application/json")
            return
        if requested.stat().st_size > 5_000_000:
            self._send(413, b'{"error":"file too large"}', "application/json")
            return
        try:
            body = requested.read_bytes()
        except Exception as e:
            self._send(500, json.dumps({"error": str(e)}).encode(), "application/json")
            return
        # content-type
        ct = "text/plain; charset=utf-8"
        if requested.suffix.lower() in (".json",):
            ct = "application/json"
        elif requested.suffix.lower() in (".md",):
            ct = "text/markdown; charset=utf-8"
        self._send(200, body, ct)


def serve(project_root: pathlib.Path, port: int = DEFAULT_PORT, open_browser: bool = True):
    Handler.project_root = project_root
    ALLOWED_ROOTS.append(CLAUDE_DIR)
    if project_root:
        ALLOWED_ROOTS.append(project_root)
    with socketserver.TCPServer(("127.0.0.1", port), Handler) as httpd:
        url = f"http://127.0.0.1:{port}/"
        print(f"claude-explorer serving at {url}")
        if open_browser:
            threading.Thread(target=lambda: (time.sleep(0.4), webbrowser.open(url)), daemon=True).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped.")


# ----------------------------------------------------------------------------
# Embedded SPA (HTML + CSS + JS)
# ----------------------------------------------------------------------------

HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>claude-explorer</title>
<style>
:root {
  --base: #1e1e2e;
  --mantle: #181825;
  --crust: #11111b;
  --surface0: #313244;
  --surface1: #45475a;
  --surface2: #585b70;
  --text: #cdd6f4;
  --subtext1: #bac2de;
  --subtext0: #a6adc8;
  --overlay0: #6c7086;
  --blue: #89b4fa;
  --lavender: #b4befe;
  --green: #a6e3a1;
  --yellow: #f9e2af;
  --peach: #fab387;
  --red: #f38ba8;
  --mauve: #cba6f7;
  --pink: #f5c2e7;
  --teal: #94e2d5;
  --sky: #89dceb;
  --rosewater: #f5e0dc;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: ui-monospace, "JetBrains Mono", "SF Mono", Menlo, Consolas, monospace;
  font-size: 13px;
  line-height: 1.5;
  background: var(--base);
  color: var(--text);
  min-height: 100vh;
}
header {
  background: var(--mantle);
  border-bottom: 1px solid var(--surface0);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 16px;
  position: sticky; top: 0; z-index: 10;
}
header .title { font-weight: 600; color: var(--lavender); }
header .meta { color: var(--overlay0); margin-left: auto; font-size: 11px; }
header button {
  background: var(--surface0);
  color: var(--text);
  border: 1px solid var(--surface1);
  padding: 4px 12px;
  font-family: inherit;
  font-size: 12px;
  cursor: pointer;
}
header button:hover { background: var(--surface1); }
header button.refreshing { color: var(--yellow); }
main {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1px;
  background: var(--surface0);
  min-height: calc(100vh - 42px);
}
.root-pane { background: var(--base); padding: 12px 16px; overflow: auto; }
.root-pane h2 {
  margin: 0 0 8px 0;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--overlay0);
  font-weight: 500;
}
.node {
  border-left: 2px solid var(--surface0);
  padding-left: 8px;
  margin: 2px 0 2px 4px;
}
.node-row {
  display: flex;
  align-items: baseline;
  cursor: pointer;
  gap: 6px;
  padding: 2px 4px;
  border-radius: 0;
}
.node-row:hover { background: var(--surface0); }
.node-row.focused { background: var(--surface1); }
.node-marker {
  display: inline-block;
  width: 1em;
  color: var(--overlay0);
  font-weight: 600;
  text-align: center;
}
.node-kind {
  display: inline-block;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 1px 5px;
  border: 1px solid var(--surface1);
  color: var(--subtext0);
  margin-right: 4px;
}
.kind-marketplace .node-kind { color: var(--peach); border-color: var(--peach); }
.kind-plugin .node-kind { color: var(--blue); border-color: var(--blue); }
.kind-skill .node-kind { color: var(--green); border-color: var(--green); }
.kind-claude_md .node-kind { color: var(--yellow); border-color: var(--yellow); }
.kind-reference_doc .node-kind { color: var(--teal); border-color: var(--teal); }
.kind-plain_md .node-kind { color: var(--subtext0); border-color: var(--surface1); }
.kind-script .node-kind { color: var(--mauve); border-color: var(--mauve); }
.kind-json .node-kind { color: var(--pink); border-color: var(--pink); }
.kind-yaml .node-kind { color: var(--rosewater); border-color: var(--rosewater); }
.kind-directory .node-kind { color: var(--overlay0); border-color: var(--surface0); }
.kind-claude_user_dir .node-kind, .kind-project .node-kind { color: var(--lavender); border-color: var(--lavender); }
.node-name { color: var(--text); }
.node-name.is-file { color: var(--subtext1); }
.node-meta { color: var(--overlay0); font-size: 11px; margin-left: 4px; }
.node-meta strong { color: var(--subtext0); font-weight: 400; }
.node-summary { color: var(--subtext0); padding-left: 22px; padding-bottom: 4px; font-size: 12px; }
.node-summary .label { color: var(--overlay0); }
.node-children { margin-left: 8px; display: none; }
.node.open > .node-children { display: block; }
.node.open > .node-row .node-marker { color: var(--blue); }
.deep { display: none; padding: 12px; background: var(--mantle); border: 1px solid var(--surface0); margin: 4px 0 8px 22px; max-height: 60vh; overflow: auto; }
.deep.open { display: block; }
.deep pre { margin: 0; white-space: pre-wrap; word-wrap: break-word; color: var(--subtext1); }
.deep .md h1, .deep .md h2, .deep .md h3 { color: var(--lavender); margin: 0.8em 0 0.4em 0; }
.deep .md h1 { font-size: 18px; }
.deep .md h2 { font-size: 15px; border-bottom: 1px solid var(--surface0); padding-bottom: 4px; }
.deep .md h3 { font-size: 13px; color: var(--blue); }
.deep .md code { color: var(--peach); background: var(--surface0); padding: 1px 4px; }
.deep .md pre { background: var(--crust); padding: 8px; border-left: 2px solid var(--surface1); }
.deep .md pre code { background: transparent; color: var(--subtext1); padding: 0; }
.deep .md a { color: var(--sky); }
.deep .md table { border-collapse: collapse; margin: 8px 0; }
.deep .md th, .deep .md td { border: 1px solid var(--surface1); padding: 4px 8px; text-align: left; }
.deep .md th { background: var(--surface0); color: var(--text); }
.deep .md blockquote { border-left: 2px solid var(--mauve); padding-left: 12px; color: var(--subtext0); margin: 8px 0; }
.deep table.kv { border-collapse: collapse; }
.deep table.kv td { padding: 2px 12px 2px 0; vertical-align: top; }
.deep table.kv td:first-child { color: var(--overlay0); }
.search {
  background: var(--surface0);
  color: var(--text);
  border: 1px solid var(--surface1);
  padding: 4px 8px;
  font-family: inherit;
  font-size: 12px;
  width: 240px;
}
.empty { color: var(--overlay0); padding: 16px; font-style: italic; }
footer {
  background: var(--mantle);
  border-top: 1px solid var(--surface0);
  padding: 6px 16px;
  color: var(--overlay0);
  font-size: 11px;
  text-align: right;
}
.kbd {
  font-size: 10px;
  color: var(--subtext0);
  border: 1px solid var(--surface1);
  padding: 1px 4px;
  background: var(--surface0);
  margin: 0 2px;
}
</style>
</head>
<body>
<header>
  <span class="title">claude-explorer</span>
  <input class="search" id="search" type="text" placeholder="/ to search">
  <button id="refresh">refresh</button>
  <span class="meta" id="meta">loading...</span>
</header>
<main>
  <section class="root-pane" id="left"><h2>Claude user directory</h2><div id="left-body" class="empty">loading...</div></section>
  <section class="root-pane" id="right"><h2>Project</h2><div id="right-body" class="empty">loading...</div></section>
</main>
<footer><span class="kbd">j</span>/<span class="kbd">k</span> navigate &nbsp; <span class="kbd">Enter</span> open &nbsp; <span class="kbd">o</span> deep-render &nbsp; <span class="kbd">Esc</span> close &nbsp; <span class="kbd">/</span> search</footer>
<script>
// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let INDEX = null;
let NODES = []; // flat list of visible node DOM elements for j/k nav
let focused = -1;

// ---------------------------------------------------------------------------
// Minimal markdown renderer (CommonMark subset)
// ---------------------------------------------------------------------------
function esc(s) { return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
function renderMarkdown(src) {
  const lines = src.split(/\r?\n/);
  let out = [];
  let inCode = false, codeLang = "", codeBuf = [];
  let inTable = false, tableRows = [];
  let inList = false, listType = null, listBuf = [];
  let inQuote = false, quoteBuf = [];
  let inPara = [], finalize = () => {
    if (inPara.length) { out.push("<p>" + inlineFmt(inPara.join(" ")) + "</p>"); inPara = []; }
    if (inList) { out.push("<" + listType + ">" + listBuf.join("") + "</" + listType + ">"); inList = false; listBuf = []; }
    if (inQuote) { out.push("<blockquote>" + inlineFmt(quoteBuf.join(" ")) + "</blockquote>"); inQuote = false; quoteBuf = []; }
    if (inTable) { out.push(renderTable(tableRows)); inTable = false; tableRows = []; }
  };
  for (let i = 0; i < lines.length; i++) {
    let line = lines[i];
    if (line.startsWith("```")) {
      if (inCode) { out.push('<pre><code class="lang-' + esc(codeLang) + '">' + esc(codeBuf.join("\n")) + "</code></pre>"); inCode = false; codeBuf = []; codeLang = ""; }
      else { finalize(); inCode = true; codeLang = line.slice(3).trim(); }
      continue;
    }
    if (inCode) { codeBuf.push(line); continue; }
    if (/^#{1,6}\s/.test(line)) {
      finalize();
      const m = line.match(/^(#{1,6})\s+(.*)$/);
      out.push("<h" + m[1].length + ">" + inlineFmt(m[2]) + "</h" + m[1].length + ">");
      continue;
    }
    if (/^\s*[-*+]\s/.test(line)) {
      if (inPara.length) { out.push("<p>" + inlineFmt(inPara.join(" ")) + "</p>"); inPara = []; }
      if (!inList || listType !== "ul") { if (inList) out.push("<" + listType + ">" + listBuf.join("") + "</" + listType + ">"); inList = true; listType = "ul"; listBuf = []; }
      listBuf.push("<li>" + inlineFmt(line.replace(/^\s*[-*+]\s+/, "")) + "</li>");
      continue;
    }
    if (/^\s*\d+\.\s/.test(line)) {
      if (inPara.length) { out.push("<p>" + inlineFmt(inPara.join(" ")) + "</p>"); inPara = []; }
      if (!inList || listType !== "ol") { if (inList) out.push("<" + listType + ">" + listBuf.join("") + "</" + listType + ">"); inList = true; listType = "ol"; listBuf = []; }
      listBuf.push("<li>" + inlineFmt(line.replace(/^\s*\d+\.\s+/, "")) + "</li>");
      continue;
    }
    if (/^>\s?/.test(line)) {
      if (!inQuote) { finalize(); inQuote = true; }
      quoteBuf.push(line.replace(/^>\s?/, ""));
      continue;
    }
    if (/^\|.*\|\s*$/.test(line)) {
      if (!inTable) { finalize(); inTable = true; }
      tableRows.push(line);
      continue;
    }
    if (line.trim() === "") { finalize(); continue; }
    if (inList || inQuote || inTable) finalize();
    inPara.push(line);
  }
  finalize();
  return out.join("\n");
}
function renderTable(rows) {
  if (rows.length < 2) return "<pre>" + esc(rows.join("\n")) + "</pre>";
  const split = r => r.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
  const header = split(rows[0]);
  const body = rows.slice(2).map(split);
  let html = "<table><thead><tr>" + header.map(c => "<th>" + inlineFmt(c) + "</th>").join("") + "</tr></thead><tbody>";
  for (const r of body) html += "<tr>" + r.map(c => "<td>" + inlineFmt(c) + "</td>").join("") + "</tr>";
  return html + "</tbody></table>";
}
function inlineFmt(s) {
  let out = esc(s);
  out = out.replace(/`([^`]+)`/g, (_, c) => "<code>" + c + "</code>");
  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
  return out;
}

// ---------------------------------------------------------------------------
// Render tree
// ---------------------------------------------------------------------------
function nodeRow(label, kind, meta, summaryLines, hasChildren, filePath, isFile) {
  const id = "node-" + (window._nodeIdSeq = (window._nodeIdSeq || 0) + 1);
  const marker = hasChildren ? "+" : (isFile ? "•" : " ");
  let html = '<div class="node kind-' + kind + '" id="' + id + '">';
  html += '<div class="node-row" data-id="' + id + '"';
  if (filePath) html += ' data-file="' + esc(filePath) + '" data-kind="' + kind + '"';
  html += '>';
  html += '<span class="node-marker">' + marker + '</span>';
  html += '<span class="node-kind">' + kind + '</span>';
  html += '<span class="node-name' + (isFile ? " is-file" : "") + '">' + esc(label) + '</span>';
  if (meta) html += '<span class="node-meta">' + meta + '</span>';
  html += '</div>';
  if (summaryLines && summaryLines.length) {
    html += '<div class="node-summary">' + summaryLines.map(s => '<div>' + s + '</div>').join("") + '</div>';
  }
  if (filePath) html += '<div class="deep" id="' + id + '-deep"></div>';
  return { html, hasChildren };
}
function metaPairs(pairs) {
  return pairs.filter(p => p[1] != null && p[1] !== "").map(p => '<strong>' + esc(p[0]) + '</strong>:' + esc(String(p[1]))).join(" &nbsp; ");
}
function fmtTokens(n) { return n >= 1000 ? (n/1000).toFixed(1) + "k" : String(n); }

function renderNode(n) {
  if (!n || n.kind === "missing") return '<div class="empty">missing</div>';
  const kind = n.kind;
  let label = n.name || (n.projection && n.projection.name) || "(unnamed)";
  let meta = "";
  let summary = [];
  if (kind === "marketplace") {
    const p = n.projection || {};
    meta = metaPairs([["plugins", p.plugin_count]]);
  } else if (kind === "plugin") {
    const p = n.projection || {};
    label = p.name || label;
    meta = metaPairs([["v", p.version]]);
    if (p.description) summary.push('<span class="label">desc</span>: ' + esc(p.description));
    if (p.razor) summary.push('<span class="label">razor</span>: ' + esc(p.razor));
  } else if (kind === "skill") {
    const p = n.projection || {};
    label = p.name || label;
    meta = metaPairs([["type", p.skill_type], ["author", p.author], ["lines", p.body_lines], ["tok", fmtTokens(p.body_tokens || 0)]]);
    if (p.description) summary.push('<span class="label">desc</span>: ' + esc(p.description));
  } else if (kind === "claude_user_dir") {
    label = "~/.claude/";
  } else if (kind === "project") {
    label = n.name + " (project)";
  } else if (kind === "directory") {
    // skip plain-named uninteresting dirs in summary
  }
  const childrenHtml = [];
  if (n.marketplaces) childrenHtml.push(renderNode({ ...n.marketplaces, name: "marketplaces" }));
  if (n.user_skills) childrenHtml.push(renderNode({ ...n.user_skills, name: "user skills" }));
  if (n.tree) childrenHtml.push(renderNode(n.tree));
  if (n.children) for (const c of n.children) childrenHtml.push(renderNode(c));
  if (n.files) for (const f of n.files) childrenHtml.push(renderFile(f));
  const hasChildren = childrenHtml.length > 0;
  const row = nodeRow(label, kind, meta, summary, hasChildren, null, false);
  let html = row.html.replace("</div>", "</div>"); // marker placeholder
  // inject children
  html = html.replace(/<\/div>$/, "");
  if (hasChildren) html += '<div class="node-children">' + childrenHtml.join("") + "</div>";
  html += "</div>";
  return html;
}

function renderFile(f) {
  const k = f.kind;
  const p = f.projection || {};
  let label = p.filename || f.name;
  let meta = "";
  let summary = [];
  if (k === "claude_md") {
    if (p.scope_directory) summary.push('<span class="label">scope</span>: ' + esc(p.scope_directory));
    if (p.scope_covers && p.scope_covers.length) summary.push('<span class="label">covers</span>: ' + p.scope_covers.slice(0, 3).map(esc).join(" | "));
    meta = metaPairs([["lines", p.lines]]);
  } else if (k === "reference_doc" || k === "plain_md") {
    if (p.first_heading) summary.push('<span class="label">#</span> ' + esc(p.first_heading));
    if (p.first_lines) summary.push(esc(p.first_lines));
    meta = metaPairs([["lines", p.lines]]);
  } else if (k === "script") {
    if (p.leading_doc) summary.push(esc(p.leading_doc));
    meta = metaPairs([["lang", p.language], ["lines", p.lines]]);
  } else if (k === "json" || k === "yaml") {
    // no projection yet
  }
  const row = nodeRow(label, k, meta, summary, false, f.path, true);
  return row.html;
}

function attachHandlers() {
  document.querySelectorAll(".node-row").forEach(row => {
    row.addEventListener("click", ev => {
      ev.stopPropagation();
      const id = row.getAttribute("data-id");
      const node = document.getElementById(id);
      const file = row.getAttribute("data-file");
      if (file) {
        toggleDeep(id, file, row.getAttribute("data-kind"));
      } else if (node) {
        node.classList.toggle("open");
        rebuildNodeList();
      }
    });
  });
}

async function toggleDeep(id, path, kind) {
  const deep = document.getElementById(id + "-deep");
  if (!deep) return;
  if (deep.classList.contains("open")) { deep.classList.remove("open"); deep.innerHTML = ""; return; }
  deep.classList.add("open");
  deep.innerHTML = '<div class="empty">loading...</div>';
  try {
    const resp = await fetch("/file?path=" + encodeURIComponent(path));
    if (!resp.ok) { deep.innerHTML = '<div class="empty">error: ' + resp.status + '</div>'; return; }
    const txt = await resp.text();
    if (kind === "json") {
      try { const data = JSON.parse(txt); deep.innerHTML = renderJsonKV(data); }
      catch { deep.innerHTML = "<pre>" + esc(txt) + "</pre>"; }
    } else if (kind === "yaml") {
      deep.innerHTML = "<pre>" + esc(txt) + "</pre>";
    } else if (kind === "script") {
      deep.innerHTML = "<pre>" + esc(txt) + "</pre>";
    } else { // md kinds
      deep.innerHTML = '<div class="md">' + renderMarkdown(txt) + "</div>";
    }
  } catch (e) {
    deep.innerHTML = '<div class="empty">error: ' + esc(String(e)) + '</div>';
  }
}

function renderJsonKV(data, depth=0) {
  if (data === null || data === undefined) return '<em>null</em>';
  if (typeof data !== "object") return esc(String(data));
  if (Array.isArray(data)) {
    if (data.length === 0) return '<em>[]</em>';
    return '<table class="kv">' + data.map((v, i) => '<tr><td>[' + i + ']</td><td>' + renderJsonKV(v, depth+1) + '</td></tr>').join("") + '</table>';
  }
  const keys = Object.keys(data);
  if (keys.length === 0) return '<em>{}</em>';
  return '<table class="kv">' + keys.map(k => '<tr><td>' + esc(k) + '</td><td>' + renderJsonKV(data[k], depth+1) + '</td></tr>').join("") + '</table>';
}

function rebuildNodeList() {
  NODES = Array.from(document.querySelectorAll(".node-row"));
  if (focused >= NODES.length) focused = NODES.length - 1;
}

// ---------------------------------------------------------------------------
// Keyboard nav
// ---------------------------------------------------------------------------
document.addEventListener("keydown", ev => {
  if (ev.target.tagName === "INPUT") {
    if (ev.key === "Escape") { ev.target.value=""; doSearch(""); ev.target.blur(); }
    return;
  }
  if (ev.key === "/") { ev.preventDefault(); document.getElementById("search").focus(); return; }
  if (ev.key === "j" || ev.key === "ArrowDown") { ev.preventDefault(); moveFocus(1); }
  else if (ev.key === "k" || ev.key === "ArrowUp") { ev.preventDefault(); moveFocus(-1); }
  else if (ev.key === "Enter" || ev.key === " ") {
    ev.preventDefault();
    if (focused >= 0 && NODES[focused]) NODES[focused].click();
  } else if (ev.key === "Escape") {
    document.querySelectorAll(".deep.open").forEach(d => { d.classList.remove("open"); d.innerHTML = ""; });
  }
});
function moveFocus(delta) {
  rebuildNodeList();
  if (!NODES.length) return;
  if (focused >= 0 && NODES[focused]) NODES[focused].classList.remove("focused");
  focused = Math.max(0, Math.min(NODES.length-1, focused + delta));
  NODES[focused].classList.add("focused");
  NODES[focused].scrollIntoView({block: "nearest"});
}

// ---------------------------------------------------------------------------
// Search
// ---------------------------------------------------------------------------
function doSearch(q) {
  q = q.trim().toLowerCase();
  const all = document.querySelectorAll(".node");
  if (!q) { all.forEach(n => n.style.display = ""); return; }
  all.forEach(n => {
    const text = n.querySelector(".node-row").textContent.toLowerCase();
    n.style.display = text.includes(q) ? "" : "none";
  });
}
document.getElementById("search").addEventListener("input", ev => doSearch(ev.target.value));

// ---------------------------------------------------------------------------
// Refresh
// ---------------------------------------------------------------------------
async function refresh() {
  const btn = document.getElementById("refresh");
  btn.classList.add("refreshing");
  btn.textContent = "refreshing...";
  try {
    await fetch("/refresh");
    await load();
  } finally {
    btn.classList.remove("refreshing");
    btn.textContent = "refresh";
  }
}
document.getElementById("refresh").addEventListener("click", refresh);

// ---------------------------------------------------------------------------
// Load
// ---------------------------------------------------------------------------
async function load() {
  try {
    const resp = await fetch("/index.json");
    if (!resp.ok) { document.getElementById("left-body").innerHTML = '<div class="empty">no index</div>'; return; }
    INDEX = await resp.json();
    document.getElementById("meta").textContent = "generated " + (INDEX.generated_at || "?").replace("T", " ").replace(/\.\d+Z?$/, "");
    const userRoot = INDEX.roots.find(r => r.kind === "claude_user_dir");
    const project = INDEX.roots.find(r => r.kind === "project");
    document.getElementById("left-body").innerHTML = userRoot ? renderNode(userRoot) : '<div class="empty">no user dir</div>';
    document.getElementById("right-body").innerHTML = project ? renderNode(project) : '<div class="empty">no project</div>';
    attachHandlers();
    rebuildNodeList();
  } catch (e) {
    document.getElementById("left-body").innerHTML = '<div class="empty">error: ' + e + '</div>';
  }
}

load();
</script>
</body>
</html>
"""


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="claude-explorer")
    parser.add_argument("command", nargs="?", default="run", choices=["crawl", "serve", "run"])
    parser.add_argument("--project", type=pathlib.Path, default=pathlib.Path.cwd())
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)

    if args.command in ("crawl", "run"):
        print(f"crawl: scanning {args.project} ...")
        idx = crawl(args.project)
        roots = idx.get("roots", [])
        print(f"crawl: wrote index with {len(roots)} roots to {INDEX_PATH}")
    if args.command in ("serve", "run"):
        serve(args.project, port=args.port, open_browser=not args.no_open)
    return 0


if __name__ == "__main__":
    sys.exit(main())
