# md2book Preview — VS Code Extension

Live preview for md2book. Edit your Markdown book and see it rendered as a beautiful 6"x9" book right in VS Code.

## Features

- **Toolbar button** appears when editing any `.md` file, or use the Command Palette: "md2book: Open Book Preview"
- **Debounced auto-refresh** — preview updates ~1 second after you stop typing
- **Self-contained** — no Python or external dependencies needed at runtime

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
