import { readdirSync } from "node:fs";
import { join } from "node:path";

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

const SCRIPT_OR_STYLE_RE = /<(script|style)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi;
const HTML_COMMENT_RE = /<!--[\s\S]*?-->/g;
const TAG_RE =
  /<![^>]*>|<\/?[a-zA-Z][\w:-]*(?:\s+(?:[^<>"']|"[^"]*"|'[^']*')*)?>/g;
const ATTR_RE =
  /([a-zA-Z_:][\w:.-]*)(?:\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s"'=<>`]+)))?/g;
const NAMED_ENTITIES = {
  amp: "&",
  lt: "<",
  gt: ">",
  quot: '"',
  apos: "'",
  nbsp: "\u00a0",
};

function safeCodePoint(cp) {
  return cp >= 1 && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff)
    ? String.fromCodePoint(cp)
    : "\uFFFD";
}

function decodeEntities(text) {
  return text.replace(
    /&(?:#(\d+)|#x([0-9a-fA-F]+)|([a-zA-Z0-9]+));/g,
    (match, dec, hex, named) => {
      if (dec) return safeCodePoint(Number.parseInt(dec, 10));
      if (hex) return safeCodePoint(Number.parseInt(hex, 16));
      return NAMED_ENTITIES[named.toLowerCase()] ?? match;
    },
  );
}

export function removeScriptAndStyle(html) {
  let cleaned = String(html ?? "");
  let previous;
  do {
    previous = cleaned;
    cleaned = cleaned.replace(SCRIPT_OR_STYLE_RE, "");
  } while (cleaned !== previous);
  return cleaned;
}

/**
 * Strip HTML comments repeatedly so a removal cannot reveal a new comment
 * boundary (incomplete multi-character sanitization).
 */
export function removeComments(html) {
  let cleaned = String(html ?? "");
  let previous;
  do {
    previous = cleaned;
    cleaned = cleaned.replace(HTML_COMMENT_RE, "");
  } while (cleaned !== previous);
  return cleaned;
}

export function htmlText(html, { separateTags = false } = {}) {
  const withoutComments = removeComments(removeScriptAndStyle(html));
  const stripped = withoutComments.replace(TAG_RE, separateTags ? " " : "");
  return decodeEntities(stripped).replace(/\s+/g, " ").trim();
}

export function firstElement(html, tagName) {
  const tag = String(tagName).toLowerCase();
  const escaped = tag.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const openRe = new RegExp(`<${escaped}\\b([^>]*)>`, "i");
  const cleaned = removeScriptAndStyle(html);
  const match = openRe.exec(cleaned);
  if (!match) return null;

  const attrs = [];
  for (const attr of match[1].matchAll(ATTR_RE)) {
    attrs.push({
      name: attr[1].toLowerCase(),
      value: decodeEntities(attr[2] ?? attr[3] ?? attr[4] ?? ""),
    });
  }

  const start = match.index + match[0].length;
  const tokenRe = new RegExp(`<(\\/)?${escaped}\\b[^>]*>`, "gi");
  tokenRe.lastIndex = start;
  let depth = 1;
  let closeIndex = -1;
  let token;
  while ((token = tokenRe.exec(cleaned)) !== null) {
    if (token[1]) {
      depth--;
      if (depth === 0) {
        closeIndex = token.index;
        break;
      }
    } else if (!token[0].endsWith("/>")) {
      depth++;
    }
  }
  const innerHtml = closeIndex >= 0 ? cleaned.slice(start, closeIndex) : "";

  return { tagName: tag, attrs, innerHtml };
}

export function elementText(html, tagName) {
  const element = firstElement(html, tagName);
  return element ? htmlText(element.innerHtml) : "";
}
