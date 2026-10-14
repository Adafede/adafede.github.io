import { parse, parseFragment, serialize } from 'parse5';

function appendText(node, parts, separateTags) {
  const tag = node.tagName;
  if (tag === 'script' || tag === 'style') return;

  if (node.nodeName === '#text') {
    parts.push(node.value);
    return;
  }

  if (separateTags && tag) parts.push(' ');
  for (const child of node.childNodes ?? []) appendText(child, parts, separateTags);
  if (node.content) appendText(node.content, parts, separateTags);
  if (separateTags && tag) parts.push(' ');
}

export function htmlText(html, { separateTags = false } = {}) {
  const parts = [];
  appendText(parseFragment(String(html ?? '')), parts, separateTags);
  return parts.join('').replace(/\s+/g, ' ').trim();
}

export function firstElement(html, tagName) {
  return findElement(parseFragment(String(html ?? '')), tagName);
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
  if (!element) return '';
  const parts = [];
  appendText(element, parts, false);
  return parts.join('').replace(/\s+/g, ' ').trim();
}

export function removeScriptAndStyle(html) {
  const document = parse(String(html ?? ''));
  const removeElements = (nodes) => nodes.filter((node) => {
    if (node.tagName === 'script' || node.tagName === 'style') return false;
    if (node.childNodes) node.childNodes = removeElements(node.childNodes);
    if (node.content?.childNodes) {
      node.content.childNodes = removeElements(node.content.childNodes);
    }
    return true;
  });

  document.childNodes = removeElements(document.childNodes);
  return serialize(document);
}
