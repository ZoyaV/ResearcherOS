"use strict";

const http = require("http");
const https = require("https");
const path = require("path");
const vscode = require("vscode");

const timers = new Map();
const pollers = new Map();
const commandIds = new Map();
const sentVersions = new Map();

function isPaperTex(document) {
  if (!document || document.uri.scheme !== "file") return false;
  const normalized = document.uri.fsPath.replaceAll("\\", "/");
  return path.basename(normalized) === "main.tex" && normalized.includes("/koi-structure/paper/");
}

function postJson(urlString, payload) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const data = Buffer.from(JSON.stringify(payload), "utf8");
    const transport = url.protocol === "https:" ? https : http;
    const request = transport.request(
      url,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Content-Length": data.length,
        },
        timeout: 3000,
      },
      (response) => {
        response.resume();
        response.on("end", () => {
          if (response.statusCode >= 200 && response.statusCode < 300) {
            resolve();
          } else if (response.statusCode === 404) {
            resolve();
          } else {
            reject(new Error(`ResearchOS returned ${response.statusCode}`));
          }
        });
      }
    );
    request.on("timeout", () => request.destroy(new Error("ResearchOS request timed out")));
    request.on("error", reject);
    request.end(data);
  });
}

function getJson(urlString) {
  return new Promise((resolve, reject) => {
    const url = new URL(urlString);
    const transport = url.protocol === "https:" ? https : http;
    const request = transport.get(url, { timeout: 3000 }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        if (response.statusCode === 404) {
          resolve(null);
        } else if (response.statusCode >= 200 && response.statusCode < 300) {
          try {
            resolve(JSON.parse(body));
          } catch (error) {
            reject(error);
          }
        } else {
          reject(new Error(`ResearchOS returned ${response.statusCode}`));
        }
      });
    });
    request.on("timeout", () => request.destroy(new Error("ResearchOS request timed out")));
    request.on("error", reject);
  });
}

function ensureCommandPolling(document, output) {
  const key = document.uri.toString();
  if (pollers.has(key)) return;
  pollers.set(
    key,
    setInterval(async () => {
      if (document.isClosed) return;
      if (document.isDirty && sentVersions.get(key) !== document.version) {
        scheduleDocument(document, output);
      }
      const config = vscode.workspace.getConfiguration("researchOS.paperBufferSync");
      const endpoint = new URL(
        String(config.get("endpoint", "http://127.0.0.1:8010/collaboration/editor-buffer"))
      );
      endpoint.pathname = `${endpoint.pathname}/command`;
      endpoint.searchParams.set("path", document.uri.fsPath);
      const after = commandIds.get(key);
      if (after) endpoint.searchParams.set("after", after);
      try {
        const response = await getJson(endpoint.toString());
        const command = response?.command;
        if (!command || command.id === after) return;
        if (document.isDirty && !command.force) return;
        commandIds.set(key, command.id);
        if (document.getText() === command.text) {
          if (command.save && document.isDirty) await document.save();
          return;
        }
        const edit = new vscode.WorkspaceEdit();
        edit.replace(
          document.uri,
          new vscode.Range(document.positionAt(0), document.positionAt(document.getText().length)),
          command.text
        );
        await vscode.workspace.applyEdit(edit);
        if (command.save) await document.save();
      } catch (error) {
        output.appendLine(`[command sync] ${error.message}`);
      }
    }, 350)
  );
}

function scheduleDocument(document, output) {
  if (!isPaperTex(document)) return;
  ensureCommandPolling(document, output);
  const key = document.uri.toString();
  clearTimeout(timers.get(key));
  const config = vscode.workspace.getConfiguration("researchOS.paperBufferSync");
  const debounceMs = Math.max(50, Number(config.get("debounceMs", 180)) || 180);
  const endpoint = String(
    config.get("endpoint", "http://127.0.0.1:8010/collaboration/editor-buffer")
  );
  timers.set(
    key,
    setTimeout(async () => {
      timers.delete(key);
      try {
        await postJson(endpoint, {
          path: document.uri.fsPath,
          text: document.getText(),
          version: document.version,
        });
        sentVersions.set(key, document.version);
      } catch (error) {
        output.appendLine(`[buffer sync] ${error.message}`);
      }
    }, debounceMs)
  );
}

function activate(context) {
  const output = vscode.window.createOutputChannel("ResearchOS Paper Buffer Sync");
  context.subscriptions.push(output);
  context.subscriptions.push(
    vscode.workspace.onDidChangeTextDocument((event) => {
      scheduleDocument(event.document, output);
    })
  );
  context.subscriptions.push(
    vscode.workspace.onDidCloseTextDocument((document) => {
      const key = document.uri.toString();
      clearTimeout(timers.get(key));
      timers.delete(key);
      clearInterval(pollers.get(key));
      pollers.delete(key);
      commandIds.delete(key);
      sentVersions.delete(key);
    })
  );
  const active = vscode.window.activeTextEditor?.document;
  if (active?.isDirty) scheduleDocument(active, output);
}

function deactivate() {
  for (const timer of timers.values()) clearTimeout(timer);
  for (const poller of pollers.values()) clearInterval(poller);
  timers.clear();
  pollers.clear();
  commandIds.clear();
  sentVersions.clear();
}

module.exports = { activate, deactivate };
