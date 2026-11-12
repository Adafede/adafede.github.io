import assert from "node:assert/strict";
import test from "node:test";

import {
  parseFrontmatter,
  splitFrontmatter,
  truncateAtWord,
} from "../src/lib/frontmatter.mjs";

test("splitFrontmatter removes a terminated block and keeps the body", () => {
  assert.deepEqual(splitFrontmatter("---\ntitle: A\n---\nBody\n"), {
    head: "title: A",
    body: "Body\n",
  });
});

test("splitFrontmatter accepts CRLF frontmatter from the content pipeline", () => {
  assert.deepEqual(splitFrontmatter("---\r\ntitle: A\r\n---\r\nBody"), {
    head: "title: A",
    body: "Body",
  });
});

test("splitFrontmatter treats an unterminated block as body text", () => {
  const raw = "---\ntitle: A\nBody with no closing delimiter\n";
  assert.deepEqual(splitFrontmatter(raw), { head: null, body: raw });
});

test("splitFrontmatter handles an empty frontmatter block", () => {
  assert.deepEqual(splitFrontmatter("---\n---\nBody"), {
    head: "",
    body: "Body",
  });
});

test("splitFrontmatter ignores a block that does not start the document", () => {
  const raw = "Intro\n\n---\ntitle: A\n---\n";
  assert.deepEqual(splitFrontmatter(raw), { head: null, body: raw });
});

test("parseFrontmatter parses YAML data and returns the body", () => {
  const { data, body } = parseFrontmatter(
    "---\ntitle: A\ntags:\n  - one\n  - two\n---\nBody\n",
  );
  assert.deepEqual(data, { title: "A", tags: ["one", "two"] });
  assert.equal(body, "Body\n");
});

test("parseFrontmatter returns empty data and the whole document without a block", () => {
  assert.deepEqual(parseFrontmatter("Just prose."), {
    data: {},
    body: "Just prose.",
  });
});

test("truncateAtWord leaves short text untouched", () => {
  assert.equal(truncateAtWord("Short text", 20), "Short text");
  assert.equal(truncateAtWord("   Short text   ", 20), "Short text");
});

test("truncateAtWord cuts at a word boundary and appends an ellipsis", () => {
  assert.equal(truncateAtWord("one two three four", 10), "one two…");
  // The trailing comma belongs to the cut word, not to the excerpt.
  assert.equal(truncateAtWord("one two, three four", 10), "one two…");
});

test("truncateAtWord keeps a long unbroken word rather than returning nothing", () => {
  assert.equal(truncateAtWord("supercalifragilistic", 10), "supercalif…");
});
