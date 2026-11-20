import assert from "node:assert/strict";
import test from "node:test";
import { PREFIXES, pruneRdfaPrefixes } from "../src/lib/prefixes.mjs";

const ALL_PREFIXES = Object.entries(PREFIXES)
  .map(([prefix, iri]) => `${prefix}: ${iri}`)
  .join(" ");

test("pruneRdfaPrefixes keeps only body-used prefixes in canonical order", () => {
  const html =
    `<!doctype html><html lang="en" vocab="https://schema.org/" prefix="${ALL_PREFIXES}">` +
    "<head><title>Home</title></head>" +
    '<body><div about="wd:Q97455964" property="wdt:P31" typeof="schema:Person">Ada</div></body>' +
    "</html>";

  const result = pruneRdfaPrefixes(html);
  assert.equal(
    result.match(/<html\b[^>]*prefix="([^"]*)"/)?.[1],
    `wd: ${PREFIXES.wd} wdt: ${PREFIXES.wdt} schema: ${PREFIXES.schema}`,
  );
});

test("pruneRdfaPrefixes keeps schema from head meta property while ignoring og and article", () => {
  const html =
    `<html lang="en" prefix="${ALL_PREFIXES}">` +
    '<head><meta property="og:title" content="X"><meta property="article:published_time" content="2026"><meta property="schema:type" content="ScholarlyArticle"></head>' +
    "<body><p>Plain body</p></body></html>";

  const result = pruneRdfaPrefixes(html);
  assert.equal(
    result.match(/<html\b[^>]*prefix="([^"]*)"/)?.[1],
    `schema: ${PREFIXES.schema}`,
  );
});

test("pruneRdfaPrefixes drops prefix attribute cleanly when no prefixes are used", () => {
  const html =
    `<!doctype html>\n<html lang="en" vocab="https://schema.org/" prefix="${ALL_PREFIXES}">` +
    "<head><title>Privacy</title></head>" +
    '<body><div property="mainContentOfPage" typeof="WebPageElement">Policy</div></body></html>';

  const result = pruneRdfaPrefixes(html);
  assert.doesNotMatch(result, /\bprefix=/);
  assert.ok(
    result.includes('<html lang="en" vocab="https://schema.org/">'),
    `expected clean <html> tag, got: ${result.slice(0, 120)}`,
  );
});

test("pruneRdfaPrefixes ignores scripts, styles, comments, links, and absolute IRIs", () => {
  const html =
    `<html lang="en" prefix="${ALL_PREFIXES}">` +
    "<head>" +
    '<style>.x{content:"cito:cites"}</style>' +
    '<script>const x = \'property="bibo:Article"\';</script>' +
    "</head>" +
    "<body>" +
    '<!-- <span about="foaf:Person" property="dcterms:title">commented</span> -->' +
    '<link rel="license" resource="cc:Attribution" href="https://creativecommons.org/licenses/by/4.0/" />' +
    '<a rel="https://schema.org/sameAs" href="mailto:ada@example.org">Mail</a>' +
    '<span about="wd:Q97455964">Ada</span>' +
    "</body></html>";

  const result = pruneRdfaPrefixes(html);
  assert.equal(
    result.match(/<html\b[^>]*prefix="([^"]*)"/)?.[1],
    `wd: ${PREFIXES.wd}`,
  );
});

test("pruneRdfaPrefixes returns documents without an html prefix attribute unchanged", () => {
  const html =
    '<!doctype html><html lang="en"><head><meta http-equiv="refresh" content="0;url=/"></head><body></body></html>';
  assert.equal(pruneRdfaPrefixes(html), html);
});
