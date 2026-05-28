#!/usr/bin/env python3
"""
md2book.py — Convert a Markdown file with YAML front matter into a
             beautiful single-file HTML book, ready to print-to-PDF.

Usage:
    python md2book.py input.md
    python md2book.py input.md -o mybook.html
    python md2book.py input.md --title "Override Title"
"""

import re
import sys
import argparse
import base64
import mimetypes
import urllib.request
from pathlib import Path

import yaml
import markdown
from pygments.formatters import HtmlFormatter

PYGMENTS_CSS = HtmlFormatter(style='friendly', nobackground=True).get_style_defs('.codehilite')




# ─────────────────────────────────────────────────────────────────────────────
# Style override map — semantic name → CSS selector
# ─────────────────────────────────────────────────────────────────────────────

STYLE_SELECTORS = {
    # Interior page
    'h1':               '.page:not(.cover) h1',
    'h2':               '.page:not(.cover) h2',
    'h3':               '.page:not(.cover) h3',
    'h4':               '.page:not(.cover) h4',
    'h5':               '.page:not(.cover) h5',
    'body_text':        '.page:not(.cover) p',
    'blockquote': [
        '.page:not(.cover) blockquote',
        '.page:not(.cover) blockquote p',
    ],
    'link':             '.page:not(.cover) a',
    'code_inline':      '.page:not(.cover) code',
    'code_block': [
        '.page:not(.cover) pre',
        '.page:not(.cover) pre code',
    ],
    # Admonitions — each entry is a list so child text elements are also targeted,
    # which is necessary to override the general `.page:not(.cover) p` font rules.
    'callout': [
        '.page:not(.cover) .admonition',
        '.page:not(.cover) .admonition p',
        '.page:not(.cover) .admonition .admonition-title',
    ],
    'callout_tip': [
        '.page:not(.cover) .admonition.tip',
        '.page:not(.cover) .admonition.tip p',
        '.page:not(.cover) .admonition.tip .admonition-title',
    ],
    'callout_warning': [
        '.page:not(.cover) .admonition.warning',
        '.page:not(.cover) .admonition.warning p',
        '.page:not(.cover) .admonition.warning .admonition-title',
    ],
    'callout_note': [
        '.page:not(.cover) .admonition.note',
        '.page:not(.cover) .admonition.note p',
        '.page:not(.cover) .admonition.note .admonition-title',
    ],
    'callout_important': [
        '.page:not(.cover) .admonition.important',
        '.page:not(.cover) .admonition.important p',
        '.page:not(.cover) .admonition.important .admonition-title',
    ],
    'callout_example': [
        '.page:not(.cover) .admonition.example',
        '.page:not(.cover) .admonition.example p',
        '.page:not(.cover) .admonition.example .admonition-title',
    ],
    # Cover
    'cover':            '.cover',
    'cover_title':      '.cover h1',
    'cover_subtitle':   '.cover h2',
    'cover_author':     '.cover .author',
    'cover_blurb':      '.cover .blurb',
}


def build_google_fonts_import(font_names):
    """Generate a Google Fonts @import for a list of family names."""
    if not font_names:
        return ''
    families = []
    for name in font_names:
        encoded = name.replace(' ', '+')
        families.append(f'family={encoded}:ital,wght@0,400;0,700;1,400')
    url = 'https://fonts.googleapis.com/css2?' + '&'.join(families) + '&display=swap'
    return f"@import url('{url}');"


def build_style_overrides(styles):
    """Convert a {name: css_props} dict from front matter into a CSS override block."""
    if not styles:
        return ''
    lines = ['/* User style overrides */']
    for name, props in styles.items():
        selectors = STYLE_SELECTORS.get(name)
        if selectors is None:
            print(f"Warning: unknown style name '{name}' — skipped")
            continue
        if isinstance(selectors, str):
            selectors = [selectors]
        for selector in selectors:
            lines.append(f'{selector} {{ {props} }}')
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# CSS — embedded in the output HTML (minified-ish but readable for editing)
# ─────────────────────────────────────────────────────────────────────────────

BOOK_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

