#!/usr/bin/env python3
"""Convert an HTML file to PDF via headless Chromium, then open it in the
system default web browser.

Chromium (Playwright) is used -- not a pure-Python PDF lib -- so CSS, web fonts,
the page's dark/light theme, and any JS run exactly as they do in a real browser.

Default mode is SINGLE-PAGE: the PDF page is sized to the content's real pixel
height, so there is no A4 pagination and therefore no blank gaps from
`break-inside: avoid` blocks being pushed to the next page (the classic
poster-paginated-to-A4 problem). Use --a4 to paginate to A4 instead, which
honors the page's own @media print rules.

Playwright is imported lazily inside convert() so this module can be imported
(e.g. by tests) without the browser dependency installed.

Usage:
    python html_to_pdf.py <input.html> [output.pdf] [--a4] [--width PX] [--no-open]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import webbrowser
from pathlib import Path


# --------------------------------------------------------------------------
# Pure helpers (unit-tested; no browser / OS side effects)
# --------------------------------------------------------------------------
def default_output_path(input_path) -> Path:
    """PDF path next to the input, same stem with a .pdf suffix."""
    return Path(input_path).with_suffix(".pdf")


def exe_from_command(command: str):
    """Extract the executable path from a Windows shell 'open' command string.

    Registry command values look like:
        "C:\\Program Files\\...\\msedge.exe" --single-argument %1
        C:\\Windows\\system32\\rundll32.exe ...,%1     (unquoted, no spaces in exe)
    Returns the exe path, or None if it can't be parsed.
    """
    command = (command or "").strip()
    if not command:
        return None
    if command.startswith('"'):
        end = command.find('"', 1)
        if end == -1:
            return None
        return command[1:end] or None
    # Unquoted: best-effort -- the exe is the token before the first space.
    return command.split(" ", 1)[0] or None


# --------------------------------------------------------------------------
# Browser launch
# --------------------------------------------------------------------------
def _windows_default_browser():
    """Resolve the default browser executable from the Windows registry.

    Reads the user's chosen handler for https (then http), maps the ProgId to
    its shell open command, and extracts the exe. Returns None off-Windows or
    if anything is unreadable.
    """
    try:
        import winreg
    except ImportError:
        return None

    for scheme in ("https", "http"):
        try:
            key = (
                r"Software\Microsoft\Windows\Shell\Associations"
                rf"\UrlAssociations\{scheme}\UserChoice"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
                progid = winreg.QueryValueEx(k, "ProgId")[0]
            with winreg.OpenKey(
                winreg.HKEY_CLASSES_ROOT, rf"{progid}\shell\open\command"
            ) as k:
                command = winreg.QueryValueEx(k, "")[0]
        except OSError:
            continue
        exe = exe_from_command(command)
        if exe and Path(exe).exists():
            return exe
    return None


def open_in_default_browser(pdf_path) -> bool:
    """Open the PDF in the system default web browser. Returns True on launch.

    On Windows the default *web browser* is resolved explicitly (so a local PDF
    opens in the browser, not whatever app owns the .pdf association). Elsewhere
    the stdlib webbrowser controller handles it.
    """
    uri = Path(pdf_path).resolve().as_uri()
    if sys.platform.startswith("win"):
        exe = _windows_default_browser()
        if exe:
            try:
                subprocess.Popen([exe, uri])
                return True
            except OSError:
                pass
    return webbrowser.open(uri)


# --------------------------------------------------------------------------
# Conversion (requires Playwright + a Chromium browser)
# --------------------------------------------------------------------------
def convert(input_path, output_path, *, a4: bool = False, width: int = 1280) -> Path:
    from playwright.sync_api import sync_playwright

    src = Path(input_path).expanduser().resolve()
    out = Path(output_path).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            if a4:
                page = browser.new_page()
                page.goto(src.as_uri(), wait_until="networkidle")
                # A4 mode: let the page's own @media print rules apply (white bg, etc.).
                page.pdf(
                    path=str(out),
                    print_background=True,
                    prefer_css_page_size=True,
                    format="A4",
                    margin={"top": "0.4in", "bottom": "0.4in",
                            "left": "0.4in", "right": "0.4in"},
                )
            else:
                # Single-page: render at a fixed layout width, measure the real
                # content height, emit one page exactly that tall -> no pagination.
                page = browser.new_page(viewport={"width": width, "height": 1000})
                page.goto(src.as_uri(), wait_until="networkidle")
                page.emulate_media(media="screen")  # keep the on-screen design
                height = page.evaluate(
                    "Math.ceil(Math.max("
                    "document.documentElement.scrollHeight,"
                    "document.body.scrollHeight))"
                )
                page.pdf(
                    path=str(out),
                    print_background=True,
                    width=f"{width}px",
                    height=f"{height}px",
                    margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                )
        finally:
            browser.close()
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Convert an HTML file to PDF and open it in the default browser."
    )
    ap.add_argument("input", help="path to the HTML file to convert")
    ap.add_argument("output", nargs="?",
                    help="output PDF path (default: <input>.pdf next to the input)")
    ap.add_argument("--a4", action="store_true",
                    help="paginate to A4 using the page's @media print styles")
    ap.add_argument("--width", type=int, default=1280,
                    help="layout width in CSS px for single-page mode (default 1280)")
    ap.add_argument("--no-open", action="store_true",
                    help="write the PDF but do not open it in the browser")
    args = ap.parse_args()

    src = Path(args.input).expanduser()
    if not src.is_file():
        raise SystemExit(f"ERROR input not found or not a file: {src}")
    out = Path(args.output).expanduser() if args.output else default_output_path(src)

    out = convert(src, out, a4=args.a4, width=args.width)
    print(f"PDF {out}")

    if not args.no_open:
        if open_in_default_browser(out):
            print("OPENED in default browser")
        else:
            print(f"OPEN-FAILED -- open it manually: {out}")


if __name__ == "__main__":
    main()
