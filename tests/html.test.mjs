import assert from "node:assert/strict";
import test from "node:test";
import {
  elementText,
  firstElement,
  htmlText,
  removeScriptAndStyle,
} from "../scripts/site/html.mjs";

test("extracts text without exposing executable or style contents", () => {
  assert.equal(
    htmlText(
      "<p>Safe <strong>text</strong><script>alert(1)</script><style>x{}</style></p>",
    ),
    "Safe text",
  );
});

test("uses HTML parsing rather than treating angle brackets as tags blindly", () => {
  assert.equal(htmlText("1 < 2 &amp; 3 > 2"), "1 < 2 & 3 > 2");
});

test("can preserve spacing at markup boundaries for link labels", () => {
  assert.equal(
    htmlText("Read<strong>PDF</strong>now", { separateTags: true }),
    "Read PDF now",
  );
});

test("finds the first matching HTML element independent of tag case", () => {
  const image = firstElement('<P>intro</P><IMG SRC="/cover.webp">', "img");
  assert.equal(
    image?.attrs.find(({ name }) => name === "src")?.value,
    "/cover.webp",
  );
  assert.equal(
    elementText("<P>first <b>paragraph</b></P><P>second</P>", "p"),
    "first paragraph",
  );
});

test("removes script and style elements including mixed-case tags", () => {
  const result = removeScriptAndStyle(
    "<!doctype html><html><head><STYLE>secret</STYLE></head><body><SCRIPT>bad()</SCRIPT><main>ok</main></body></html>",
  );
  assert.doesNotMatch(result, /secret|bad\(\)/);
  assert.match(result, /<main>ok<\/main>/);
});
