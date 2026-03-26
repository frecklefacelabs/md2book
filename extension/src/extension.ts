import * as vscode from "vscode";
import * as path from "path";
import { writeFile } from "fs/promises";
import { tmpdir } from "os";
import { randomBytes } from "crypto";
import { convert } from "./converter";

let panel: vscode.WebviewPanel | undefined;
let debounceTimer: ReturnType<typeof setTimeout> | undefined;

// ── Activation ──────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext) {
  const openCmd = vscode.commands.registerCommand(
    "md2book.openPreview",
    () => openPreview()
  );
  context.subscriptions.push(openCmd);

  const exportCmd = vscode.commands.registerCommand(
    "md2book.exportToBrowser",
    () => exportToBrowser()
  );
  context.subscriptions.push(exportCmd);

  // Debounced auto-refresh on text change
  const onChange = vscode.workspace.onDidChangeTextDocument((e) => {
    if (!panel || e.document.languageId !== "markdown") return;

    const config = vscode.workspace.getConfiguration("md2book");
    if (!config.get<boolean>("autoRefresh", true)) return;

    const delay = config.get<number>("debounceDelay", 1000);
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => refreshPreview(e.document), delay);
  });
  context.subscriptions.push(onChange);

  // Also refresh when switching to a different markdown file
  const onEditor = vscode.window.onDidChangeActiveTextEditor((editor) => {
    if (panel && editor?.document.languageId === "markdown") {
      refreshPreview(editor.document);
    }
  });
  context.subscriptions.push(onEditor);
}

export function deactivate() {
  if (debounceTimer) clearTimeout(debounceTimer);
}

// ── Preview panel ───────────────────────────────────────────────────────────

function openPreview() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "markdown") {
    vscode.window.showWarningMessage("md2book: Open a Markdown file first.");
    return;
  }

  if (panel) {
    panel.reveal(vscode.ViewColumn.Beside);
    refreshPreview(editor.document);
    return;
  }

  panel = vscode.window.createWebviewPanel(
    "md2bookPreview",
    "md2book Preview",
    vscode.ViewColumn.Beside,
    {
      enableScripts: true,
      retainContextWhenHidden: true,
    }
  );

  panel.onDidDispose(() => {
    panel = undefined;
  });

  refreshPreview(editor.document);
}

// ── Run converter and update the webview ─────────────────────────────────────

function refreshPreview(document: vscode.TextDocument) {
  if (!panel) return;

  const source = document.getText();
  const baseDir = path.dirname(document.uri.fsPath);

  try {
    const html = convert(source, { baseDir });
    panel.webview.html = html;
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    panel.webview.html = errorPage(msg);
  }
}

// ── Export to browser ────────────────────────────────────────────────────────

async function exportToBrowser() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.document.languageId !== "markdown") {
    vscode.window.showWarningMessage("md2book: Open a Markdown file first.");
    return;
  }

  const source = editor.document.getText();
  const baseDir = path.dirname(editor.document.uri.fsPath);

  try {
    const html = convert(source, { baseDir });
    const tmpFile = path.join(
      tmpdir(),
      `md2book-${randomBytes(4).toString("hex")}.html`
    );
    await writeFile(tmpFile, html, "utf-8");
    await vscode.env.openExternal(vscode.Uri.file(tmpFile));
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    vscode.window.showErrorMessage(`md2book export failed: ${msg}`);
  }
}

// ── Error fallback page ─────────────────────────────────────────────────────

function errorPage(message: string): string {
  const escaped = message
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return `<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:sans-serif; padding:2em; color:#c33;">
  <h2>md2book preview error</h2>
  <pre>${escaped}</pre>
</body></html>`;
}
