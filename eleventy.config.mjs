/**
 * Eleventy configuration.
 *
 *   Quarto   -> _site/           (system of record for content)
 *   Eleventy -> _eleventy_site/  (the candidate replacement)
 *
 * Both consume the same generated Markdown and JSON under src/content/, so the
 * content pipeline is shared and only the templating differs. That is what makes
 * the parallel comparison useful: a difference in output is a difference between
 * the pipelines, not between two sets of content.
 *
 * Eleventy has no component model, so reusable markup is Nunjucks includes and
 * data files here.
 */
import markdownIt from "markdown-it";
import { existsSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  elementText,
  firstElement,
  htmlText as extractHtmlText,
} from "./scripts/site/html.mjs";
import {
  MONTHS,
  detex,
  escapeHtml,
  inlineCitation,
  parseAuthors,
  parseBib,
  renderReference,
} from "./src/lib/bib.mjs";
import { truncateAtWord } from "./src/lib/frontmatter.mjs";
import siteContent, { resetSiteContent } from "./src/eleventy/_data/sitecontent.js";
import { buildJsonFeed } from "./src/lib/jsonFeed.mjs";

const ROOT = dirname(fileURLToPath(import.meta.url));
const BIB_PATH = fileURLToPath(new URL("./posts/references.bib", import.meta.url));
const SITE_HOST = "adafede.github.io";

let bib = parseBib(readFileSync(BIB_PATH, "utf-8"));

const MONTH_NAMES = MONTHS.map((m) => m[0].toUpperCase() + m.slice(1));

/**
 * CiTO predicates are snake_case in the post sources (`[@cites_as_data:key]`)
 * and camelCase in the rendered `[cito:…]` spans, which is what Quarto's
 * filters/extract-cito.lua produced.
 */
const CITO_CANONICAL = {
  cites: "cites",
  cites_as_recommended_reading: "citesAsRecommendedReading",
  cites_as_data_source: "citesAsDataSource",
  cites_as_motivational_work: "citesAsMotivationalWork",
  uses_method_in: "usesMethodIn",
  uses_dataset: "usesDataset",
  obtains_background_from: "obtainsBackgroundFrom",
  is_supplemented_by: "isSupplementedBy",
  is_supplement_to: "isSupplementTo",
  is_continued_by: "isContinuedBy",
  agrees_with: "agreesWith",
  disagrees_with: "disagreesWith",
  has_version: "hasVersion",
  concludes: "concludes",
  criticizes: "criticizes",
  documents: "documents",
  discusses: "discusses",
  mentions: "mentions",
  refutes: "refutes",
  replicates: "replicates",
  retracts: "retracts",
  reviews: "reviews",
  corrects: "corrects",
  disputes: "disputes",
  extends: "extends",
  updates: "updates",
  continues: "continues",
  forks: "forks",
};

const citoPredicate = (name) =>
  CITO_CANONICAL[name.toLowerCase()] ??
  // Unknown predicates fall back to camelCase, which is the general rule.
  name.replace(/_([a-z])/g, (_, c) => c.toUpperCase());

/**
 * The post citing itself.
 *
 * Quarto minted the post DOI and wrote a matching BibTeX entry into
 * references.bib before rendering, so every post cited itself. There is no
 * prerender step here, so the entry is synthesised from the frontmatter.
 * Matches what Quarto's filters/extract-cito.lua produced.
 */
function selfCitation(fm) {
  if (!fm.title || !fm.doi || !fm.pubDate) return null;
  const date = new Date(fm.pubDate);
  if (Number.isNaN(date.valueOf())) return null;

  const names = (fm.authors ?? []).map((a) => a?.name).filter(Boolean);
  const first = names[0] ?? "Adriano Rutz";
  const family = first.trim().split(/\s+/).pop().toLowerCase();

  return {
    key: `${family}${date.getUTCFullYear()}`,
    type: "article",
    fields: {
      author: names.join(" and "),
      year: String(date.getUTCFullYear()),
      month: `${MONTH_NAMES[date.getUTCMonth()]} ${date.getUTCDate()}`,
      title: String(fm.title),
      doi: String(fm.doi),
      url: `https://doi.org/${fm.doi}`,
    },
  };
}

/** CSL year disambiguation across the full author list. */
function yearSuffixes(keys, entries) {
  const out = new Map();
  const groups = new Map();
  for (const key of keys) {
    const entry = entries.get(key);
    if (!entry) continue;
    const author = parseAuthors(entry.fields.author ?? "").join(";");
    const year = detex(entry.fields.year ?? "");
    if (!author || !year) continue;
    const group = `${author}|${year}`;
    groups.set(group, [...(groups.get(group) ?? []), key]);
  }
  const letters = "abcdefghijklmnopqrstuvwxyz";
  for (const [, group] of groups) {
    if (group.length < 2) continue;
    const ordered = [...group].sort((a, b) =>
      detex(entries.get(a)?.fields.title ?? "").localeCompare(
        detex(entries.get(b)?.fields.title ?? ""),
      ),
    );
    ordered.forEach((key, i) => out.set(key, letters[i]));
  }
  return out;
}

/**
 * Coerce a frontmatter date to a Date.
 *
 * One Quarto source uses a partial date (`date: 2019-03`), which `new Date()`
 * rejects. An empty month takes it as the first of the month,
 * so this matches rather than emitting an invalid date.
 */
const toDate = (value) => {
  if (value instanceof Date) return value;
  // An empty value means "now", so `{{ '' | year }}` renders the current year.
  const text = String(value ?? "").trim() || new Date().toISOString();
  // A bare ISO date has to be pinned to UTC or it parses as local midnight and
  // can shift a day either side of the date boundary.
  if (/^\d{4}-\d{2}$/.test(text)) return new Date(`${text}-01T00:00:00Z`);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return new Date(`${text}T00:00:00Z`);
  const d = new Date(text);
  return d;
};

// --- superscript & subscript ------------------------------------------------

/**
 * Pandoc's `^2^` superscript and `~2~` subscript, which markdown-it has no
 * built-in rule for. Anchored like Pandoc: no whitespace inside the pair.
 */