:root {
  --page-width:    6in;
  --page-height:   9in;
  --color-bg:      #fffdf8;
  --color-text:    #2a2118;
  --color-heading: #1a1208;
  --color-accent:  %(accent_color)s;
  --color-rule:    #c8a97e;
  --font-heading:  %(font_heading)s;
  --font-body:     %(font_body)s;
  --font-code:     %(font_code)s;
  --margin-outer:  %(margin_outer)s;
  --margin-inner:  %(margin_inner)s;
  --margin-top:    %(margin_top)s;
  --margin-bottom: %(margin_bottom)s;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

body {
  background: #d4cfc8;
  font-family: var(--font-body);
  color: var(--color-text);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 32px;
  padding: 40px 20px;
}

.page {
  width: var(--page-width);
  height: var(--page-height);
  background: var(--color-bg);
  overflow: hidden;
  position: relative;
  padding: var(--margin-top) var(--margin-outer) var(--margin-bottom) var(--margin-inner);
  box-shadow: 0 4px 24px rgba(0,0,0,0.18), 0 1px 4px rgba(0,0,0,0.10);
}

.page:not(.cover):not(.has-header)::before {
  content: '';
  display: block;
  position: absolute;
  top: 0.45in;
  left: var(--margin-inner);
  right: var(--margin-outer);
  height: 1px;
  background: linear-gradient(to right, var(--color-rule), transparent);
  opacity: 0.5;
}

/* Interior headings */
.page:not(.cover) h1 {
  font-family: var(--font-body);
  font-size: 1.0rem;
  font-weight: 400;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin-bottom: 0.12in;
}
.page:not(.cover) h2 {
  font-family: var(--font-heading);
  font-size: 1.3rem;
  font-weight: 700;
  color: var(--color-heading);
  line-height: 1.0;
  margin-bottom: 0.12in;
}
.page:not(.cover) h3 {
  font-family: var(--font-heading);
  font-style: italic;
  font-weight: 400;
  font-size: 1rem;
  color: var(--color-accent);
  margin-bottom: 0.25in;
}
.page:not(.cover) h4 {
  font-family: var(--font-heading);
  font-size: 0.95rem;
  font-weight: 700;
  color: var(--color-heading);
  letter-spacing: 0.03em;
  margin-top: 0.2in;
  margin-bottom: 0.1in;
}
.page:not(.cover) h5 {
  font-family: var(--font-body);
  font-size: 0.8rem;
  font-weight: 600;
  font-style: italic;
  color: var(--color-accent);
  margin-top: 0.15in;
  margin-bottom: 0.08in;
}
.page:not(.cover) hr {
  width: 1.5in;
  height: 2px;
  background: linear-gradient(to right, var(--color-accent), transparent);
  margin-bottom: 0.3in;
  border: none;
}
.page:not(.cover) p {
  font-family: var(--font-body);
  font-size: 0.875rem;
  line-height: 1.75;
  color: var(--color-text);
  margin-bottom: 0.18in;
  text-align: left;
  hyphens: auto;
}
/* Extra bottom margin on first paragraph to clear space below the drop cap */
.page:not(.cover) > p:first-of-type {
  margin-bottom: 0.25in;
}
.page:not(.cover) > p:first-of-type::first-letter {
  font-family: var(--font-heading);
  font-size: 3.2rem;
  font-weight: 700;
  color: var(--color-accent);
  float: left;
  line-height: 0.8;
  margin-right: 0.03in;
  margin-top: 0.04in;
}
/* Disable drop cap when page has .no-drop-cap */
.page.no-drop-cap > p:first-of-type { margin-bottom: 0.18in; }
.page.no-drop-cap > p:first-of-type::first-letter {
  font-size: inherit; font-weight: inherit; color: inherit;
  float: none; line-height: inherit; margin: 0;
}
/* Clear drop cap float for everything that follows the first paragraph */
.page:not(.cover) p + p,
.page:not(.cover) p + h4,
.page:not(.cover) p + h5,
.page:not(.cover) p + ul,
.page:not(.cover) p + ol,
.page:not(.cover) p + blockquote,
.page:not(.cover) p + pre,
.page:not(.cover) p + hr {
  clear: both;
}
.page:not(.cover) blockquote {
  border-left: 3px solid var(--color-accent);
  background: rgba(200, 169, 126, 0.12);
  border-radius: 0 3px 3px 0;
  margin: 0.2in 0 0.2in 0.1in;
  padding: 0.1in 0.15in 0.1in 0.18in;
  font-style: italic;
  color: var(--color-text);
  font-size: 0.875rem;
  line-height: 1.7;
}
.page:not(.cover) ul,
.page:not(.cover) ol {
  font-size: 0.875rem;
  line-height: 1.75;
  color: var(--color-text);
  margin-bottom: 0.18in;
  padding-left: 0.25in;
}
.page:not(.cover) li { margin-bottom: 0.05in; }

/* Fix: markdown sometimes wraps li content in <p> tags — keep them tight */
.page:not(.cover) li p {
  margin-bottom: 0;
}

/* ============================================================
   ADMONITION BOXES  (!!! tip / warning / note / important / example)
   ============================================================ */
.page:not(.cover) .admonition {
  border-radius: 3px;
  margin: 0.18in 0;
  padding: 0.12in 0.15in 0.12in 0.5in;
  position: relative;
  clear: both;
  font-size: 0.85rem;
  line-height: 1.6;
}
/* Icon — injected via ::before on the title */
.page:not(.cover) .admonition-title {
  font-family: var(--font-body);
  font-weight: 600;
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  margin-bottom: 0.05in;
  padding-left: 0;
}
.page:not(.cover) .admonition-title::before {
  position: absolute;
  left: 0.12in;
  top: 0.1in;
  font-size: 1.1rem;
  line-height: 1;
}
.page:not(.cover) .admonition p {
  margin-bottom: 0.06in;
  font-size: 0.85rem;
  text-align: left;
  hyphens: none;
}
.page:not(.cover) .admonition p:last-child {
  margin-bottom: 0;
}
/* Kill drop cap inside admonitions */
.page:not(.cover) .admonition p::first-letter {
  font-size: inherit;
  font-weight: inherit;
  color: inherit;
  float: none;
  line-height: inherit;
  margin: 0;
}

/* tip — green */
.page:not(.cover) .admonition.tip {
  background: #f0f7f0;
  border-left: 3px solid #5a9e5a;
}
.page:not(.cover) .admonition.tip .admonition-title {
  color: #3a7a3a;
}
.page:not(.cover) .admonition.tip .admonition-title::before {
  content: '💡';
}

/* warning — amber */
.page:not(.cover) .admonition.warning {
  background: #fdf7ed;
  border-left: 3px solid #d4940a;
}
.page:not(.cover) .admonition.warning .admonition-title {
  color: #a06d00;
}
.page:not(.cover) .admonition.warning .admonition-title::before {
  content: '⚠️';
}

/* note — blue */
.page:not(.cover) .admonition.note {
  background: #f0f4fa;
  border-left: 3px solid #5a7ec0;
}
.page:not(.cover) .admonition.note .admonition-title {
  color: #3a5ea0;
}
.page:not(.cover) .admonition.note .admonition-title::before {
  content: '📝';
}

/* important — red */
.page:not(.cover) .admonition.important {
  background: #fdf0f0;
  border-left: 3px solid #c05a5a;
}
.page:not(.cover) .admonition.important .admonition-title {
  color: #a03a3a;
}
.page:not(.cover) .admonition.important .admonition-title::before {
  content: '❗';
}

/* example — purple */
.page:not(.cover) .admonition.example {
  background: #f5f0fa;
  border-left: 3px solid #8a5ac0;
}
.page:not(.cover) .admonition.example .admonition-title {
  color: #6a3aa0;
}
.page:not(.cover) .admonition.example .admonition-title::before {
  content: '🔍';
}

/* Tables */
.page:not(.cover) table {
  width: 100%%;
  border-collapse: collapse;
  margin-bottom: 0.18in;
  font-family: var(--font-body);
  font-size: 0.8rem;
  line-height: 1.5;
}
.page:not(.cover) thead {
  background: var(--color-accent);
}
.page:not(.cover) thead th {
  color: #fffdf8;
  font-family: var(--font-body);
  font-weight: 600;
  letter-spacing: 0.05em;
  text-align: left;
  padding: 0.06in 0.1in;
  border: none;
}
.page:not(.cover) tbody tr:nth-child(even) {
  background: #f0ebe3;
}
.page:not(.cover) tbody tr:nth-child(odd) {
  background: #fffdf8;
}
.page:not(.cover) tbody td {
  color: var(--color-text);
  padding: 0.05in 0.1in;
  border-bottom: 1px solid #ddd5c8;
}

/* Links */
.page:not(.cover) a {
  color: #2a5db0;
  text-decoration: none;
}
.page:not(.cover) a:hover {
  text-decoration: underline;
}

/* Inline code */
.page:not(.cover) code {
  font-family: var(--font-code);
  font-size: 0.8rem;
  background: #f0ebe3;
  color: #8b4513;
  padding: 0.01in 0.05in;
  border-radius: 2px;
  border: 1px solid #ddd5c8;
  font-variant-ligatures: none;
}

/* Code blocks */
.page:not(.cover) pre {
  background: #ede8df;
  border-left: 3px solid var(--color-accent);
  border-radius: 3px;
  padding: 0.15in 0.18in;
  margin-top: 0.18in;
  margin-bottom: 0.18in;
  overflow: hidden;
}
.page:not(.cover) pre code {
  font-family: var(--font-code);
  font-size: 0.78rem;
  line-height: 1.6;
  color: #2a2118;
  background: none;
  border: none;
  padding: 0;
  border-radius: 0;
  display: block;
  white-space: pre;
}

/* ============================================================
   HEADERS AND FOOTERS
   ============================================================ */
.page-header, .page-footer {
  position: absolute;
  left: var(--margin-inner);
  width: calc(var(--page-width) - var(--margin-outer) - var(--margin-inner));
  font-family: var(--font-body);
  font-size: 0.65rem;
  color: var(--color-rule);
  letter-spacing: 0.1em;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}
.page-header { top: 0.45in; }
.page-footer { bottom: 0.45in; }
.hf-content {
  display: flex;
  flex-direction: row;
  align-items: center;
  width: 100%%;
}
.hf-right { margin-left: auto; }
.hf-center { margin: 0 auto; }
/* Inline rule — expands to fill the gap between left and right content */
.rule-inline .hf-right { margin-left: 0; }
.rule-inline .hf-fill {
  flex: 1;
  height: 1px;
  background: var(--color-rule);
  margin-right: 0.15in;
  opacity: 0.5;
}
.rule-inline .hf-left + .hf-fill { margin-left: 0.15in; }
/* Full-width rule above */
.rule-above::before {
  content: '';
  display: block;
  height: 1px;
  background: linear-gradient(to right, var(--color-rule), transparent);
  opacity: 0.5;
  margin-bottom: 0.06in;
}
/* Full-width rule below */
.rule-below::after {
  content: '';
  display: block;
  height: 1px;
  background: linear-gradient(to right, var(--color-rule), transparent);
  opacity: 0.5;
  margin-top: 0.06in;
}

/* Cover */
.cover {
  background-color: #1a120a;
  background-size: cover;
  background-position: center center;
  padding: 0.75in;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  align-items: center;
  text-align: center;
}
/* Gradient scrim — dark at top and bottom, clear in the middle */
.cover::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba(0,0,0,0.75) 0%%,
    rgba(0,0,0,0.0)  40%%,
    rgba(0,0,0,0.0)  60%%,
    rgba(0,0,0,0.65) 100%%
  );
  z-index: 0;
}

