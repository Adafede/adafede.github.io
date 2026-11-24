import assert from "node:assert/strict";
import test from "node:test";
import { decodeEntities } from "../scripts/site/html.mjs";
import {
  encodeHtmlEntities,
  obfuscateEmailHtml,
  obfuscateMailto,
  spellEmail,
} from "../src/lib/email.mjs";

const ADDRESS = "rutz@imsb.biol.ethz.ch";

function revealObfuscatedHtml(html) {
  const withoutDecoy = html.replace(
    /<span class="contact-decoy"[^>]*>[\s\S]*?<\/span>/g,
    "",
  );
  const withoutComments = withoutDecoy.replace(/<!--[\s\S]*?-->/g, "");
  return decodeEntities(withoutComments);
}

test("obfuscateMailto encodes the full mailto URI without plaintext leakage", () => {
  const encoded = obfuscateMailto(ADDRESS);
  assert.doesNotMatch(encoded, /mailto:/i);
  assert.ok(!encoded.includes("@"));
  assert.ok(!encoded.includes(ADDRESS));
  assert.equal(decodeEntities(encoded), `mailto:${ADDRESS}`);
});

test("obfuscateEmailHtml adds decoy and comment while preserving decoded address", () => {
  const html = obfuscateEmailHtml(ADDRESS);
  assert.ok(!html.includes("@"));
  assert.ok(!html.includes(ADDRESS));
  assert.ok(html.includes('<span class="contact-decoy" aria-hidden="true">mail.</span>'));
  assert.ok(html.includes("<!--.invalid-->"));
  assert.equal(revealObfuscatedHtml(html), ADDRESS);
});

test("spellEmail formats readable email text and handles whitespace", () => {
  assert.equal(spellEmail(ADDRESS), "rutz [at] imsb [dot] biol [dot] ethz [dot] ch");
  assert.equal(spellEmail(`  ${ADDRESS}  `), "rutz [at] imsb [dot] biol [dot] ethz [dot] ch");
  assert.equal(spellEmail(""), "");
  assert.equal(spellEmail(null), "");
});

test("encodeHtmlEntities encodes ASCII and supplementary Unicode code points", () => {
  assert.equal(encodeHtmlEntities("a@b"), "&#97;&#64;&#98;");
  assert.equal(encodeHtmlEntities("a😀"), "&#97;&#128512;");
  assert.equal(encodeHtmlEntities(""), "");
  assert.equal(encodeHtmlEntities(undefined), "");
});

test("email helpers handle edge cases cleanly", () => {
  assert.equal(obfuscateMailto(""), "");
  assert.equal(obfuscateMailto("   "), "");
  assert.equal(obfuscateMailto(null), "");
  assert.equal(obfuscateMailto(`  ${ADDRESS}  `), obfuscateMailto(ADDRESS));

  assert.equal(obfuscateEmailHtml(""), "");
  assert.equal(obfuscateEmailHtml("   "), "");
  assert.equal(obfuscateEmailHtml(undefined), "");
  assert.equal(obfuscateEmailHtml(`  ${ADDRESS}  `), obfuscateEmailHtml(ADDRESS));

  const noAt = obfuscateEmailHtml("plain.example");
  assert.equal(noAt, encodeHtmlEntities("plain.example"));
  assert.ok(!noAt.includes("contact-decoy"));
  assert.ok(!noAt.includes("<!--"));

  const noDomainDot = obfuscateEmailHtml("user@localhost");
  assert.equal(noDomainDot, encodeHtmlEntities("user@localhost"));
  assert.ok(!noDomainDot.includes("contact-decoy"));
  assert.ok(!noDomainDot.includes("<!--"));
});
