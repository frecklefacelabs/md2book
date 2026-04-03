# md2book Preview — VS Code Extension

Live preview for md2book. Edit your Markdown book and see it rendered as a beautiful 6"x9" book right in VS Code.

## Features

- **Toolbar buttons** appear when editing any `.md` file:
  - **Preview** — opens a live book preview panel (or use Command Palette: "md2book: Open Book Preview")
  - **Export to Browser** — opens the rendered book in your default browser for print-to-PDF (Ctrl+P)
- **Debounced auto-refresh** — preview updates ~1 second after you stop typing
- **Self-contained** — no Python or external dependencies needed at runtime

## Front Matter

Add a YAML front matter block at the top of your file to configure the cover page and book styling:

```yaml
---
title: My Book
subtitle: A story of adventure
author: Freckleface
blurb: A short teaser paragraph shown at the bottom of the cover.
cover_image: cover.jpg        # local path or URL
accent_color: "#8b4513"       # CSS color for headings, drop caps, rules
drop_cap: true                # set to false to disable drop caps globally
margin_top: 0.75in
margin_bottom: 0.75in
margin_inner: 0.875in         # spine-side margin
margin_outer: 0.75in
---
```

All fields are optional. The cover page is always generated; fields not provided are simply left blank.

### Style overrides

Use the `styles` key to override the CSS for specific elements. Values are plain CSS property strings:

```yaml
styles:
  h2: "font-size: 1.6rem; color: #2a5090;"
  body_text: "line-height: 1.9; font-size: 0.9rem;"
  callout_tip: "background: #e8f4f8; border-left-color: #2a7ab5;"
  cover_title: "font-size: 3rem; letter-spacing: 0.08em;"
```

Available names:

| Name | Element |
|---|---|
| `h1` | Chapter/section label |
| `h2` | Main heading |
| `h3` | Subheading |
| `h4` | Minor heading |
| `h5` | Minor subheading |
| `body_text` | Paragraph text |
| `blockquote` | Blockquote |
| `code_inline` | Inline code |
| `code_block` | Code block |
| `callout_tip` | Tip admonition box |
| `callout_warning` | Warning admonition box |
| `callout_note` | Note admonition box |
| `callout_important` | Important admonition box |
| `callout_example` | Example admonition box |
| `cover_title` | Cover page title |
| `cover_subtitle` | Cover page subtitle |
| `cover_author` | Cover page author byline |
| `cover_blurb` | Cover page blurb |

## Markdown Directives

### Page breaks

Use an `# ` heading to start a new page (the heading becomes the page title), or use a comment for a page break without a heading:

```markdown
<!-- pagebreak -->
```

### Drop caps

By default, the first paragraph on each page gets a decorative drop cap. You can control this globally via front matter, and override it per page with comments.

**Disable globally:**

```yaml
---
drop_cap: false
---
```

**Disable on a specific page** (when global is on):

```markdown
# Some Chapter
<!-- no-drop-cap -->

This paragraph will start normally.
```

**Enable on a specific page** (when global is off):

```markdown
# Some Chapter
<!-- add-drop-cap -->

This paragraph will get a drop cap.
```

### Admonition boxes

Call out tips, warnings, and notes with styled admonition boxes:

```markdown
!!! tip
    A helpful suggestion with a 💡 icon.

!!! warning
    Something to watch out for — shown in amber with a ⚠️ icon.

!!! note
    Extra context — shown in blue with a 📝 icon.

!!! important
    Critical information — shown in red with a ❗ icon.

!!! example
    An illustrative example — shown in purple with a 🔍 icon.
```

### Math

Inline and block math are rendered via KaTeX. Use standard LaTeX delimiters:

```markdown
Inline: $E = mc^2$

Block:
$$\int_0^\infty e^{-x^2} dx = \frac{\sqrt{\pi}}{2}$$
```

### Tables

Standard Markdown tables are supported and styled automatically:

```markdown
| Column A | Column B | Column C |
|----------|----------|----------|
| one      | two      | three    |
| four     | five     | six      |
```

### Code blocks

Fenced code blocks are styled with a monospace font and an accent-colored left border:

````markdown
```python
def hello():
    print("Hello, world!")
```
````

### Image placement

Control image alignment, float behavior, and size via alt text:

```markdown
![right-wrap-40](photo.jpg)   — 40% wide, right-aligned, text wraps
![left-block-50](chart.jpg)   — 50% wide, left-aligned, text below
![](diagram.jpg)              — 100% wide, centered (default)
```

Format: `![alignment-behavior-size](file)` where alignment is `left`/`right`, behavior is `wrap`/`block`, and size is a width percentage.

## Settings

| Setting | Default | Description |
|---|---|---|
| `md2book.debounceDelay` | `1000` | Delay (ms) after last keystroke before refreshing |
| `md2book.autoRefresh` | `true` | Auto-refresh on document change |

## Building

The first time:

```bash
cd extension
npm install
```

## Packaging & Installing

Enter a nix development shell:

```
nix develop
```

Build the `.vsix` file:

```bash
npm run compile
vsce package
```

Install it in VS Code:

```bash
code --install-extension md2book-preview-0.0.1.vsix
```

Or from inside VS Code: Command Palette → "Extensions: Install from VSIX..." and pick the file.

!!! Tip
    If building from within WSL, you'll need to copy the built extension over to the Windows drive. We recommend always copying it to the same place, as shown below.

The first time:
```
mkdir /mnt/c/Users/jeffc/vsextensions
```

From then on:

```
cp md2book*.vsix /mnt/c/Users/jeffc/vsextensions/
```

And then to switch back to Windows to install:

```
code --install-extension \Users\jeffc\vsextensions\md2book-preview-0.0.1.vsix
```

Once installed, the `.vsix` file can be deleted — VS Code copies everything it needs into `~/.vscode/extensions/`.

## Printing

If Chrome's Print to PDF doesn't list 6x9, try using Chrome as a command line tool:

```
"C:\Program Files\Google\Chrome\Application\chrome.exe" --headless --print-to-pdf="c:\users\jeffc\output.pdf" --print-to-pdf-no-header "file:///C:/Users/jeffc/AppData/Local/Temp/md2book-f74b4440.html"
```

(Grab the file:/// URL from the Chrome address bar. And for the output, replace your own username. Note that you MUST specifify the full path for the output.)

## Development

To test without packaging, press **F5** in VS Code with the `extension/` folder open. This launches an Extension Development Host where you can try the extension live.

For continuous compilation while developing:

```bash
npm run watch
```