/* All direct children of .cover sit above the scrim */
.cover > * { position: relative; z-index: 1; }

.cover h1 {
  font-family: var(--font-heading);
  font-size: 2.6rem;
  font-weight: 700;
  color: #f5e6c8;
  letter-spacing: 0.04em;
  line-height: 1.15;
  margin-bottom: 0.18in;
}
.cover h2 {
  font-family: var(--font-heading);
  font-style: italic;
  font-weight: 400;
  font-size: 1.05rem;
  color: #e8d5b0;
  line-height: 1.4;
  margin-bottom: 0.35in;
  letter-spacing: 0.02em;
}
.cover .divider {
  width: 0.6in;
  height: 2px;
  background: #c8a97e;
  margin: 0 auto 0.35in;
  flex-shrink: 0;
}
.cover .spacer { flex: 1; }
.cover .blurb {
  font-family: var(--font-body);
  font-style: italic;
  font-size: 0.85rem;
  color: #e0cba8;
  line-height: 1.7;
  max-width: 3.8in;
  text-align: center;
  margin-bottom: 0.25in;
  flex-shrink: 0;
}
.cover .author {
  font-family: var(--font-body);
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.2em;
  text-transform: uppercase;
  color: #e8d5b0;
  align-self: flex-end;
  flex-shrink: 0;
}

