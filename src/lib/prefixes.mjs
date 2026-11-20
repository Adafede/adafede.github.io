/**
 * RDFa prefix table.
 *
 * From _includes/prefixes.html in the Quarto project: lets posts write
 * `about="wd:Q12345"` instead of repeating the Wikidata namespace.
 *
 * `xsd` is the one addition. schema.org dates are written
 * `datatype="xsd:date"`, and neither the Quarto prefix table nor this one
 * declared it, so those literals did not resolve. Kept here rather than in the
 * Quarto source so the two builds stay comparable while the comparison runs.
 */
export const PREFIXES = {
  wd: "http://www.wikidata.org/entity/",
  wdt: "http://www.wikidata.org/prop/direct/",
  wdtn: "http://www.wikidata.org/prop/direct-normalized/",
  wdno: "http://www.wikidata.org/prop/novalue/",
  wds: "http://www.wikidata.org/entity/statement/",
  p: "http://www.wikidata.org/prop/",
  ps: "http://www.wikidata.org/prop/statement/",
  pq: "http://www.wikidata.org/prop/qualifier/",
  schema: "http://schema.org/",
  rdfs: "http://www.w3.org/2000/01/rdf-schema#",
  rdf: "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
  dcterms: "http://purl.org/dc/terms/",
  dc: "http://purl.org/dc/elements/1.1/",
  foaf: "http://xmlns.com/foaf/0.1/",
  skos: "http://www.w3.org/2004/02/skos/core#",
  owl: "http://www.w3.org/2002/07/owl#",
  bibo: "http://purl.org/ontology/bibo/",
  dbo: "http://dbpedia.org/ontology/",
  dbr: "http://dbpedia.org/resource/",
  cc: "http://creativecommons.org/ns#",
  cito: "http://purl.org/spar/cito/",
  orcid: "https://orcid.org/",
  ror: "https://ror.org/",
  viaf: "http://viaf.org/viaf/",
  xsd: "http://www.w3.org/2001/XMLSchema#",
};

const RDFA_ATTRS = [
  "about",
  "resource",
  "property",
  "rel",
  "typeof",
  "datatype",
];

const BARE_TERMS = new Set([
  "a",
  "describedby",
  "label",
  "title",
  "type",
  "value",
  "xml:lang",
  "role",
]);

const IRI = /^(?:[a-z][a-z0-9+.-]*:\/\/|(?:mailto|tel|urn|data|javascript|about):)/i;
const SCRIPT_OR_STYLE_RE = /<(script|style)\b[^>]*>[\s\S]*?(?:<\/\1\s*>|$)/gi;
const HTML_COMMENT_RE = /<!--[\s\S]*?-->/g;
const HTML_OPEN_TAG_RE = /<html\b((?:[^>"']|"[^"]*"|'[^']*')*)>/i;
const TAG_RE = /<[a-zA-Z][\w:-]*(?:\s+(?:[^<>"']|"[^"]*"|'[^']*')*)?>/g;

function stripNonContent(html) {
  let cleaned = String(html ?? "");
  let previous;
  do {
    previous = cleaned;
    cleaned = cleaned.replace(SCRIPT_OR_STYLE_RE, "");
  } while (cleaned !== previous);
  do {
    previous = cleaned;
    cleaned = cleaned.replace(HTML_COMMENT_RE, "");
  } while (cleaned !== previous);
  return cleaned;
}

/**
 * Rewrite `<html ... prefix="...">` on a built HTML document so it declares only
 * the RDFa prefixes actually referenced by CURIEs on that page.
 */
export function pruneRdfaPrefixes(html, prefixes = PREFIXES) {
  const htmlMatch = HTML_OPEN_TAG_RE.exec(html);
  if (!htmlMatch || !/\bprefix="[^"]*"/i.test(htmlMatch[0])) {
    return html;
  }

  const cleaned = stripNonContent(html);
  const used = new Set();
  const addTerms = (value) => {
    for (const term of value.split(/\s+/)) {
      if (!term || BARE_TERMS.has(term) || !term.includes(":")) continue;
      if (IRI.test(term)) continue;
      const prefix = term.slice(0, term.indexOf(":"));
      if (Object.hasOwn(prefixes, prefix)) used.add(prefix);
    }
  };

  const headMatch = /<head\b[^>]*>([\s\S]*?)<\/head>/i.exec(cleaned);
  if (headMatch) {
    for (const meta of headMatch[1].matchAll(
      /<meta\b[^>]*\bproperty="([^"]*)"/gi,
    )) {
      addTerms(meta[1]);
    }
  }

  const bodyScope = cleaned.replace(/<head\b[^>]*>[\s\S]*?<\/head>/gi, "");
  for (const m of bodyScope.matchAll(TAG_RE)) {
    const tag = m[0];
    if (/^<link\b/i.test(tag)) continue;
    for (const attr of RDFA_ATTRS) {
      const value = tag.match(new RegExp(`\\b${attr}="([^"]*)"`, "i"))?.[1];
      if (value) addTerms(value);
    }
  }

  const usedEntries = Object.entries(prefixes).filter(([prefix]) =>
    used.has(prefix),
  );
  const updatedHtmlTag = usedEntries.length
    ? htmlMatch[0].replace(
        /\bprefix="[^"]*"/i,
        `prefix="${usedEntries.map(([prefix, iri]) => `${prefix}: ${iri}`).join(" ")}"`,
      )
    : htmlMatch[0].replace(/\s+\bprefix="[^"]*"/i, "");

  return (
    html.slice(0, htmlMatch.index) +
    updatedHtmlTag +
    html.slice(htmlMatch.index + htmlMatch[0].length)
  );
}