function delimitedInlineRule(mdi, markerCode, markerChar, name, tag) {
  mdi.inline.ruler.before("emphasis", name, (state, silent) => {
    const start = state.pos;
    const max = state.posMax;
    if (state.src.charCodeAt(start) !== markerCode) return false;
    if (state.src[start + 1] === undefined || /\s/.test(state.src[start + 1]))
      return false;

    let pos = start + 1;
    while (pos < max) {
      const ch = state.src[pos];
      if (ch === markerChar) break;
      if (/\s/.test(ch) || ch === undefined) return false;
      pos++;
    }
    if (pos >= max || pos === start + 1) return false;

    if (!silent) {
      const token = state.push(name, "", 0);
      token.content = state.src.slice(start + 1, pos);
    }
    state.pos = pos + 1;
    return true;
  });

  mdi.renderer.rules[name] = (tokens, idx) =>
    `<${tag}>${escapeHtml(tokens[idx].content)}</${tag}>`;
}

export const md = markdownIt({ html: true, linkify: false, typographer: false });
delimitedInlineRule(md, 0x5e, "^", "superscript", "sup");
delimitedInlineRule(md, 0x7e, "~", "subscript", "sub");

const inlineMd = markdownIt({
  html: false,
  linkify: true,
  typographer: false,
});
inlineMd.linkify.set({ fuzzyLink: false, fuzzyEmail: false });
delimitedInlineRule(inlineMd, 0x5e, "^", "superscript", "sup");
delimitedInlineRule(inlineMd, 0x7e, "~", "subscript", "sub");
// Warm up linkify's regex state machine at module load time.
inlineMd.renderInline("https://example.org");

const rawIncludeCache = new Map();

// --- panel tabsets -----------------------------------------------------------

/**
 * Turns a Quarto panel-tabset into a set of tabs that work without JavaScript.
 *
 * Quarto's is a script that moves DOM between panes. This site ships none, so
 * the tabs are built from radio inputs and CSS: the checked state is the only
 * state there is, and the stylesheet does the rest. A reader with scripts
 * blocked gets the same working tabs as everyone else.
 *
 * The panels are ordinary content, not ARIA tabpanels. Real `role="tablist"`
 * markup without the script that implements arrow-key navigation and
 * `aria-selected` would advertise behaviour that does not exist, which is worse
 * than not claiming it. What is here is a labelled radio group, which is
 * keyboard-operable and announced correctly, controlling a region that is
 * simply shown or hidden.
 */
const PANEL_LANGS = {
  english: "en",
  francais: "fr",
  français: "fr",
  french: "fr",
  deutsch: "de",
  german: "de",
  italiano: "it",
  italian: "it",
  espanol: "es",
  español: "es",
  spanish: "es",
};

function resolvePanelLang(label) {
  const lower = String(label ?? "")
    .trim()
    .toLowerCase();
  if (/^[a-z]{2}$/.test(lower)) return lower;
  return PANEL_LANGS[lower] ?? "";
}

md.block.ruler.before(
  "fence",
  "panel_tabset",
  (state, startLine, endLine, silent) => {
    const start = state.bMarks[startLine] + state.tShift[startLine];
    const max = state.eMarks[startLine];
    if (state.src.slice(start, max).trim() !== "::: {.panel-tabset}")
      return false;
    if (silent) return true;

    // Collect until the closing fence.
    let nextLine = startLine;
    let closed = false;
    while (nextLine + 1 < endLine) {
      nextLine++;
      const from = state.bMarks[nextLine] + state.tShift[nextLine];
      const to = state.eMarks[nextLine];
      if (state.src.slice(from, to).trim() === ":::") {
        closed = true;
        break;
      }
    }
    if (!closed) return false;

    // Split the block at its `### Label` headings; each becomes one tab.
    const lines = [];
    for (let i = startLine + 1; i < nextLine; i++) {
      lines.push(state.src.slice(state.bMarks[i], state.eMarks[i]));
    }

    const panels = [];
    let current = null;
    for (const line of lines) {
      const heading = /^\s*###\s+(.+?)\s*$/.exec(line);
      if (heading) {
        current = { label: heading[1].trim(), lines: [] };
        panels.push(current);
      } else if (current) {
        current.lines.push(line);
      }
    }
    if (panels.length === 0) return false;

    const slug = (label) =>
      label
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "") || "panel";

    const html = [];
    html.push('<div class="tabset">');
    html.push('<fieldset class="tabset__tabs">');
    html.push('<legend class="tabset__legend">Language</legend>');
    panels.forEach((panel, index) => {
      const id = `tabset-${startLine}-${index + 1}-${slug(panel.label)}`;
      const lang = resolvePanelLang(panel.label);
      const langAttr = lang ? ` lang="${escapeHtml(lang)}"` : "";
      html.push(
        `<input class="tabset__radio tabset__radio--${index + 1}" type="radio" name="tabset-${startLine}" id="${id}"${index === 0 ? " checked" : ""}>`,
      );
      html.push(
        `<label class="tabset__tab tabset__tab--${index + 1}" for="${id}"${langAttr}>${escapeHtml(panel.label)}</label>`,
      );
    });
    html.push("</fieldset>");
    html.push('<div class="tabset__panels">');
    for (const [index, panel] of panels.entries()) {
      const lang = resolvePanelLang(panel.label);
      const langAttr = lang ? ` lang="${escapeHtml(lang)}"` : "";
      html.push(
        `<section class="tabset__panel tabset__panel--${index + 1}"${langAttr}>`,
      );
      html.push(md.render(panel.lines.join("\n"), state.env));
      html.push("</section>");
    }
    html.push("</div>");
    html.push("</div>");

    state.line = nextLine + 1;
    const token = state.push("html_block", "", 0);
    token.content = html.join("\n");
    token.block = true;
    return true;
  },
);

// --- citations -------------------------------------------------------------

