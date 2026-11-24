/**
 * Zero-JS email obfuscation helpers.
 *
 * Encodes email addresses and `mailto:` URIs into decimal HTML numeric character
 * references and splits displayed addresses with hidden CSS decoys and HTML
 * comments so naive scrapers cannot lift a working address from raw markup.
 */

/** Encode every Unicode code point in `value` as a decimal HTML entity. */
export function encodeHtmlEntities(value) {
  return [...String(value ?? "")]
    .map((char) => `&#${char.codePointAt(0)};`)
    .join("");
}

/**
 * Encode a full `mailto:<email>` URI as HTML entities so the `mailto:` scheme
 * itself never appears in plaintext in the HTML source.
 */
export function obfuscateMailto(email) {
  const trimmed = String(email ?? "").trim();
  return trimmed ? encodeHtmlEntities(`mailto:${trimmed}`) : "";
}

/**
 * Spell out an email address for plain-text or screen-reader display
 * (`"rutz [at] imsb [dot] ..."`).
 */
export function spellEmail(email) {
  return String(email ?? "")
    .replace(/@/g, " [at] ")
    .replace(/\./g, " [dot] ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Obfuscate an email address for visible HTML display using HTML entities,
 * a CSS-hidden decoy token (`.contact-decoy`), and an HTML comment.
 */
export function obfuscateEmailHtml(email) {
  const trimmed = String(email ?? "").trim();
  if (!trimmed) return "";

  const at = trimmed.indexOf("@");
  if (at < 0) return encodeHtmlEntities(trimmed);

  const local = trimmed.slice(0, at);
  const domain = trimmed.slice(at + 1);
  const dot = domain.indexOf(".");
  if (dot < 0) return encodeHtmlEntities(trimmed);

  const firstLabel = domain.slice(0, dot);
  const rest = domain.slice(dot);
  return `${encodeHtmlEntities(`${local}@`)}<span class="contact-decoy" aria-hidden="true">mail.</span>${encodeHtmlEntities(firstLabel)}<!--.invalid-->${encodeHtmlEntities(rest)}`;
}
