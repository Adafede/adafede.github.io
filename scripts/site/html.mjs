import { readdirSync } from "node:fs";
import { join } from "node:path";
import { parse, parseFragment, serialize } from "parse5";

/**
 * Every .html file under a directory, recursively.
 *
 * Shared by the validators and the inline-CSS pass, which all walk a built site
 * the same way. Uses Dirent rather than a stat per entry so the walk costs one
 * readdir per directory rather than two syscalls per file.
 */
export function htmlFiles(dir) {
  const out = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) out.push(...htmlFiles(path));
    else if (entry.name.endsWith(".html")) out.push(path);
  }
  return out;
}

function appendText(node, parts, separateTags) {
  const tag = node.tagName;
  if (tag === "script" || tag === "style") return;

  if (node.nodeName === "#text") {
    parts.push(node.value);
    return;
  }

  if (separateTags && tag) parts.push(" ");
  for (const child of node.childNodes ?? [])
    appendText(child, parts, separateTags);
  if (node.content) appendText(node.content, parts, separateTags);
  if (separateTags && tag) parts.push(" ");
}

export function htmlText(html, { separateTags = false } = {}) {
  const parts = [];
  appendText(parseFragment(String(html ?? "")), parts, separateTags);
  return parts.join("").replace(/\s+/g, " ").trim();
}

export function firstElement(html, tagName) {
  return findElement(parseFragment(String(html ?? "")), tagName);
}

function findElement(node, tagName) {
  if (node.tagName === tagName) return node;
  for (const child of node.childNodes ?? []) {
    const found = findElement(child, tagName);
    if (found) return found;
  }
  if (node.content) return findElement(node.content, tagName);
  return null;
}

export function elementText(html, tagName) {
  const element = firstElement(html, tagName);
  if (!element) return "";
  const parts = [];
  appendText(element, parts, false);
  return parts.join("").replace(/\s+/g, " ").trim();
}

export function removeScriptAndStyle(html) {
  const document = parse(String(html ?? ""));
  const removeElements = (nodes) =>
    nodes.filter((node) => {
      if (node.tagName === "script" || node.tagName === "style") return false;
      if (node.childNodes) node.childNodes = removeElements(node.childNodes);
      if (node.content?.childNodes) {
        node.content.childNodes = removeElements(node.content.childNodes);
      }
      return true;
    });

  document.childNodes = removeElements(document.childNodes);
  return serialize(document);
}