md.inline.ruler.before("html_inline", "cito_citation", (state, silent) => {
  if (
    state.src.charCodeAt(state.pos) !== 0x5b /* [ */ ||
    state.src.charCodeAt(state.pos + 1) !== 0x40 /* @ */
  )
    return false;
  const close = state.src.indexOf("]", state.pos + 2);
  if (close === -1) return false;
  const inner = state.src.slice(state.pos + 1, close);
  if (inner.includes("[")) return false;

  const items = inner
    .split(";")
    .map((part) => part.trim().replace(/^@/, ""))
    .filter(Boolean)
    .map((item) => {
      const colon = item.indexOf(":");
      const hasPredicate =
        colon > 0 && /^[a-z_]+$/i.test(item.slice(0, colon).trim());
      const predicate = hasPredicate ? item.slice(0, colon).trim() : null;
      const key = (hasPredicate ? item.slice(colon + 1) : item).trim();
      return { key, predicate };
    })
    .filter((item) => Boolean(item.key));

  if (!items.length) return false;

  if (!silent) {
    const token = state.push("cito_citation", "", 0);
    token.meta = items;
    state.env.cito ??= new Map();
    for (const item of items) {
      if (!state.env.cito.has(item.key)) state.env.cito.set(item.key, new Set());
      if (item.predicate) state.env.cito.get(item.key).add(item.predicate);
    }
  }

  state.pos = close + 1;
  return true;
});

md.renderer.rules.cito_citation = (tokens, idx, _opts, env) => {
  const entries = env?.bibEntries ?? bib;
  const suffixes = env?.yearSuffixes;
  const byKey = new Map();
  for (const item of tokens[idx].meta) {
    if (!byKey.has(item.key)) byKey.set(item.key, new Set());
    if (item.predicate) byKey.get(item.key).add(citoPredicate(item.predicate));
  }
  const keys = [...byKey.keys()];
  const links = keys
    .map((key) => {
      const preds = byKey.get(key);
      const prop = preds.size
        ? [...preds].map((p) => `cito:${p}`).join(" ")
        : "cito:cites";
      const safeKey = escapeHtml(key);
      const label = escapeHtml(
        inlineCitation(entries.get(key), suffixes?.get(key) ?? ""),
      );
      return `<a href="#ref-${safeKey}" role="doc-biblioref" property="${escapeHtml(prop)}" resource="#ref-${safeKey}">${label}</a>`;
    })
    .join("; ");
  return `<span class="citation" data-cites="${escapeHtml(keys.join(" "))}">(${links})</span>`;
};

md.core.ruler.push("eleventy_references", (state) => {
  const cited = state.env.cito;
  if (!cited || !cited.size) return;

  // Per-document view, so one post's self-citation cannot leak into another.
  const entries = new Map(bib);
  const self = selfCitation(state.env.frontmatter ?? {});
  if (self) entries.set(self.key, self);

  const keys = [...cited.keys()].sort((a, b) =>
    inlineCitation(entries.get(a)).localeCompare(
      inlineCitation(entries.get(b)),
    ),
  );
  const suffixes = yearSuffixes(keys, entries);
  state.env.bibEntries = entries;
  state.env.yearSuffixes = suffixes;

  const html = keys
    .map((key) => {
      const predicates = [
        ...new Set([...(cited.get(key) ?? [])].map(citoPredicate)),
      ].sort();
      const resolved = entries.get(key) ?? { key, type: "misc", fields: {} };
      const doiAttr = resolved.fields?.doi
        ? ` resource="https://doi.org/${escapeHtml(resolved.fields.doi)}"`
        : "";
      const citoProp = predicates.length
        ? ` property="${escapeHtml(predicates.map((p) => `cito:${p}`).join(" "))}"`
        : "";
      const cito = predicates.length
        ? `<span class="cito"${citoProp}> [cito:${escapeHtml(predicates.join(","))}]</span>`
        : "";
      const entry = renderReference(resolved, suffixes.get(key) ?? "");
      return `<div class="csl-entry" id="ref-${escapeHtml(key)}" role="listitem" typeof="schema:ScholarlyArticle"${doiAttr}>${entry}${cito}</div>`;
    })
    .join("");

  state.env.references = html;
});