/* ============================================================
   IMAGES
   Alt text convention: ![alignment-behavior-size](file.jpg)
   alignment: left | right
   behavior:  wrap (text flows around) | block (text follows below)
   size:      integer percent of content width e.g. 30, 50, 100
   Examples:
     ![right-wrap-40](chart.jpg)   — 40%% wide, right, text wraps
     ![left-block-50](photo.jpg)   — 50%% wide, left, text below
     ![](diagram.jpg)              — 100%% wide, centered block (default)
   ============================================================ */
.page:not(.cover) img {
  max-width: 100%%;
  height: auto;
  display: block;
  margin: 0.15in auto 0.15in;
}
.page:not(.cover) img.right-wrap {
  float: right;
  margin: 0 0 0.12in 0.18in;
  display: inline;
}
.page:not(.cover) img.left-wrap {
  float: left;
  margin: 0 0.18in 0.12in 0;
  display: inline;
}
.page:not(.cover) img.right-block {
  float: right;
  clear: both;
  margin: 0.12in 0 0.12in 0.18in;
  display: inline;
}
.page:not(.cover) img.left-block {
  float: left;
  clear: both;
  margin: 0.12in 0.18in 0.12in 0;
  display: inline;
}
/* Clear floats after block images */
.page:not(.cover) .img-block-clear { clear: both; }

