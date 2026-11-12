import { JSON_SCHEMA, load } from "js-yaml";

const FRONTMATTER_RE =
  /^---[ \t]*\r?\n(?:([\s\S]*?)\r?\n)?---[ \t]*(?:\r?\n|$)/;

/**
 * Split a `---\n...\n---` YAML frontmatter block off a Markdown/Quarto file.
 * Returns `{ head: null, body: raw }` when no terminated frontmatter exists.
 */
export function splitFrontmatter(raw) {
  const text = String(raw ?? "");
  const match = FRONTMATTER_RE.exec(text);
  if (!match) return { head: null, body: text };
  return { head: match[1] ?? "", body: text.slice(match[0].length) };
}

/** Parse YAML frontmatter + Markdown body from a document string. */
export function parseFrontmatter(raw) {
  const { head, body } = splitFrontmatter(raw);
  if (head === null) return { data: {}, body };
  return { data: load(head, { schema: JSON_SCHEMA }) ?? {}, body };
}

/** Truncate to `limit` characters at a word boundary, never mid-word. */
export function truncateAtWord(text, limit) {
  const value = String(text ?? "").trim();
  if (value.length <= limit) return value;
  const clipped = value.slice(0, limit);
  const lastSpace = clipped.lastIndexOf(" ");
  const cut = lastSpace > limit * 0.6 ? clipped.slice(0, lastSpace) : clipped;
  return `${cut.replace(/[\s,;:.—-]+$/, "")}…`;
}
