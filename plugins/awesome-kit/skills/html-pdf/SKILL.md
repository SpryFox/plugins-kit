---
_schema_version: 1
name: html-pdf
author: christina
skill-type: technique-skill
description: Use when asked to convert an HTML file to a PDF and open it. Do NOT use for non-HTML inputs, PDF editing, or page screenshots.
disable-model-invocation: true
---

# html-pdf

Convert an HTML file to a PDF and open it in the system default web browser.

Rendering goes through **headless Chromium** (Playwright), so CSS, web fonts,
the page's dark/light theme, and any JavaScript run exactly as in a real
browser. The work is a deterministic facade script
(`scripts/html_to_pdf.py`); this skill decides the input/output paths and
relays the result.

## Engine & modes (reference)

| Aspect | Detail |
|---|---|
| Engine | Headless Chromium via Playwright (provisioned by the plugin venv + `custom_bootstrap` chromium install). |
| Default mode | Single-page -- PDF page sized to the content's real height, so there are no A4 pagination blank-gaps. Suits posters and diagram pages. |
| `--a4` | Paginates to A4 and honors the page's own `@media print` rules (white background, page breaks). |
| Default output | `<input>.pdf` next to the input file; pass an explicit second argument to override. |
| `--scale` | Fraction (`0.8`) or percent (`80%` / `80`). Range 10%-200%, default 100%. When the user says "scale it to 80%", pass `--scale 80%`. |
| Invocation | `uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/skills/html-pdf/scripts/html_to_pdf.py" <input.html> [output.pdf] [--scale 80%] [--a4]` |

## Technique

The load-bearing contract; the table above is reference detail the steps draw on.

```yaml
technique_skill:
  _schema_version: "1"
  trigger_model: user-only
  identity: Convert an HTML file to a PDF via headless Chromium and open it in the default browser.

  scope:
    covers:
      - rendering a local .html file to a .pdf with full CSS/JS fidelity
      - opening the resulting PDF in the system default web browser
      - choosing single-page (poster) vs A4-paginated output
    excludes:
      - non-HTML inputs (markdown, images, URLs) -- this takes a local HTML file
      - editing, merging, or annotating existing PDFs
      - capturing a screenshot/PNG of a page (this produces a PDF)

  techniques:
    - id: convert
      name: Convert an HTML file to a PDF and open it
      keywords: [html to pdf, convert html, render pdf, html pdf, export pdf, print to pdf, open pdf, scale, scale to 80%, percent, shrink, zoom]
      goal: Render a local HTML file to a PDF via headless Chromium at the chosen mode and scale, then open it in the default browser.
      steps:
        - n: 1
          action: Resolve the input HTML file
          detail: >-
            Take the .html path the user referenced and confirm it exists. The input must be
            a local HTML file. For best results it should be self-contained -- a page that
            pulls in sibling files or local-disk asset paths will convert but render broken.
        - n: 2
          action: Decide the output path, mode, and scale
          detail: >-
            Default output is <input>.pdf beside the input; pass an explicit second argument to
            override. Default rendering is single-page (no blank gaps), which suits posters and
            diagram pages. Use --a4 only when the user wants a paginated, print-style document.
            If the user asks to scale ("scale it to 80%", "make it 80%", "0.8"), pass --scale 80%
            -- it shrinks/grows the whole rendering; in single-page mode the page resizes with it
            so there is no surrounding whitespace.
        - n: 3
          action: Run the converter
          tool: ${CLAUDE_PLUGIN_ROOT}/skills/html-pdf/scripts/html_to_pdf.py
          precondition: >-
            Before running, confirm bootstrap has provisioned html-pdf: if
            ~/.claude/plugins/data/plugins-kit/awesome-kit/bootstrap.log is missing, tell the user
            "the bootstrap plugin hasn't provisioned awesome-kit's html-pdf -- install/enable
            plugins-kit:bootstrap and start a new session" and stop (the venv + Chromium aren't set up).
          detail: 'uv run --project "${CLAUDE_PLUGIN_ROOT}" python "${CLAUDE_PLUGIN_ROOT}/skills/html-pdf/scripts/html_to_pdf.py" "<input.html>" ["<output.pdf>"] [--scale 80%] [--a4]'
        - n: 4
          action: Relay the result
          detail: >-
            The script prints `PDF <path>` then `OPENED in default browser` (or `OPEN-FAILED ...`).
            It opens the PDF in the default browser automatically; pass --no-open to skip that.
            Give the user the output path and confirm it opened.
      output_template: |
        Converted -> <output.pdf> (opened in your default browser).
      gotchas:
        - id: needs_chromium
          keywords: [playwright, chromium, browser not installed, executable doesn't exist]
          gotcha: >-
            Requires the Chromium browser binary. Bootstrap installs it (custom_bootstrap.py). If
            the converter errors that the browser is missing, install it manually:
            `uv run --project "${CLAUDE_PLUGIN_ROOT}" python -m playwright install chromium`.
        - id: self_contained_only
          keywords: [broken page, missing css, external assets, fragment, relative paths]
          gotcha: Only self-contained HTML renders correctly. External stylesheets/scripts over the network load, but sibling-file and local-disk asset references render broken in the PDF.
        - id: single_page_default
          keywords: [blank space, blank pages, pagination gaps, a4, poster]
          gotcha: >-
            Default single-page mode avoids the blank gaps that A4 pagination creates when tall
            `break-inside: avoid` blocks jump to the next page. Reach for --a4 only when a true
            paginated/printable document is wanted; expect some bottom-of-page whitespace then.
        - id: opens_browser_not_reader
          keywords: [opened in pdf app, default handler, wrong app, system default browser]
          gotcha: >-
            On Windows the default *web browser* is resolved from the registry so the PDF opens in
            the browser, not the .pdf-associated app. If no browser resolves, it falls back to the
            stdlib opener, which may use the OS default handler instead.
        - id: overwrites_output
          keywords: [overwrite, existing pdf, clobber]
          gotcha: The output path is overwritten without prompting. Use a distinct output name to keep a prior PDF.
```