/* ============================================================
   MATH (KaTeX server-side rendered)
   Inline math stays in the text flow.
   Block math is centered with vertical breathing room.
   ============================================================ */
.page:not(.cover) .math-inline .katex {
  font-size: 1em;
}
.page:not(.cover) .math-block {
  display: block;
  text-align: center;
  margin: 0.18in 0;
  overflow: hidden;
}
.page:not(.cover) .math-block .katex {
  font-size: 1.1em;
}

@media print {
  @page { size: 6in 9in; margin: 0; }
  body { background: none; padding: 0; gap: 0; }
  .page { box-shadow: none; break-after: page; page-break-after: always; }
  .page:last-child { break-after: avoid; page-break-after: avoid; }
}
"""

# ─────────────────────────────────────────────────────────────────────────────
# HTML template
# ─────────────────────────────────────────────────────────────────────────────

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>%(title)s</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" />
  <style>%(css)s</style>
</head>
<body>
%(cover)s
%(pages)s
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js"></script>
<script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js"></script>
<script>
  document.addEventListener("DOMContentLoaded", function() {
    renderMathInElement(document.body, {
      delimiters: [
        {left: "$$", right: "$$", display: true},
        {left: "$",  right: "$",  display: false}
      ],
      throwOnError: false
    });
  });
</script>
</body>
</html>"""

COVER_TEMPLATE = """  <div class="page cover">
    <h1>%(title)s</h1>
    <h2>%(subtitle)s</h2>
    <div class="divider"></div>
    <div class="spacer"></div>
    <p class="blurb">%(blurb)s</p>
    <span class="author">%(author)s</span>
  </div>"""

PAGE_TEMPLATE = """  <div class="page">
%(content)s
    <div class="page-number"><span>%(page_num)s</span></div>
  </div>"""


# ─────────────────────────────────────────────────────────────────────────────
# Image handling
# ─────────────────────────────────────────────────────────────────────────────

def load_image_as_data_uri(image_ref, base_dir=None):
    """
    Given a local file path or a URL, return a base64 data URI string
    suitable for use in CSS background-image or <img src>.
    Returns None if the image cannot be loaded.
    """
    if not image_ref:
        return None

    # ── URL ──────────────────────────────────────────────────────────────────
    if image_ref.startswith('http://') or image_ref.startswith('https://'):
        try:
            with urllib.request.urlopen(image_ref) as response:
                data = response.read()
                content_type = response.headers.get_content_type()
        except Exception as e:
            print(f"Warning: could not fetch cover image URL — {e}")
            return None

    # ── Local file ───────────────────────────────────────────────────────────
    else:
        image_path = Path(image_ref)
        # Resolve relative paths against the markdown file's directory
        if not image_path.is_absolute() and base_dir:
            image_path = Path(base_dir) / image_path
        if not image_path.exists():
            print(f"Warning: cover image not found — {image_path}")
            return None
        data = image_path.read_bytes()
        content_type, _ = mimetypes.guess_type(str(image_path))
        content_type = content_type or 'image/jpeg'

    encoded = base64.b64encode(data).decode('utf-8')
    return f"data:{content_type};base64,{encoded}"


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def process_images(html, base_dir=None):
    """
    Post-process HTML to handle the image alt text convention.
    Alt text format: alignment-behavior-size  e.g. "right-wrap-40"
    Injects the correct class and width style onto each <img> tag.
    Also base64-encodes local image src attributes.
    """
    def replace_img(match):
        tag = match.group(0)

        # ── Parse alt text for alignment/behavior/size ───────────────────────
        alt_match = re.search(r'alt="([^"]*)"', tag)
        alt = alt_match.group(1) if alt_match else ''
        parts = alt.strip().lower().split('-')

        css_class = ''
        width_pct = None

        if len(parts) >= 2 and parts[0] in ('left', 'right') and parts[1] in ('wrap', 'block'):
            css_class = f"{parts[0]}-{parts[1]}"
            if len(parts) >= 3 and parts[2].isdigit():
                width_pct = parts[2]

        # ── Base64-encode local src images ───────────────────────────────────
        src_match = re.search(r'src="([^"]*)"', tag)
        if src_match:
            src = src_match.group(1)
            if not src.startswith('http://') and not src.startswith('https://') \
               and not src.startswith('data:'):
                uri = load_image_as_data_uri(src, base_dir=base_dir)
                if uri:
                    tag = tag.replace(f'src="{src}"', f'src="{uri}"')

        # ── Inject class and width ────────────────────────────────────────────
        style = f'width:{width_pct}%%' if width_pct else 'width:100%%'
        if css_class:
            tag = re.sub(r'<img ', f'<img class="{css_class}" style="{style}" ', tag)
        else:
            # Default: full width centered block
            tag = re.sub(r'<img ', f'<img style="{style}" ', tag)

        # ── Add clear div after block images so text starts below ────────────
        if css_class and 'block' in css_class:
            tag += '<div class="img-block-clear"></div>'

        return tag

    return re.sub(r'<img [^>]+>', replace_img, html)


