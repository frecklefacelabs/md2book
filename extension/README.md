# md2book Preview — VS Code Extension

Live preview for md2book. Edit your Markdown book and see it rendered as a beautiful 6"x9" book right in VS Code.

## Features

- **Toolbar buttons** appear when editing any `.md` file:
  - **Preview** — opens a live book preview panel (or use Command Palette: "md2book: Open Book Preview")
  - **Export to Browser** — opens the rendered book in your default browser for print-to-PDF (Ctrl+P)
- **Debounced auto-refresh** — preview updates ~1 second after you stop typing
- **Self-contained** — no Python or external dependencies needed at runtime

## Markdown Directives

### Page breaks

Use an `# ` heading to start a new page (the heading becomes the page title), or use a comment for a page break without a heading:

```markdown
<!-- pagebreak -->
```

### Disable drop cap

By default, the first paragraph on each page gets a decorative drop cap. To disable it for a specific page, add this comment before the first paragraph:

```markdown
# Some Chapter
<!-- no-drop-cap -->

This paragraph will start normally.
```

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

```bash
cd extension
npm install
npm run compile
```

## Packaging & Installing

Install the packaging tool (one-time):

```bash
npm install -g @vscode/vsce
```

Build the `.vsix` file:

```bash
vsce package
```

Install it in VS Code:

```bash
code --install-extension md2book-preview-0.0.1.vsix
```

Or from inside VS Code: Command Palette → "Extensions: Install from VSIX..." and pick the file.

Once installed, the `.vsix` file can be deleted — VS Code copies everything it needs into `~/.vscode/extensions/`.

## Development

To test without packaging, press **F5** in VS Code with the `extension/` folder open. This launches an Extension Development Host where you can try the extension live.

For continuous compilation while developing:

```bash
npm run watch
```