function mergeRel(attrs, extraTokens) {
  const relRe = /\srel=(["'])([^"']*)\1/i;
  const match = attrs.match(relRe);
  if (!match) return `${attrs} rel="${extraTokens.join(" ")}"`;
  const existing = match[2].split(/\s+/).filter(Boolean);
  const combined = [...new Set([...existing, ...extraTokens])].join(" ");
  return attrs.replace(relRe, ` rel="${combined}"`);
}

export function describeTarget(href) {
  try {
    const u = new URL(href, `https://${SITE_HOST}`);
    if (/\.pdf$/i.test(u.pathname)) return "PDF";
    if (u.hostname !== SITE_HOST) return "external page";
    if (u.pathname === "/") return "home page";
    return "internal page";
  } catch {
    return /\.pdf$/i.test(href) ? "PDF" : "external page";
  }
}

export default function (eleventyConfig) {
  eleventyConfig.setQuietMode(true);
  let affiliationsMap = new Map();
  let artworkManifest = {};
  let artworkThumbnails = {};
  let artworkSizes = {};

  const inlineMarkdownCache = new Map();
  const renderedCache = new Map();
  const plainTextCache = new Map();

  const readArtworkManifest = (name) => {
    const path = join(ROOT, "public", "images", "artwork", name);
    if (!existsSync(path)) return {};
    try {
      return JSON.parse(readFileSync(path, "utf-8"));
    } catch {
      return {};
    }
  };

  const refreshState = () => {
    resetSiteContent();
    rawIncludeCache.clear();
    inlineMarkdownCache.clear();
    renderedCache.clear();
    plainTextCache.clear();
    if (existsSync(BIB_PATH)) bib = parseBib(readFileSync(BIB_PATH, "utf-8"));
    affiliationsMap = new Map(
      siteContent()
        .affiliations()
        .map((a) => [a.id, a]),
    );
    artworkManifest = readArtworkManifest("manifest.json");
    artworkThumbnails = readArtworkManifest("thumbnails.json");
    artworkSizes = readArtworkManifest("sizes.json");
  };
  refreshState();
  eleventyConfig.on("eleventy.before", refreshState);

  // --- assets --------------------------------------------------------
  eleventyConfig.addPassthroughCopy({
    "build/eleventy/styles.css": "styles.css",
  });
  eleventyConfig.addPassthroughCopy({ "src/eleventy/static": "." });
  eleventyConfig.addPassthroughCopy({ public: "." });

  // Root-level resources that Quarto handles via `resources:` in _quarto.yml.
  // Eleventy needs explicit passthrough copies for each.
  eleventyConfig.addPassthroughCopy({ ".well-known": ".well-known" });
  eleventyConfig.addPassthroughCopy({ images: "images" });
  eleventyConfig.addPassthroughCopy("robots.txt");
  eleventyConfig.addPassthroughCopy("_headers");
  eleventyConfig.addPassthroughCopy("humans.txt");
  eleventyConfig.addPassthroughCopy("llm.txt");
  eleventyConfig.addPassthroughCopy("llms.txt");
  eleventyConfig.addPassthroughCopy("llms-full.txt");
  eleventyConfig.addPassthroughCopy("site.webmanifest");

  eleventyConfig.addWatchTarget("src/content/");
  eleventyConfig.addWatchTarget("posts/references.bib");

  // --- transforms ----------------------------------------------------
  const EXTERNAL_LINK_RE = /<a\b([^>]*)>/g;
  const HREF_RE = /\bhref=(["'])([^"']*)\1/i;

  eleventyConfig.addTransform("externalLinks", (content, outputPath) => {
    if (!outputPath || !outputPath.endsWith(".html")) return content;
    return content.replace(EXTERNAL_LINK_RE, (tag, attrs) => {
      if (!attrs.includes("http")) return tag;
      const hrefMatch = attrs.match(HREF_RE);
      if (!hrefMatch) return tag;
      const href = hrefMatch[2];
      if (!href.startsWith("http://") && !href.startsWith("https://"))
        return tag;
      let url;
      try {
        url = new URL(href);
      } catch {
        return tag;
      }
      if (url.protocol !== "http:" && url.protocol !== "https:") return tag;
      if (url.hostname === SITE_HOST) return tag;

      let nextAttrs = mergeRel(attrs, ["noopener", "noreferrer"]);
      if (!/\btarget=/i.test(nextAttrs)) nextAttrs += ' target="_blank"';
      return `<a${nextAttrs}>`;
    });
  });

  // --- collections ---------------------------------------------------
  eleventyConfig.addCollection("posts", () => siteContent().posts());
  eleventyConfig.addCollection("articles", () => siteContent().articles());
  eleventyConfig.addCollection("talks", () => siteContent().talks());
  eleventyConfig.addCollection("teaching", () => siteContent().teaching());
  eleventyConfig.addCollection("variaItems", () => siteContent().varia());

  const ARTICLE_GROUPS = [
    { key: "first", label: "Articles as single first author", table: false },
    { key: "shared", label: "Articles as shared first author", table: false },
    { key: "co", label: "Articles as co-author", table: true },
    { key: "thesis", label: "Doctoral thesis", table: true },
  ];

  eleventyConfig.addCollection("articleGroups", () => {
    const articles = siteContent().articles();
    return ARTICLE_GROUPS.map((group) => ({
      ...group,
      items: articles
        .filter((a) => a.data.group === group.key)
        .sort((a, b) => toDate(b.data.date) - toDate(a.data.date)),
    }));
  });

  // --- global data ---------------------------------------------------
  // Not named `cv`: Eleventy reserves that on the data cascade.
  eleventyConfig.addGlobalData("curriculum", () => siteContent().cv());
  eleventyConfig.addGlobalData("profiles", () => siteContent().profiles());
  eleventyConfig.addGlobalData("varia", () => siteContent().varia());

  eleventyConfig.addGlobalData("postsJsonFeed", () =>
    buildJsonFeed(siteContent().posts(), {
      url: "https://adafede.github.io/posts.html",
      renderBody: (post) => renderBody(post.body, post.data),
    }),
  );

  // --- filters -------------------------------------------------------
  eleventyConfig.setLibrary("md", md);
  eleventyConfig.addShortcode("rawInclude", (name) => {
    let html = rawIncludeCache.get(name);
    if (html === undefined) {
      html = readFileSync(
        join(ROOT, "src", "eleventy", "_includes", name),
        "utf-8",
      );
      rawIncludeCache.set(name, html);
    }
    return html;
  });

  const GENERIC_LINK_TEXT = /^\s*(here|link|this|read more|more|visit|click here)\s*$/i;

  /** The text of a fragment of HTML, tags out. */
  function stripTags(html) {
    return extractHtmlText(html, { separateTags: true });
  }

  /** The text of the first paragraph of a rendered body, or ''. */
  function firstParagraphText(html) {
    return elementText(html, "p");
  }

  /** The `src` of the first image in a rendered body, or ''. */
  function firstImageSrc(html) {
    return (
      firstElement(html, "img")?.attrs.find(({ name }) => name === "src")
        ?.value ?? ""
    );
  }

  function markPdfLinks(html) {
    return String(html ?? "").replace(
      /<a\b([^>]*?)href="([^"]*\.pdf(?:[?#][^"]*)?)"([^>]*)>([\s\S]*?)<\/a>/gi,
      (_match, before, href, after, text) => {
        const rawAttrs = `${before}href="${href}"${after}`;
        let attrs = mergeRel(rawAttrs, ["noopener", "noreferrer"]);
        if (!/\btarget=/i.test(attrs)) attrs += ' target="_blank"';

        const saysPdf = /\bpdf\b/i.test(stripTags(text));
        const label = saysPdf ? "" : '<span class="link-format"> (PDF)</span>';

        return `<a${attrs}>${text}${label}</a>`;
      },
    );
  }

  eleventyConfig.addFilter("inlineMarkdown", (value) => {
    if (!value) return "";
    const key = String(value);
    if (inlineMarkdownCache.has(key)) return inlineMarkdownCache.get(key);
    const rendered = markPdfLinks(
      inlineMd
        .renderInline(key)
        .replace(/<a href="([^"]+)">([^<]*)<\/a>/g, (match, href, text) =>
          GENERIC_LINK_TEXT.test(text)
            ? `<a href="${href}">${text}<span class="visually-hidden"> (${describeTarget(href)})</span></a>`
            : match,
        ),
    );
    inlineMarkdownCache.set(key, rendered);
    return rendered;
  });

  function renderBody(body, frontmatter = {}) {
    if (!body) return { html: "", references: [] };
    const cacheKey = `${frontmatter.doi ?? frontmatter.title ?? ""}\0${body}`;
    if (renderedCache.has(cacheKey)) return renderedCache.get(cacheKey);
    const env = { frontmatter };
    let html = markPdfLinks(md.render(body, env));

    if (env.references) {
      const block = `<div class="references csl-bib-body hanging-indent" id="refs" role="list" property="citation">${env.references}</div>`;
      const refHeadingRe = /<h2\b[^>]*>\s*References\s*<\/h2>/i;
      html = refHeadingRe.test(html)
        ? html.replace(refHeadingRe, (m) => `${m}\n${block}`)
        : `${html}\n${block}`;
    }

    // The DOIs in the reference list, lifted back out of the rendered block.
    // This is Quarto's `_references`, and it is the only place a feed reader can
    // get from a post to the papers behind it.
    //
    // Scoped to the bibliography rather than the whole body on purpose: a DOI
    // linked in passing is not a reference, and listing it as one turns the
    // feed's citation list into a list of everything the post ever mentioned.
    //
    // Each reference also carries its CiTO predicates — the `[cito:…]` spans
    // inside the entry. Quarto's postrender injected those into the RSS feed
    // before converting it to JSON, so a reader parsing `_references` has always
    // been able to see how a post uses a paper. Dropping them here would quietly
    // delete that annotation.
    const references = [];
    const bibliography = env.references || "";
    const ownDoi = String(frontmatter.doi || "").toLowerCase();
    const entryRe = /<div class="csl-entry"[^>]*>([\s\S]*?)<\/div>/g;
    for (const match of bibliography.matchAll(entryRe)) {
      const entry = match[1];
      const doiMatch = entry.match(
        /https?:\/\/(?:dx\.)?doi\.org\/([^\s"'<)]+)/i,
      );
      if (!doiMatch) continue;
      const doi = doiMatch[1].replace(/[.,;]$/, "");
      // A post that lists itself among its own references is not a reference.
      // Quarto drops the self-citation here, and a feed that reports one back to
      // the reader as "this post cites this post" reads as a bug.
      if (doi.toLowerCase() === ownDoi) continue;
      if (references.some((r) => r.doi === doi)) continue;
      const ref = { url: `https://doi.org/${doi}`, doi };
      const cito = [];
      for (const c of entry.matchAll(/\[cito:([^\]]+)\]/g)) {
        for (const p of c[1].split(",")) {
          const t = p.trim();
          if (t && !cito.includes(t)) cito.push(t);
        }
      }
      if (cito.length) ref.cito = cito;
      references.push(ref);
    }

    const result = {
      html,
      references,
      // The first paragraph, tags out. The Quarto feed used the first paragraph
      // as the item summary; the truncated page meta description is a page
      // concern, not a feed one, so the feed gets the whole paragraph.
      firstParagraph: firstParagraphText(html),
      // The first figure's source, absolutized by the feed builder.
      image: firstImageSrc(html),
    };
    renderedCache.set(cacheKey, result);
    return result;
  }

  eleventyConfig.addFilter(
    "renderMarkdown",
    (body, frontmatter = {}) => renderBody(body, frontmatter).html,
  );
  /**
   * The newest date among a collection of posts, as a Date or null.
   *
   * A post's own modification date wins over its publication date, so the feed's
   * single build date moves when a post is edited rather than going stale.
   */
  const pickNewestDate = (items, pick) => {
    let newest = null;
    for (const item of items ?? []) {
      const value = pick(item);
      const date =
        value instanceof Date ? value : value ? new Date(value) : null;
      if (date && !Number.isNaN(date.valueOf()) && (!newest || date > newest))
        newest = date;
    }
    return newest;
  };

  eleventyConfig.addFilter("latestPostDate", (posts) =>
    pickNewestDate(posts, (post) => post.data.updatedDate || post.data.pubDate),
  );

  eleventyConfig.addFilter("latestDate", pickNewestDate);

  /**
   * A string, percent-encoded for use in a query string.
   *
   * Post titles carry spaces, colons and ampersands, all of which would
   * otherwise change the meaning of the URL they are interpolated into.
   */
  eleventyConfig.addFilter("urlencode", (value) =>
    encodeURIComponent(String(value ?? "")),
  );

  /**
   * The first `count` items of an array.
   *
   * A missing count means "all of them", so feeds that have no cap do not have
   * to carry a `limit` just to be sliced.
   */
  eleventyConfig.addFilter("limitCount", (items, count) =>
    count ? items.slice(0, count) : items,
  );

  eleventyConfig.addFilter("readableDate", (value) => {
    const d = toDate(value);
    return Number.isNaN(d.valueOf()) ? "" : d.toISOString().slice(0, 10);
  });
  /** `2026-02-11` -> `02-11`, for the timeline's date column. */
  eleventyConfig.addFilter("monthDay", (value) => {
    const d = toDate(value);
    // Slice the *formatted* day, not the ISO timestamp: toISOString() returns
    // `2026-02-11T00:00:00.000Z`, so .slice(5) on it yields the whole tail.
    return Number.isNaN(d.valueOf()) ? "" : d.toISOString().slice(5, 10);
  });
  eleventyConfig.addFilter("year", (value) => toDate(value).getUTCFullYear());
  eleventyConfig.addFilter("isoDate", (value) => toDate(value).toISOString());
  eleventyConfig.addFilter("toRfc822", (value) =>
    new Date(toDate(value)).toUTCString(),
  );
  eleventyConfig.addFilter("stripTags", (html) => stripTags(html));

  // Nunjucks has no `map`, so the operations a component would do inline are
  // provided here instead.
  eleventyConfig.addFilter("joinNames", (items) =>
    (items ?? [])
      .map((item) => item?.name)
      .filter(Boolean)
      .join(", "),
  );
  eleventyConfig.addFilter("sliceYears", (items) =>
    [
      ...new Set(
        (items ?? []).map((i) => toDate(i.data?.date ?? i).getUTCFullYear()),
      ),
    ].sort((a, b) => b - a),
  );
  /** Varia cards grouped by their subdirectory, in the order defined by varia.qmd. */
  const VARIA_GROUPS = {
    adafede: { label: "Extras", order: 1 },
    lotus: { label: "LOTUS", order: 2 },
    taxonomicallyinformedannotation: {
      label: "Taxonomically Informed Metabolite Annotation",
      order: 3,
    },
    additional_contributions: { label: "Additional contributions", order: 4 },
  };
  eleventyConfig.addFilter("groupByVaria", (cards) => {
    const groups = new Map();
    for (const card of cards) {
      const key = card.data.group;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(card);
    }
    return [...groups.entries()]
      .sort(
        ([a], [b]) =>
          (VARIA_GROUPS[a]?.order ?? 99) - (VARIA_GROUPS[b]?.order ?? 99) ||
          a.localeCompare(b),
      )
      .map(([id, items]) => ({
        id: id.toLowerCase().replace(/[^a-z0-9]+/g, "-"),
        label:
          VARIA_GROUPS[id]?.label ??
          id.replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
        items: items.sort((a, b) => a.data.title.localeCompare(b.data.title)),
      }));
  });

  /**
   * Every distinct tag across a collection, most-used first, with counts.
   * Precomputed because Nunjucks cannot filter inside {% set %}.
   */
  eleventyConfig.addFilter("tagCounts", (items) => {
    const counts = new Map();
    for (const item of items ?? []) {
      for (const tag of item.data?.tags ?? [])
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
    }
    return [...counts.entries()]
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
  });

  /**
   * The tags on one item, lowercased, as a delimited list for `data-tags`.
   *
   * Pipe-delimited with a leading and trailing pipe so each tag is bracketed:
   * the no-JS filter matches with `[data-tags*="|tag name|"]`, and the brackets
   * stop one tag matching inside another ("sciences" must not hit "science").
   * `~=` is not an option because it only ever matches a single whitespace-
   * delimited token, and tags like "Open Science" are two words.
   */
  eleventyConfig.addFilter(
    "tagKey",
    (item) =>
      `|${(item.data?.tags ?? []).map((t) => String(t).toLowerCase()).join("|")}|`,
  );

  /** The CV's four sections, newest first, for the section loop. */
  eleventyConfig.addFilter("cvSections", (data) =>
    [data.experience, data.education, data.awards, data.sports]
      .filter((section) => section?.entries?.length)
      .map((section) => ({
        ...section,
        id: section.label.toLowerCase().replace(/[^a-z]+/g, "-"),
        // Newest first: Quarto ordered by filename, which reads oldest-first.
        entries: [...section.entries].sort(
          (a, b) => (b.startYear ?? 0) - (a.startYear ?? 0),
        ),
      })),
  );

  /**
   * Contact details obfuscated, in a form a person can still read.
   *
   * The email is spelled out with [at], and every digit is separated by a
   * zero-width space. A phone number is the thing worth breaking up, and a
   * scraper lifts it as an unbroken run of digits — so breaking the run is what
   * does the work, not disguising the letters around it, which would only make
   * the page worse to read.
   *
   * Zero-width rather than visible spaces because the value has to stay
   * copy-pasteable: a visible separator ends up in whatever the reader pastes it
   * into. A zero-width space is invisible on screen and dropped by most editors
   * and mail clients.
   *
   * Worth being clear about the ceiling: this defeats harvesting that looks for
   * a pattern. It does not defeat anything that renders the page, and no amount
   * of obfuscation does, short of not publishing the value.
   */
  eleventyConfig.addFilter("obfuscateContact", (value) => {
    const ZWSP = "\u200B";
    return String(value ?? "")
      .replace(/@/g, " [at] ")
      .replace(/\d/g, (d) => `${d}${ZWSP}`);
  });

  /**
   * The schema.org property a CV header fact is, keyed off its label.
   *
   * "Status" and "Field" said almost nothing, so the labels in cv.qmd are the
   * ones a CV actually uses. That also means the label is a safe key for the
   * structured data: "Current position" is a jobTitle, "Areas of expertise" is
   * knowsAbout, "Languages" is knowsLanguage. Without this the facts are free
   * text, and a machine reading the page has to infer what they mean from where
   * they appear.
   *
   * Matching on the label rather than a position in a list, because the labels
   * are the part that has a meaning.
   */
  eleventyConfig.addFilter("schemaProperty", (label) => {
    const value = String(label ?? "").toLowerCase();
    if (/position|role|title/.test(value)) return "jobTitle";
    if (/language/.test(value)) return "knowsLanguage";
    if (/expertise|specials|interest|field/.test(value)) return "knowsAbout";
    return "";
  });

  /**
   * A string as HTML numeric character references, every character of it.
   *
   * The address is published to people who should be able to click it, and not
   * to the crawlers and scrapers that harvest addresses off the open web.
   * Encoding is what separates the two without making the page behave
   * differently for anyone: the browser decodes the entities before the link is
   * ever used, so a human clicking it gets a working mailto, while the bytes in
   * the file are not an address.
   *
   * This is obfuscation, not protection. A scraper that decodes entities — which
   * a competent one does — still recovers the address, and nothing here should
   * be relied on to keep a genuinely private address private. It raises the cost
   * of the naive harvesting that happens at scale, and that is the whole of it.
   *
   * Deliberately not conditional on user-agent. Serving crawlers different
   * content from humans is cloaking, and search engines treat it as a
   * manipulation technique and can act on the whole site. Every visitor gets
   * byte-identical markup.
   */
  eleventyConfig.addFilter("obfuscate", (value) =>
    [...String(value ?? "")].map((c) => `&#${c.codePointAt(0)};`).join(""),
  );

  /**
   * An address spelled out for reading: "rutz [at] imsb [dot] …".
   *
   * For the visible text where the address itself has to be legible. The words
   * keep it copy-pasteable by hand and screen-reader legible, while the pattern a
   * harvester matches on — one run of characters, an @, a domain — does not
   * appear.
   */
  eleventyConfig.addFilter("spellEmail", (value) =>
    String(value ?? "")
      .replace(/@/g, " [at] ")
      .replace(/\./g, " [dot] ")
      .replace(/\s+/g, " ")
      .trim(),
  );

  /**
   * The first `count` words of some text, cut at a word boundary.
   *
   * For feed summaries. Cut on a word rather than a character so the last word
   * is not cut in half, and an ellipsis is added only when there was more to
   * come, so a short description is not given a full stop it did not have.
   */
  eleventyConfig.addFilter("truncateWords", (value, count) => {
    const words = String(value ?? "")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (words.length <= count) return words.join(" ");
    return `${words.slice(0, count).join(" ")}…`;
  });

  /**
   * Plain text for a meta description.
   *
   * A description ends up in a content attribute, and Nunjucks escapes it on
   * the way in. An abstract that carries Markdown autolinks (`<https://…>`)
   * arrives already escaped, so it would be escaped a second time and reach the
   * crawler as `&amp;lt;https://…`. Strip the markup here, before any
   * templating touches it.
   */
  eleventyConfig.addFilter("plainText", (value) => {
    const key = String(value ?? "");
    if (plainTextCache.has(key)) return plainTextCache.get(key);
    const markdown = key
      .replace(/<https?:\/\/[^>\s]+>/gi, " ")
      .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1") // links
      .replace(/[*_`]/g, ""); // emphasis and code markers
    const text = extractHtmlText(markdown)
      // A description is prose, not code: quotes and apostrophes carry no
      // meaning here, and keeping them means the attribute is escaped twice
      // (once by eleventyComputed, once by the content attribute) and the
      // reader sees a literal &quot;.
      .replace(/["'\u2018\u2019]/g, "")
      .replace(/\s+/g, " ")
      .trim();
    // Roughly what a search result will show; the rest is truncated by the
    // consumer anyway, and a description that fits is one that gets read.
    const out = truncateAtWord(text, 300);
    plainTextCache.set(key, out);
    return out;
  });

  /**
   * Meta description for an article, derived when it has no abstract.
   *
   * A filter rather than a template expression because Nunjucks reads the `?`
   * of a ternary as part of its own syntax.
   */
  eleventyConfig.addFilter("orDescription", (abstract, data) => {
    if (abstract) return abstract;
    const parts = [`${data.title}.`];
    if (data.venue) parts.push(`Published in ${data.venue}.`);
    if (data.authors?.length) {
      parts.push(`Authors: ${data.authors.map((a) => a.name).join(", ")}.`);
    }
    if (data.tags?.length) parts.push(`Topics: ${data.tags.join(", ")}.`);
    return truncateAtWord(parts.join(" "), 300);
  });

  /**
   * Resolve an author's affiliation id to its record, so templates can show the
   * name and link it to the ROR entry and Wikidata item Quarto linked to.
   */
  const affiliation = (id) => affiliationsMap.get(id) ?? {};
  /**
   * Marks for the registries this site links out to.
   *
   * All five are the publishers' own files, under static/logos/:
   *
   *   ORCID          ORCID/ORCID-Source, static/img/id-icon.svg
   *   ROR            ror-community/ror-logos
   *   Scholia        Wikimedia Commons, Scholia_Logo_Improved.svg. Note that
   *                   file's width/height attributes disagree with its
   *                   viewBox, so it must be sized by height alone.
   *   Google Scholar Wikimedia Commons
   *   DOI            DOI Foundation, doi.svg
   *
   * The remaining marks (email, GitHub, PDF) are drawn, because nothing
   * publishes one. They are paths rather than <text>: a checker treats text
   * inside an inline <svg> as real text and measures it, which is how an
   * earlier ORCID "iD" failed on contrast when the mark was correct.
   *
   * All of them are decorative: the link text already names the registry, so
   * they carry a null alt or aria-hidden.
   */
  const LOGO_FILES = {
    orcid: "orcid-id.svg",
    ror: "ror-icon-rgb-transparent.svg",
    scholia: "scholia.svg",
    scholar: "google-scholar.svg",
    doi: "doi.svg",
  };

  /** Drawn marks, for the places no registry publishes an icon. */
  const DRAWN = {
    // LinkedIn's own square badge is a solid blue tile that reads louder than
    // every other mark on the page. The "in" logotype on its own is the same
    // brand shape and takes the text colour, so it sits with the rest.
    linkedin:
      '<circle cx="4.4" cy="4.6" r="2.1"/>' +
      '<path d="M2.6 8.6h3.6v12.2H2.6zM9 8.6h3.45v1.67h.05a3.78 3.78 0 0 1 3.4-1.87c3.64 0 4.31 2.4 4.31 5.52v6.88h-3.6v-6.1c0-1.46-.03-3.34-2.03-3.34-2.04 0-2.35 1.59-2.35 3.23v6.21H9z"/>',
    email:
      '<path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M3 6.5h18v11H3zM3 7l9 6.5L21 7"/>',
    github:
      '<path d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.89 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2"/>',
  };

  /**
   * Intrinsic box for each cached logo, in the units the SVG declares.
   *
   * An <img> with no width and no height is a layout shift waiting to happen:
   * the browser has nothing to reserve, so the row jumps when the file lands.
   * These marks are all rendered at about 1em, so the exact numbers barely
   * matter — what matters is that both attributes are present and describe the
   * same box.
   */
  const LOGO_SIZES = {
    orcid: [256, 256],
    ror: [156, 111],
    scholia: [512, 512],
    scholar: [512, 512],
    doi: [512, 512],
  };

  const renderRegistryIcon = (name) => {
    if (LOGO_FILES[name]) {
      const [w, h] = LOGO_SIZES[name] ?? [512, 512];
      return `<img class="registry-icon registry-icon--${name}" src="/logos/${LOGO_FILES[name]}" alt="" width="${w}" height="${h}" loading="lazy" decoding="async">`;
    }
    switch (name) {
      case "email":
      case "linkedin":
      case "github":
        return `<svg class="registry-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${DRAWN[name]}</svg>`;
      case "pdf":
        return (
          '<svg class="registry-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
          '<path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" d="M6 2.8h8l4 4v14.4H6z"/>' +
          '<path d="M14 2.8v4h4zM8.4 16.2h7.2v1.5H8.4z"/>' +
          "</svg>"
        );
      default:
        return "";
    }
  };
  eleventyConfig.addShortcode("registryIcon", renderRegistryIcon);

  const ICON_ORCID = renderRegistryIcon("orcid");
  const ICON_SCHOLIA = renderRegistryIcon("scholia");
  const ICON_ROR = renderRegistryIcon("ror");

  const renderAffiliationSpan = (affId, linkClass = "") => {
    const aff = affiliation(affId);
    const about = aff.qid ? ` about="wd:${escapeHtml(aff.qid)}"` : "";
    const cls = linkClass ? ` class="${linkClass}"` : "";
    const name = `<span${linkClass && !aff.ror && !aff.qid ? cls : ""} property="name">${escapeHtml(aff.name ?? "")}</span>`;
    let inner = name;
    if (aff.ror) {
      const ror = escapeHtml(aff.ror);
      inner = `<a${cls} href="${ror}" rel="sameAs noopener noreferrer" title="ROR ${ror}">${ICON_ROR}<span property="name">${escapeHtml(aff.name ?? "")}</span></a>`;
    } else if (aff.qid) {
      const qid = escapeHtml(aff.qid);
      inner = `<a${cls} href="https://www.wikidata.org/wiki/${qid}" rel="sameAs noopener noreferrer" title="Wikidata ${qid}"><span property="name">${escapeHtml(aff.name ?? "")}</span></a>`;
    }
    return `<span property="affiliation" typeof="Organization"${about}>${inner}</span>`;
  };

  const authorBadges = (author, leadSpace = " ") => {
    const about = author.qid ? ` about="wd:${escapeHtml(author.qid)}"` : "";
    const orcid = author.orcid
      ? `${leadSpace}<a class="author__id" href="https://orcid.org/${escapeHtml(author.orcid)}" rel="sameAs noopener noreferrer" title="ORCID ${escapeHtml(author.orcid)}">${ICON_ORCID}ORCID</a>`
      : "";
    const scholia = author.qid
      ? `${leadSpace}<a class="author__id" href="https://qlever.scholia.wiki/author/${escapeHtml(author.qid)}" rel="sameAs noopener noreferrer" title="Scholia ${escapeHtml(author.qid)}">${ICON_SCHOLIA}Scholia</a>`
      : "";
    return { about, orcid, scholia };
  };

  eleventyConfig.addShortcode("authorList", (authors, mode = "article") => {
    if (!authors?.length) return "";
    if (mode === "article") {
      const items = authors
        .map((author, idx) => {
          const { about, orcid, scholia } = authorBadges(author);
          const corr = author.corresponding
            ? '<abbr class="mark" title="Corresponding author">†</abbr>'
            : "";
          const eq = author.equalContributor
            ? '<abbr class="mark" title="Equal contribution">*</abbr>'
            : "";
          const affs = author.affiliationIds?.length
            ? `<span class="author__affiliation">${author.affiliationIds.map((id) => renderAffiliationSpan(id)).join("; ")}</span>`
            : "";
          return `<li class="author" property="author" typeof="Person"${about}><span class="author__name"><span aria-hidden="true">${idx + 1}. </span><span property="name">${escapeHtml(author.name)}</span>${corr}${eq}${orcid}${scholia}</span>${affs}</li>`;
        })
        .join("");
      return `<div class="article__authors"><h2 class="article__subheading">Authors</h2><ol class="author-list">${items}</ol></div>`;
    }
    if (mode === "post") {
      const items = authors
        .map((author) => {
          const { about, orcid, scholia } = authorBadges(author);
          const affs = author.affiliationIds?.length
            ? ` ${author.affiliationIds.map((id) => renderAffiliationSpan(id, "author__affiliation")).join("; ")}`
            : "";
          return `<span property="author" rel="author" typeof="Person"${about}><span class="author__name" property="name">${escapeHtml(author.name)}</span>${orcid}${scholia}${affs}</span>`;
        })
        .join(", ");
      return `<span class="post-header__authors">${items}</span>`;
    }
    const items = authors
      .map((author) => {
        const { about, orcid, scholia } = authorBadges(author, "");
        const affs = author.affiliationIds?.length
          ? `<span class="event-detail__affiliations">${author.affiliationIds.map((id) => renderAffiliationSpan(id)).join("; ")}</span>`
          : "";
        return `<p class="event-detail__author" property="${escapeHtml(mode)}" typeof="Person"${about}><span property="name">${escapeHtml(author.name)}</span>${orcid}${scholia}${affs}</p>`;
      })
      .join("");
    return `<div class="event-detail__authors">${items}</div>`;
  });

  eleventyConfig.addFilter("artwork", (url) =>
    url ? (artworkManifest[url] ?? url) : "",
  );
  eleventyConfig.addFilter("artworkThumb", (url) =>
    url ? (artworkThumbnails[url] ?? artworkManifest[url] ?? url) : "",
  );
  eleventyConfig.addFilter("artworkSize", (url) => {
    const resolved =
      artworkManifest[url] ?? artworkThumbnails[url] ?? String(url ?? "");
    const name = resolved.split("/").pop();
    return artworkSizes[name] ?? { width: 576, height: 576 };
  });

  return {
    dir: {
      input: "src/eleventy",
      output: "_eleventy_site",
      includes: "_includes",
      data: "_data",
    },
    templateFormats: ["njk", "md", "11ty.js"],
    markdownTemplateEngine: "njk",
    htmlTemplateEngine: "njk",
    pathPrefix: "/",
  };
}