def process_math(html):
    """
    Math is rendered client-side by KaTeX auto-render (loaded from CDN).
    This function just ensures $...$ and $$...$$ delimiters are preserved
    intact — the markdown library leaves them alone so nothing to do here.
    We do wrap them in spans so CSS can style the containers consistently.
    """
    # Block math: $$...$$ — wrap in a div for centering
    html = re.sub(
        r'\$\$(.+?)\$\$',
        lambda m: f'<div class="math-block">$${m.group(1)}$$</div>',
        html,
        flags=re.DOTALL
    )
    # Inline math: $...$ — wrap in a span
    html = re.sub(
        r'\$(.+?)\$',
        lambda m: f'<span class="math-inline">${m.group(1)}$</span>',
        html
    )
    return html


def clean_escapes(text):
    """Strip backslash escapes that Google Drive's markdown export adds to
    characters with no special meaning in Markdown (e.g. = : > <).
    Deliberately narrow: backslashes before letters must survive so LaTeX
    commands like \\frac and \\sqrt reach KaTeX intact."""
    over_escaped = r'=:><'
    return re.sub(r'\\([' + re.escape(over_escaped) + r'])', r'\1', text)


def parse_front_matter(text):
    """Split YAML front matter from body. Returns (metadata_dict, body_str)."""
    if not text.startswith('---'):
        return {}, text

    parts = text.split('---', 2)
    if len(parts) < 3:
        return {}, text

    metadata = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return metadata, body


def split_pages(body):
    """Split body markdown into pages on h1 headings (# ) or <!-- pagebreak -->."""
    # Replace pagebreak comments with a sentinel heading so we can split uniformly
    body = re.sub(r'^<!--\s*pagebreak\s*-->', '# ', body, flags=re.MULTILINE)
    # Look-ahead split: keep the delimiter (the # heading) with its page
    raw = re.split(r'(?=^# )', body, flags=re.MULTILINE)
    return [p.strip() for p in raw if p.strip()]


def md_to_html(md_text, base_dir=None):
    """Convert a markdown string to an HTML fragment."""
    import re
    html = markdown.markdown(
        md_text,
        extensions=['extra', 'sane_lists', 'admonition', 'codehilite'],
        extension_configs={
            'codehilite': {'guess_lang': False},
        }
    )
    # Strip trailing whitespace inside <pre><code> blocks —
    # the markdown library adds a trailing newline that renders as extra padding
    html = re.sub(r'\s+</code></pre>', '</code></pre>', html)
    # Process images: inject classes, width, and base64-encode local files
    html = process_images(html, base_dir=base_dir)
    # Process math: render $...$ and $$...$$ via KaTeX
    html = process_math(html)
    return html


# ─────────────────────────────────────────────────────────────────────────────
# Builders
# ─────────────────────────────────────────────────────────────────────────────

def build_cover(meta, overrides, image_uri=None):
    """Build the cover page HTML from metadata + any CLI overrides."""
    data = {
        'title':    overrides.get('title')    or meta.get('title',    'Untitled'),
        'subtitle': overrides.get('subtitle') or meta.get('subtitle', ''),
        'blurb':    overrides.get('blurb')    or meta.get('blurb',    ''),
        'author':   overrides.get('author')   or meta.get('author',   ''),
    }

    # Inject cover image directly as background-image inline style
    style_attr = ''
    if image_uri:
        style_attr = f' style="background-image: url(\'{image_uri}\')"'

    return f"""  <div class="page cover"{style_attr}>
    <h1>{data['title']}</h1>
    <h2>{data['subtitle']}</h2>
    <div class="divider"></div>
    <div class="spacer"></div>
    <p class="blurb">{data['blurb']}</p>
    <span class="author">{data['author']}</span>
  </div>"""


DEFAULT_FOOTER_CONFIG = {'right': '{page}', 'rule': 'inline'}


