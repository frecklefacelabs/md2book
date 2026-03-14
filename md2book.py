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
  --font-heading:  'Playfair Display', Georgia, serif;
  --font-body:     'Lora', Georgia, serif;
  --margin-outer:  0.75in;
  --margin-inner:  0.875in;
  --margin-top:    0.75in;
  --margin-bottom: 0.75in;
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

.page:not(.cover)::before {
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
  font-size: 0.65rem;
  font-weight: 400;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--color-accent);
  margin-bottom: 0.2in;
}
.page:not(.cover) h2 {
  font-family: var(--font-heading);
  font-size: 1.75rem;
  font-weight: 700;
  color: var(--color-heading);
  line-height: 1.2;
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
  text-align: justify;
  hyphens: auto;
}
.page:not(.cover) p:first-of-type::first-letter {
  font-family: var(--font-heading);
  font-size: 3.2rem;
  font-weight: 700;
  color: var(--color-accent);
  float: left;
  line-height: 0.8;
  margin-right: 0.06in;
  margin-top: 0.04in;
}
.page:not(.cover) blockquote {
  border-left: 3px solid var(--color-rule);
  margin: 0.2in 0 0.2in 0.2in;
  padding-left: 0.15in;
  font-style: italic;
  color: var(--color-accent);
  font-size: 0.875rem;
  line-height: 1.6;
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

/* Inline code */
.page:not(.cover) code {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.8rem;
  background: #f0ebe3;
  color: #8b4513;
  padding: 0.01in 0.05in;
  border-radius: 2px;
  border: 1px solid #ddd5c8;
}

/* Code blocks */
.page:not(.cover) pre {
  background: #1e1e1e;
  border-left: 3px solid var(--color-accent);
  border-radius: 3px;
  padding: 0.15in 0.18in;
  margin-bottom: 0.18in;
  overflow: hidden;
}
.page:not(.cover) pre code {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.78rem;
  line-height: 1.6;
  color: #d4d4d4;
  background: none;
  border: none;
  padding: 0;
  border-radius: 0;
  display: block;
  white-space: pre;
}

.page-number {
  position: absolute;
  bottom: 0.45in;
  left: var(--margin-inner);
  width: calc(var(--page-width) - var(--margin-outer) - var(--margin-inner));
  font-family: var(--font-body);
  font-size: 0.65rem;
  color: var(--color-rule);
  letter-spacing: 0.1em;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.page-number::before {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--color-rule);
  margin-right: 0.15in;
  opacity: 0.5;
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
  <style>%(css)s</style>
</head>
<body>
%(cover)s
%(pages)s
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
    """Split body markdown into pages wherever an h1 heading (# ) appears."""
    # Look-ahead split: keep the delimiter (the # heading) with its page
    raw = re.split(r'(?=^# )', body, flags=re.MULTILINE)
    return [p.strip() for p in raw if p.strip()]


def md_to_html(md_text):
    """Convert a markdown string to an HTML fragment."""
    return markdown.markdown(
        md_text,
        extensions=['extra', 'sane_lists']
    )


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


def build_pages(pages):
    """Convert each markdown page chunk to a styled HTML page div."""
    html_pages = []
    for i, page_md in enumerate(pages, start=1):
        content = md_to_html(page_md)
        # Indent content for readability
        indented = '\n'.join('    ' + line for line in content.splitlines())
        html_pages.append(PAGE_TEMPLATE % {
            'content':  indented,
            'page_num': i,
        })
    return '\n'.join(html_pages)


def build_html(meta, cover_html, pages_html, overrides):
    """Assemble the final HTML document."""
    accent_color = overrides.get('accent_color') or meta.get('accent_color', '#8b4513')
    css = BOOK_CSS % {'accent_color': accent_color}
    title = overrides.get('title') or meta.get('title', 'Untitled')

    return HTML_TEMPLATE % {
        'title':  title,
        'css':    css,
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
    args = parser.parse_args()

    # ── Read input ──────────────────────────────────────────────────────────
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found — {input_path}")
        sys.exit(1)

    source = input_path.read_text(encoding='utf-8')

    # ── Parse ────────────────────────────────────────────────────────────────
    meta, body = parse_front_matter(source)
    pages = split_pages(body)

    if not pages:
        print("Warning: no pages found. Make sure body content uses # headings.")

    # ── CLI overrides ────────────────────────────────────────────────────────
    overrides = {k: v for k, v in {
        'title':        args.title,
        'subtitle':     args.subtitle,
        'author':       args.author,
        'blurb':        args.blurb,
        'accent_color': args.accent_color,
        'cover_image':  args.cover_image,
    }.items() if v}

    # ── Load cover image (local file or URL) ────────────────────────────────
    image_ref = overrides.get('cover_image') or meta.get('cover_image')
    image_uri = load_image_as_data_uri(image_ref, base_dir=input_path.parent)

    # ── Build ────────────────────────────────────────────────────────────────
    cover_html = build_cover(meta, overrides, image_uri=image_uri)
    pages_html = build_pages(pages)
    html       = build_html(meta, cover_html, pages_html, overrides)

    # ── Write output ─────────────────────────────────────────────────────────
    output_path = Path(args.output) if args.output else input_path.with_suffix('.html')
    output_path.write_text(html, encoding='utf-8')

    print(f"✅  {len(pages)} page(s) written to: {output_path}")
    if meta:
        print(f"    Title:  {meta.get('title', '—')}")
        print(f"    Author: {meta.get('author', '—')}")


if __name__ == '__main__':
    main()