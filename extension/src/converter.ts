/**
 * converter.ts — TypeScript port of md2book.py
 *
 * Converts a Markdown string with YAML front matter into a single-file
 * HTML book, ready to print-to-PDF.
 */

import * as fs from "fs";
import * as path from "path";
import * as yaml from "js-yaml";
import MarkdownIt from "markdown-it";
import admonPlugin from "markdown-it-admon";

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────

export interface BookMeta {
  title?: string;
  subtitle?: string;
  author?: string;
  blurb?: string;
  accent_color?: string;
  cover_image?: string;
  [key: string]: unknown;
}

export interface ConvertOptions {
  /** Directory to resolve relative image paths against */
  baseDir?: string;
  /** Override any front-matter fields */
  overrides?: Partial<BookMeta>;
}

// ─────────────────────────────────────────────────────────────────────────────
// CSS (embedded in output HTML)
// ─────────────────────────────────────────────────────────────────────────────

function bookCss(accentColor: string): string {
  return `
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;1,400&family=Lora:ital,wght@0,400;0,600;1,400&display=swap');

:root {
  --page-width:    6in;
  --page-height:   9in;
  --color-bg:      #fffdf8;
  --color-text:    #2a2118;
  --color-heading: #1a1208;
  --color-accent:  ${accentColor};
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
  text-align: justify;
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
  width: 100%;
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
  background: #ede8df;
  border-left: 3px solid var(--color-accent);
  border-radius: 3px;
  padding: 0.15in 0.18in;
  margin-top: 0.18in;
  margin-bottom: 0.18in;
  overflow: hidden;
}
.page:not(.cover) pre code {
  font-family: 'Courier New', Courier, monospace;
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
    rgba(0,0,0,0.75) 0%,
    rgba(0,0,0,0.0)  40%,
    rgba(0,0,0,0.0)  60%,
    rgba(0,0,0,0.65) 100%
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
   ============================================================ */
.page:not(.cover) img {
  max-width: 100%;
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
   MATH (KaTeX — rendered client-side)
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
}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Markdown renderer (singleton)
// ─────────────────────────────────────────────────────────────────────────────

const md = new MarkdownIt({ html: true, typographer: false })
  .use(admonPlugin);

// ─────────────────────────────────────────────────────────────────────────────
// Image handling
// ─────────────────────────────────────────────────────────────────────────────

function loadImageAsDataUri(
  imageRef: string,
  baseDir?: string
): string | null {
  if (!imageRef) return null;

  // URL — fetch synchronously is not practical in Node; skip for now.
  // The webview can load remote URLs directly.
  if (imageRef.startsWith("http://") || imageRef.startsWith("https://")) {
    return null; // leave as URL — the webview will fetch it
  }

  // Local file
  let imagePath = imageRef;
  if (!path.isAbsolute(imagePath) && baseDir) {
    imagePath = path.join(baseDir, imagePath);
  }
  if (!fs.existsSync(imagePath)) {
    return null;
  }

  const data = fs.readFileSync(imagePath);
  const ext = path.extname(imagePath).toLowerCase();
  const mimeTypes: Record<string, string> = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
  };
  const contentType = mimeTypes[ext] || "image/jpeg";
  return `data:${contentType};base64,${data.toString("base64")}`;
}

// ─────────────────────────────────────────────────────────────────────────────
// Post-processing
// ─────────────────────────────────────────────────────────────────────────────

function processImages(html: string, baseDir?: string): string {
  return html.replace(/<img [^>]+>/g, (tag) => {
    // Parse alt text for alignment/behavior/size
    const altMatch = tag.match(/alt="([^"]*)"/);
    const alt = altMatch ? altMatch[1] : "";
    const parts = alt.trim().toLowerCase().split("-");

    let cssClass = "";
    let widthPct: string | null = null;

    if (
      parts.length >= 2 &&
      ["left", "right"].includes(parts[0]) &&
      ["wrap", "block"].includes(parts[1])
    ) {
      cssClass = `${parts[0]}-${parts[1]}`;
      if (parts.length >= 3 && /^\d+$/.test(parts[2])) {
        widthPct = parts[2];
      }
    }

    // Base64-encode local src images
    const srcMatch = tag.match(/src="([^"]*)"/);
    if (srcMatch) {
      const src = srcMatch[1];
      if (
        !src.startsWith("http://") &&
        !src.startsWith("https://") &&
        !src.startsWith("data:")
      ) {
        const uri = loadImageAsDataUri(src, baseDir);
        if (uri) {
          tag = tag.replace(`src="${src}"`, `src="${uri}"`);
        }
      }
    }

    // Inject class and width
    const style = widthPct ? `width:${widthPct}%` : "width:100%";
    if (cssClass) {
      tag = tag.replace("<img ", `<img class="${cssClass}" style="${style}" `);
    } else {
      tag = tag.replace("<img ", `<img style="${style}" `);
    }

    // Add clear div after block images
    if (cssClass && cssClass.includes("block")) {
      tag += '<div class="img-block-clear"></div>';
    }

    return tag;
  });
}

function processMath(html: string): string {
  // Block math: $$...$$ — wrap in a div for centering
  html = html.replace(
    /\$\$(.+?)\$\$/gs,
    (_match, content) => `<div class="math-block">$$${content}$$</div>`
  );
  // Inline math: $...$ — wrap in a span
  html = html.replace(
    /\$(.+?)\$/g,
    (_match, content) => `<span class="math-inline">$${content}$</span>`
  );
  return html;
}

function cleanEscapes(text: string): string {
  const markdownSpecials = "\\*_{}[]()#+-.!|`";
  // Remove backslash before characters that aren't markdown-special
  return text.replace(/\\(.)/g, (match, ch) => {
    return markdownSpecials.includes(ch) ? match : ch;
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// Parsing
// ─────────────────────────────────────────────────────────────────────────────

function parseFrontMatter(text: string): { meta: BookMeta; body: string } {
  if (!text.startsWith("---")) {
    return { meta: {}, body: text };
  }

  const parts = text.split("---");
  if (parts.length < 3) {
    return { meta: {}, body: text };
  }

  // parts[0] is empty (before first ---), parts[1] is YAML, parts[2..] is body
  const meta = (yaml.load(parts[1]) as BookMeta) || {};
  const body = parts.slice(2).join("---").trim();
  return { meta, body };
}

function splitPages(body: string): string[] {
  // Split on lines starting with "# " (h1 headings)
  const raw = body.split(/(?=^# )/m);
  return raw.map((p) => p.trim()).filter((p) => p.length > 0);
}

function mdToHtml(mdText: string, baseDir?: string): string {
  let html = md.render(mdText);

  // Strip trailing whitespace inside <pre><code> blocks
  html = html.replace(/\s+<\/code><\/pre>/g, "</code></pre>");

  // Process images: inject classes, width, and base64-encode local files
  html = processImages(html, baseDir);

  // Process math: wrap $...$ and $$...$$ for KaTeX
  html = processMath(html);

  return html;
}

// ─────────────────────────────────────────────────────────────────────────────
// Builders
// ─────────────────────────────────────────────────────────────────────────────

function buildCover(
  meta: BookMeta,
  overrides: Partial<BookMeta>,
  imageUri?: string | null
): string {
  const title = overrides.title || meta.title || "Untitled";
  const subtitle = overrides.subtitle || meta.subtitle || "";
  const blurb = overrides.blurb || meta.blurb || "";
  const author = overrides.author || meta.author || "";

  const styleAttr = imageUri
    ? ` style="background-image: url('${imageUri}')"`
    : "";

  return `  <div class="page cover"${styleAttr}>
    <h1>${title}</h1>
    <h2>${subtitle}</h2>
    <div class="divider"></div>
    <div class="spacer"></div>
    <p class="blurb">${blurb}</p>
    <span class="author">${author}</span>
  </div>`;
}

function buildPages(pages: string[], baseDir?: string): string {
  return pages
    .map((pageMd, i) => {
      const content = mdToHtml(pageMd, baseDir);

      // Indent content for readability, but skip lines inside <pre> blocks
      const indentedLines: string[] = [];
      let inPre = false;
      for (const line of content.split("\n")) {
        if (line.includes("<pre>")) inPre = true;
        indentedLines.push(inPre ? line : "    " + line);
        if (line.includes("</pre>")) inPre = false;
      }

      return `  <div class="page">
${indentedLines.join("\n")}
    <div class="page-number"><span>${i + 1}</span></div>
  </div>`;
    })
    .join("\n");
}

// ─────────────────────────────────────────────────────────────────────────────
// Public API
// ─────────────────────────────────────────────────────────────────────────────

/**
 * Convert a Markdown string (with optional YAML front matter) into a
 * complete, self-contained HTML book.
 */
export function convert(source: string, options: ConvertOptions = {}): string {
  const { baseDir, overrides = {} } = options;

  const cleaned = cleanEscapes(source);
  const { meta, body } = parseFrontMatter(cleaned);
  const pages = splitPages(body);

  // Resolve cover image
  const imageRef =
    (overrides.cover_image as string) || meta.cover_image || "";
  let imageUri: string | null = null;
  if (imageRef) {
    imageUri = loadImageAsDataUri(imageRef, baseDir);
  }

  const accentColor =
    (overrides.accent_color as string) || meta.accent_color || "#8b4513";

  const coverHtml = buildCover(meta, overrides, imageUri);
  const pagesHtml = buildPages(pages, baseDir);
  const title = overrides.title || meta.title || "Untitled";
  const css = bookCss(accentColor);

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>${escapeHtml(title)}</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" />
  <style>${css}</style>
</head>
<body>
${coverHtml}
${pagesHtml}
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
</html>`;
}

function escapeHtml(text: string): string {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