def get_chapter_name(page_md):
    """Return the text of the leading # heading, or '' if the page has none."""
    first_line = page_md.strip().split('\n')[0]
    match = re.match(r'^#\s+(.+)', first_line)
    return match.group(1).strip() if match else ''


def render_hf_variables(template, page_num, title, chapter):
    """Substitute {page}, {title}, {chapter} in a header/footer template string."""
    if not template:
        return ''
    return (template
            .replace('{page}',    str(page_num))
            .replace('{title}',   title   or '')
            .replace('{chapter}', chapter or ''))


def build_hf_html(config, page_num, title, chapter, is_header=False):
    """Build the HTML div for a page header or footer."""
    css_class    = 'page-header' if is_header else 'page-footer'
    default_rule = 'false' if is_header else 'inline'

    left   = render_hf_variables(config.get('left',   ''), page_num, title, chapter)
    right  = render_hf_variables(config.get('right',  ''), page_num, title, chapter)
    center = render_hf_variables(config.get('center', ''), page_num, title, chapter)
    rule   = config.get('rule', default_rule)

    # YAML parses `rule: false` as boolean False
    if rule is False:
        rule = 'false'

    # rule: inline doesn't make sense with center-only — fall back gracefully
    if center and rule == 'inline':
        rule = 'below' if is_header else 'above'

    rule_class = f' rule-{rule}' if rule != 'false' else ''

    position_key = 'top' if is_header else 'bottom'
    position_val = config.get(position_key, '')
    style_attr   = f' style="{position_key}: {position_val}"' if position_val else ''

    if center:
        content = f'<span class="hf-center">{center}</span>'
    else:
        parts = []
        if left:
            parts.append(f'<span class="hf-left">{left}</span>')
        if rule == 'inline':
            parts.append('<span class="hf-fill"></span>')
        if right:
            parts.append(f'<span class="hf-right">{right}</span>')
        content = ''.join(parts)

    return (f'    <div class="{css_class}{rule_class}"{style_attr}>'
            f'<div class="hf-content">{content}</div></div>')


def build_pages(pages, base_dir=None, drop_cap=True,
                header_config=None, footer_config=None, title=''):
    """Convert each markdown page chunk to a styled HTML page div."""
    html_pages = []
    current_chapter = ''

    for i, page_md in enumerate(pages, start=1):
        # Track chapter name; carry forward when page has no heading
        chapter_name = get_chapter_name(page_md)
        if chapter_name:
            current_chapter = chapter_name

        # Check for per-page directives and strip them
        has_no_drop_cap  = bool(re.search(r'<!--\s*no-drop-cap\s*-->',  page_md))
        has_add_drop_cap = bool(re.search(r'<!--\s*add-drop-cap\s*-->', page_md))
        page_md = re.sub(r'<!--\s*no-drop-cap\s*-->\n?',  '', page_md)
        page_md = re.sub(r'<!--\s*add-drop-cap\s*-->\n?', '', page_md)

        # Global off → no drop cap unless page opts in; global on → drop cap unless page opts out
        if drop_cap:
            no_drop_cap = has_no_drop_cap
        else:
            no_drop_cap = not has_add_drop_cap

        content = md_to_html(page_md, base_dir=base_dir)
        # Indent content for readability, but skip lines inside <pre> blocks
        # to avoid adding spurious whitespace that corrupts code indentation
        indented_lines = []
        in_pre = False
        for line in content.splitlines():
            if '<pre>' in line:
                in_pre = True
            if in_pre:
                indented_lines.append(line)
            else:
                indented_lines.append('    ' + line)
            if '</pre>' in line:
                in_pre = False
        indented = '\n'.join(indented_lines)
        page_class = 'page no-drop-cap' if no_drop_cap else 'page'
        if header_config:
            page_class += ' has-header'

        header_html = ''
        if header_config:
            header_html = '\n' + build_hf_html(
                header_config, i, title, current_chapter, is_header=True)

        active_footer = footer_config if footer_config is not None else DEFAULT_FOOTER_CONFIG
        footer_html = '\n' + build_hf_html(
            active_footer, i, title, current_chapter, is_header=False)

        html_pages.append(
            f'  <div class="{page_class}">\n{indented}{header_html}{footer_html}\n  </div>')

    return '\n'.join(html_pages)


def build_html(meta, cover_html, pages_html, overrides):
    """Assemble the final HTML document."""
    accent_color = overrides.get('accent_color') or meta.get('accent_color', '#8b4513')
    font_heading = overrides.get('font_heading') or meta.get('font_heading', "'Playfair Display', Georgia, serif")
    font_body    = overrides.get('font_body')    or meta.get('font_body',    "'Lora', Georgia, serif")
    font_code    = overrides.get('font_code')    or meta.get('font_code',    "'Courier New', Courier, monospace")
    css = BOOK_CSS % {
        'accent_color':  accent_color,
        'font_heading':  font_heading,
        'font_body':     font_body,
        'font_code':     font_code,
        'margin_outer':  overrides.get('margin_outer')  or meta.get('margin_outer',  '0.75in'),
        'margin_inner':  overrides.get('margin_inner')  or meta.get('margin_inner',  '0.875in'),
        'margin_top':    overrides.get('margin_top')    or meta.get('margin_top',    '0.75in'),
        'margin_bottom': overrides.get('margin_bottom') or meta.get('margin_bottom', '0.75in'),
    }
    title = overrides.get('title') or meta.get('title', 'Untitled')

    google_fonts = meta.get('google_fonts') or []
    user_import  = build_google_fonts_import(google_fonts)
    style_overrides = build_style_overrides(meta.get('styles', {}))
    full_css = (user_import + '\n' if user_import else '') + css + '\n/* Syntax highlighting */\n' + PYGMENTS_CSS
    if style_overrides:
        full_css += '\n' + style_overrides

    return HTML_TEMPLATE % {
        'title':  title,
        'css':    full_css,
        'cover':  cover_html,
        'pages':  pages_html,
    }


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Convert a Markdown book file to a PDF-ready HTML file.'
    )
    parser.add_argument('input',
        help='Path to the Markdown source file')
    parser.add_argument('-o', '--output',
        help='Output HTML filename (default: same name as input, .html extension)')
    parser.add_argument('--title',
        help='Override the title from front matter')
    parser.add_argument('--subtitle',
        help='Override the subtitle from front matter')
    parser.add_argument('--author',
        help='Override the author from front matter')
    parser.add_argument('--blurb',
        help='Override the blurb from front matter')
    parser.add_argument('--accent-color',
        help='Override the accent color (e.g. "#8b4513")')
    parser.add_argument('--cover-image',
        help='Override the cover image (local path or URL)')
    parser.add_argument('--margin-top',
        help='Override the top margin (e.g. "0.5in")')
    parser.add_argument('--margin-bottom',
        help='Override the bottom margin (e.g. "0.5in")')
    parser.add_argument('--margin-inner',
        help='Override the inner (spine-side) margin (e.g. "1in")')
    parser.add_argument('--margin-outer',
        help='Override the outer margin (e.g. "0.625in")')
    args = parser.parse_args()

    # ── Read input ──────────────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found — {input_path}")
        sys.exit(1)

    source = input_path.read_text(encoding='utf-8')
    source = clean_escapes(source)

    # ── Parse ────────────────────────────────────────────────────────────────
    meta, body = parse_front_matter(source)
    pages = split_pages(body)

    if not pages:
        print("Warning: no pages found. Make sure body content uses # headings.")

    # ── CLI overrides ────────────────────────────────────────────────────────
    overrides = {k: v for k, v in {
        'title':         args.title,
        'subtitle':      args.subtitle,
        'author':        args.author,
        'blurb':         args.blurb,
        'accent_color':  args.accent_color,
        'cover_image':   args.cover_image,
        'margin_top':    args.margin_top,
        'margin_bottom': args.margin_bottom,
        'margin_inner':  args.margin_inner,
        'margin_outer':  args.margin_outer,
    }.items() if v}

    # ── Load cover image (local file or URL) ────────────────────────────────
    image_ref = overrides.get('cover_image') or meta.get('cover_image')
    image_uri = load_image_as_data_uri(image_ref, base_dir=input_path.parent)

    # ── Build ────────────────────────────────────────────────────────────────
    cover_html    = build_cover(meta, overrides, image_uri=image_uri)
    drop_cap      = meta.get('drop_cap', True)
    title         = overrides.get('title') or meta.get('title', '')
    header_config = meta.get('header')
    footer_config = meta.get('footer')
    pages_html    = build_pages(pages, base_dir=input_path.parent, drop_cap=drop_cap,
                                header_config=header_config, footer_config=footer_config,
                                title=title)
    html          = build_html(meta, cover_html, pages_html, overrides)

    # ── Write output ─────────────────────────────────────────────────────────
    output_path = Path(args.output) if args.output else input_path.with_suffix('.html')
    output_path.write_text(html, encoding='utf-8')

    print(f"✅  {len(pages)} page(s) written to: {output_path}")
    if meta:
        print(f"    Title:  {meta.get('title', '—')}")
        print(f"    Author: {meta.get('author', '—')}")


if __name__ == '__main__':
    main()