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
import { EleventyHtmlBasePlugin } from '@11ty/eleventy';
import markdownIt from 'markdown-it';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseBib, renderReference, inlineCitation, parseAuthors, detex } from './src/lib/bib.mjs';
import siteContent from './src/eleventy/_data/sitecontent.js';
import { buildJsonFeed } from './src/lib/jsonFeed.mjs';

const ROOT = dirname(fileURLToPath(import.meta.url));

const BIB = readFileSync(fileURLToPath(new URL('./posts/references.bib', import.meta.url)), 'utf-8');
const bib = parseBib(BIB);

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
];

/**
 * CiTO predicates are snake_case in the post sources (`[@cites_as_data:key]`)
 * and camelCase in the rendered `[cito:…]` spans, which is what Quarto's
 * filters/extract-cito.lua produced.
 */
const CITO_CANONICAL = {
  cites: 'cites',
  cites_as_recommended_reading: 'citesAsRecommendedReading',
  cites_as_data_source: 'citesAsDataSource',
  cites_as_motivational_work: 'citesAsMotivationalWork',
  uses_method_in: 'usesMethodIn',
  uses_dataset: 'usesDataset',
  obtains_background_from: 'obtainsBackgroundFrom',
  is_supplemented_by: 'isSupplementedBy',
  is_supplement_to: 'isSupplementTo',
  is_continued_by: 'isContinuedBy',
  agrees_with: 'agreesWith',
  disagrees_with: 'disagreesWith',
  has_version: 'hasVersion',
  concludes: 'concludes',
  criticizes: 'criticizes',
  documents: 'documents',
  discusses: 'discusses',
  mentions: 'mentions',
  refutes: 'refutes',
  replicates: 'replicates',
  retracts: 'retracts',
  reviews: 'reviews',
  corrects: 'corrects',
  disputes: 'disputes',
  extends: 'extends',
  updates: 'updates',
  continues: 'continues',
  forks: 'forks',
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
  const first = names[0] ?? 'Adriano Rutz';
  const family = first.trim().split(/\s+/).pop().toLowerCase();

  return {
    key: `${family}${date.getUTCFullYear()}`,
    type: 'article',
    fields: {
      author: names.join(' and '),
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
    const author = parseAuthors(entry.fields.author ?? '').join(';');
    const year = detex(entry.fields.year ?? '');
    if (!author || !year) continue;
    const group = `${author}|${year}`;
    groups.set(group, [...(groups.get(group) ?? []), key]);
  }
  const letters = 'abcdefghijklmnopqrstuvwxyz';
  for (const [, group] of groups) {
    if (group.length < 2) continue;
    const ordered = [...group].sort((a, b) =>
      detex(entries.get(a)?.fields.title ?? '').localeCompare(
        detex(entries.get(b)?.fields.title ?? ''),
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
  const text = String(value ?? '').trim() || new Date().toISOString();
  // A bare ISO date has to be pinned to UTC or it parses as local midnight and
  // can shift a day either side of the date boundary.
  if (/^\d{4}-\d{2}$/.test(text)) return new Date(`${text}-01T00:00:00Z`);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return new Date(`${text}T00:00:00Z`);
  const d = new Date(text);
  return d;
};

/**
 * Truncate to `limit` characters, but never mid-word.
 *
 * Cutting at a fixed index reads as a rendering bug rather than as an
 * ellipsis: "…that fits are one that ge…" is the kind of thing a reader
 * notices and trusts less. Break at the last space before the limit and keep
 * the word whole.
 */
function truncateAtWord(text, limit) {
  const value = String(text ?? '').trim();
  if (value.length <= limit) return value;
  const clipped = value.slice(0, limit);
  const lastSpace = clipped.lastIndexOf(' ');
  const cut = lastSpace > limit * 0.6 ? clipped.slice(0, lastSpace) : clipped;
  return `${cut.replace(/[\s,;:.—-]+$/, '')}…`;
}

const md = markdownIt({ html: true, linkify: false, typographer: false });

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
const TAB_LABELS = { en: 'English', fr: 'Français', de: 'Deutsch', it: 'Italiano' };

md.block.ruler.before('fence', 'panel_tabset', (state, startLine, endLine, silent) => {
  const start = state.bMarks[startLine] + state.tShift[startLine];
  const max = state.eMarks[startLine];
  if (state.src.slice(start, max).trim() !== '::: {.panel-tabset}') return false;
  if (silent) return true;

  // Collect until the closing fence.
  let nextLine = startLine;
  while (nextLine + 1 < endLine) {
    nextLine++;
    const from = state.bMarks[nextLine] + state.tShift[nextLine];
    const to = state.eMarks[nextLine];
    if (state.src.slice(from, to).trim() === ':::') break;
  }
  if (nextLine >= endLine) return false;

  // Split the block at its `### Label` headings; each becomes one tab.
  const lines = [];
  for (let i = startLine + 1; i < nextLine; i++) {
    const from = state.bMarks[i] + state.tShift[i];
    const to = state.eMarks[i];
    lines.push(state.src.slice(from, to));
  }

  const panels = [];
  let current = null;
  for (const line of lines) {
    const heading = /^###\s+(.+?)\s*$/.exec(line);
    if (heading) {
      current = { label: heading[1].trim(), lines: [] };
      panels.push(current);
    } else if (current) {
      current.lines.push(line);
    }
  }
  if (panels.length === 0) return false;

  const slug = (label) =>
    label.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'panel';

  const html = [];
  html.push('<div class="tabset">');
  // The radios live inside the fieldset, with the labels and the legend, because
  // that is what a fieldset is for: it groups a set of related controls. An
  // earlier version had to keep the radios outside it so a sibling combinator
  // could reach the panels, which left a fieldset grouping nothing but labels —
  // malformed, and WAVE reported exactly that.
  //
  // :has() on the container is what lets the controls go back inside. It is
  // used here rather than nth-of-type because the minifier rewrites those and
  // the rewritten rules stopped matching anything.
  html.push('<fieldset class="tabset__tabs">');
  html.push('<legend class="tabset__legend">Language</legend>');
  panels.forEach((panel, index) => {
    const id = slug(panel.label);
    html.push(
      `<input class="tabset__radio tabset__radio--${index + 1}" type="radio" name="tabset-${startLine}" id="tabset-${startLine}-${id}"${index === 0 ? ' checked' : ''}>`,
    );
    // The label sits immediately after its radio, which is also how the focus
    // ring below finds it.
    html.push(
      `<label class="tabset__tab tabset__tab--${index + 1}" for="tabset-${startLine}-${id}"${/^[a-z]{2}$/i.test(panel.label) ? ` lang="${escapeHtml(panel.label)}"` : ''}>${escapeHtml(panel.label)}</label>`,
    );
  });
  html.push('</fieldset>');
  html.push('<div class="tabset__panels">');
  for (const panel of panels) {
    // No heading inside the panel: the tab above it already says which language
    // this is, and a second copy as a heading made the document outline read as
    // though the abstract had four headings in it.
    html.push('<section class="tabset__panel tabset__panel--' + (panels.indexOf(panel) + 1) + '">');
    html.push(md.render(panel.lines.join('\n')));
    html.push('</section>');
  }
  html.push('</div>');
  html.push('</div>');

  state.line = nextLine + 1;
  const token = state.push('html_block', '', 0);
  token.content = html.join('\n');
  token.block = true;
  return true;
});

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// --- citations -------------------------------------------------------------

md.inline.ruler.before('html_inline', 'cito_citation', (state, silent) => {
  const src = state.src.slice(state.pos, state.pos + 200);
  const match = src.match(/^\[@([^\]]+)\]/);
  if (!match) return false;

  const items = match[1]
    .split(';')
    .map((part) => part.trim().replace(/^@/, ''))
    .filter(Boolean)
    .map((item) => {
      const [predicate, key] = item.includes(':') ? item.split(':') : [null, item];
      return { key: (key ?? predicate).trim(), predicate: predicate?.trim() };
    });

  if (!items.length) return false;

  if (!silent) {
    const token = state.push('cito_citation', '', 0);
    token.meta = items;
    state.env.cito ??= new Map();
    for (const item of items) {
      if (item.predicate) {
        if (!state.env.cito.has(item.key)) state.env.cito.set(item.key, new Set());
        state.env.cito.get(item.key).add(item.predicate);
      }
    }
  }

  state.pos += match[0].length;
  return true;
});

md.renderer.rules.cito_citation = (tokens, idx) => {
  const keys = [...new Set(tokens[idx].meta.map((item) => item.key))];
  const links = keys
    .map((key) => `<a href="#ref-${key}" role="doc-biblioref">${inlineCitation(bib.get(key))}</a>`)
    .join('; ');
  return `<span class="citation" data-cites="${keys.join(' ')}">(${links})</span>`;
};

md.core.ruler.push('eleventy_references', (state) => {
  const cited = state.env.cito;
  if (!cited || !cited.size) return;

  // Per-document view, so one post's self-citation cannot leak into another.
  const entries = new Map(bib);

  // A post can cite itself, so the entry is made resolvable — but it is NOT
  // added to `cited`. Putting it there made every post list itself under its own
  // References whether or not the text ever mentioned it, which is what Quarto
  // does not do and reads as a mistake. An entry in `entries` only means a
  // citation such as @rutz2026 resolves; whether it is *listed* is decided by
  // the text, like any other reference.
  const self = selfCitation(state.env.frontmatter ?? {});
  if (self) entries.set(self.key, self);

  const keys = [...cited.keys()].sort((a, b) =>
    inlineCitation(entries.get(a)).localeCompare(inlineCitation(entries.get(b))),
  );
  const suffixes = yearSuffixes(keys, entries);

  const html = keys
    .map((key) => {
      const predicates = [...(cited.get(key) ?? [])].map(citoPredicate);
      const cito = predicates.length ? `<span class="cito"> [cito:${predicates.join(',')}]</span>` : '';
      const entry = renderReference(
        entries.get(key) ?? { key, type: 'misc', fields: {} },
        suffixes.get(key) ?? '',
      );
      return `<div class="csl-entry" id="ref-${key}" role="listitem">${entry}${cito}</div>`;
    })
    .join('');

  state.env.references = html;
});

export default function (eleventyConfig) {
  eleventyConfig.addPlugin(EleventyHtmlBasePlugin);

  const content = siteContent();

  // --- assets --------------------------------------------------------
  // The design system is shared with Quarto's typography so both builds
  // cannot drift: the same file, copied to the same output path.
  // The design system is shared with Quarto's typography so both builds
  // inlines it through Vite. Eleventy has no asset pipeline, so the minified
  // copy is staged in build/eleventy/ and copied here; scripts/site/inline-css.mjs
  // then folds it into every page, which is what removes the render-blocking
  // request entirely.
  eleventyConfig.addPassthroughCopy({ 'build/eleventy/styles.css': 'styles.css' });
  eleventyConfig.addPassthroughCopy({ 'src/eleventy/static': '.' });
  eleventyConfig.addPassthroughCopy({ public: '.' });

  eleventyConfig.addWatchTarget('src/content/');

  // --- collections ---------------------------------------------------
  // Backed by _data/sitecontent.js rather than getFilteredByGlob: the
  // generated Markdown lives outside dir.input (src/eleventy), and Eleventy
  // does not traverse a symlinked directory, so a glob there returns nothing
  // and pagination over an empty collection is silently skipped.
  eleventyConfig.addCollection('posts', () => content.posts());
  eleventyConfig.addCollection('articles', () => content.articles());
  eleventyConfig.addCollection('talks', () => content.talks());
  eleventyConfig.addCollection('teaching', () => content.teaching());
  // Varia is plain data rather than a Markdown collection, so it needs a
  // collection for the per-entry pages to paginate over.
  eleventyConfig.addCollection('variaItems', () => content.varia());

  const ARTICLE_GROUPS = [
    { key: 'first', label: 'Articles as single first author', table: false },
    { key: 'shared', label: 'Articles as shared first author', table: false },
    { key: 'co', label: 'Articles as co-author', table: true },
    { key: 'thesis', label: 'Doctoral thesis', table: true },
  ];

  // `articleGroups` is a collection, not global data: each entry carries the
  // label and the `table` flag alongside its items.

  // Precomputed because Nunjucks cannot filter inside {% set %} — it is a parse
  // error, so `{% set items = list | where: ... %}` is not an option.
  eleventyConfig.addCollection('articleGroups', () => {
    const articles = content.articles();
    return ARTICLE_GROUPS.map((group) => ({
      ...group,
      items: articles
        .filter((a) => a.data.group === group.key)
        .sort((a, b) => toDate(b.data.date) - toDate(a.data.date)),
    }));
  });

  // --- global data ---------------------------------------------------
  const cv = content.cv();
  // Not named `cv`: Eleventy reserves that on the data cascade.
  eleventyConfig.addGlobalData('curriculum', cv);
  eleventyConfig.addGlobalData('profiles', content.profiles());
  eleventyConfig.addGlobalData('affiliations', content.affiliations());
  eleventyConfig.addGlobalData('varia', content.varia());

  // Quarto published /posts.json and /listings.json. Nothing in this build
  // reads them, but both addresses are live and a feed that stops resolving is
  // a silent outage for every reader who already subscribed to it.
  eleventyConfig.addGlobalData('postsJsonFeed', () =>
    buildJsonFeed(content.posts(), {
      url: 'https://adafede.github.io/posts.html',
      // The same renderer the pages use, so the feed's content_html carries the
      // bibliography and CiTO annotations the post page shows.
      renderBody: (post) => renderBody(post.body, post.data),
    }),
  );

  /**
   * The topics the work clusters around, with a count each, across articles
   * and posts. Powers the home page's topics section. Precomputed because
   * Nunjucks cannot sort or aggregate inside {% set %}.
   *
   * The listing pages already carry a working topic filter; this is the same
   * data as a set of entry points, so a visitor can arrive at the work from a
   * subject rather than only from a page type.
   */
  eleventyConfig.addGlobalData('topicCounts', () => {
    const counts = new Map();
    for (const item of [...content.articles(), ...content.posts()]) {
      for (const tag of item.data?.tags ?? []) {
        counts.set(tag, (counts.get(tag) ?? 0) + 1);
      }
    }
    return [...counts.entries()]
      .map(([tag, count]) => ({ tag, count }))
      .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag));
  });

  // --- filters -------------------------------------------------------
  eleventyConfig.setLibrary('md', md);

  /**
   * Renders a single line of Markdown as inline HTML.
   *
   * Used for abstracts and summaries, which are prose that happens to arrive as
   * one string: they need `*Swertia chirayita*` to come out italic and a bare
   * DOI or URL to become a link, but they are not block content and must not
   * gain a wrapping <p>. `html: false` escapes any raw HTML that came in with
   * the content, and `linkify` turns bare URLs into links.
   */
  const inlineMd = markdownIt({ html: false, linkify: true, typographer: false });

  /**
   * Link text that tells a screen-reader user nothing on its own.
   *
   * The Quarto sources use "here" and "link" as link text, which is fine
   * visually — the surrounding sentence gives the context — but read out of
   * context it is just the word "here". Rather than rewrite the author's
   * sentences, each such link gets a visually hidden descriptor of where it
   * goes, so the accessible name carries the same information the reader gets
   * from the sentence around it.
   */
  const GENERIC_LINK_TEXT = /^\s*(here|link|this|read more|more)\s*$/i;
  const describeTarget = (href) => {
    let path = '';
    try {
      path = new URL(href, 'https://adafede.github.io').pathname;
    } catch {
      path = href;
    }
    if (/\.pdf$/i.test(path)) return 'PDF';
    if (path === '/' || path.endsWith('/')) return 'home page';
    return 'external page';
  };

  /** The text of a fragment of HTML, tags out. */
  function stripTags(html) {
    return String(html ?? '')
      .replace(/<[^>]+>/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }

  /**
   * The text of a fragment of HTML, tags removed without adding spaces.
   *
   * `stripTags` inserts a space for every tag, which is right for sentences but
   * wrong for inline runs like `<span>(<a>…</a>)</span>`, where it would open a
   * gap inside the parentheses. This one concatenates the text nodes as-is.
   */
  function htmlText(html) {
    return String(html ?? '')
      .replace(/<[^>]+>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  /** The text of the first paragraph of a rendered body, or ''. */
  function firstParagraphText(html) {
    const m = String(html ?? '').match(/<p[^>]*>([\s\S]*?)<\/p>/i);
    return m ? htmlText(m[1]) : '';
  }

  /** The `src` of the first image in a rendered body, or ''. */
  function firstImageSrc(html) {
    const m = String(html ?? '').match(/<img\b[^>]*?\bsrc="([^"]+)"/i);
    return m ? m[1] : '';
  }

  /**
   * Open links to PDFs in a new tab, and say so.
   *
   * A PDF replaces the page, so a reader who followed "slides" from a talk
   * description loses their place and has to find their way back. WAVE flags
   * these for the same reason. `rel="noopener"` comes along because the target
   * is external, and the file type is announced rather than left to be guessed.
   */
  function markPdfLinks(html) {
    return String(html ?? '').replace(
      /<a\b([^>]*?)href="([^"]*\.pdf(?:#[^"]*)?)"([^>]*)>([\s\S]*?)<\/a>/gi,
      (match, before, href, after, text) => {
        const attrs =
          /target=/.test(match)
            ? `${before}href="${href}"${after}`
            : `${before}href="${href}"${after} target="_blank" rel="noopener"`;

        // WAVE flags a PDF link whose text does not say it is a PDF, and the
        // flag is fair: the file type is the one thing a reader cannot guess
        // from the destination, and an icon alone does not reach a screen
        // reader at all.
        //
        // Real text, added at build time rather than by a CSS ::after, for two
        // reasons. It is in the accessibility tree and in the accessible name,
        // and it survives the styling being changed or the CSS not loading.
        // A pseudo-element gives you neither guarantee.
        //
        // Only appended when the link text does not already say PDF, so the
        // links that are already explicit are left exactly as written.
        const saysPdf = /\bpdf\b/i.test(stripTags(text));
        // The leading space is in the text, not only in CSS: copied and pasted
        // link text should still read as two words.
        const label = saysPdf ? '' : '<span class="link-format"> (PDF)</span>';

        return `<a${attrs}>${text}${label}</a>`;
      },
    );
  }

  eleventyConfig.addFilter('inlineMarkdown', (value) => {
    if (!value) return '';
    return markPdfLinks(
      inlineMd
      .renderInline(String(value))
      .replace(
        /<a href="([^"]+)">([^<]*)<\/a>/g,
        (match, href, text) =>
          GENERIC_LINK_TEXT.test(text)
            ? `<a href="${href}">${text}<span class="visually-hidden"> (${describeTarget(href)})</span></a>`
            : match,
      ),
    );
  });

  /**
   * Renders the Markdown body.
   *
   * Nunjucks has no component slot, so post and article bodies are rendered
   * here and injected with | safe. The reference list is appended after the
   * "References" heading, which is where Quarto inserts it in
   * the mdast tree.
   */
  /**
   * Renders a Markdown body, reference list included.
   *
   * Shared by the page templates and the JSON feed. Quarto's feed carries the
   * rendered bibliography inside content_html and a machine-readable
   * `_references` list beside it, and for the two to agree the feed has to go
   * through the same renderer as the page — not a raw md.render() that quietly
   * drops the references the citations point at.
   */
  function renderBody(body, frontmatter = {}) {
    if (!body) return { html: '', references: [] };
    const env = { frontmatter };
    let html = markPdfLinks(md.render(body, env));

    if (env.references) {
      const block = `<div class="references csl-bib-body hanging-indent" id="refs" role="list">${env.references}</div>`;
      html = /<h2[^>]*id="references"[^>]*>/i.test(html)
        ? html.replace(/(<h2[^>]*id="references"[^>]*>[\s\S]*?<\/h2>)/i, `$1\n${block}`)
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
    const bibliography = env.references || '';
    const ownDoi = String(frontmatter.doi || '').toLowerCase();
    const entryRe = /<div class="csl-entry"[^>]*>([\s\S]*?)<\/div>/g;
    for (const match of bibliography.matchAll(entryRe)) {
      const entry = match[1];
      const doiMatch = entry.match(/https?:\/\/(?:dx\.)?doi\.org\/([^\s"'<)]+)/i);
      if (!doiMatch) continue;
      const doi = doiMatch[1].replace(/[.,;]$/, '');
      // A post that lists itself among its own references is not a reference.
      // Quarto drops the self-citation here, and a feed that reports one back to
      // the reader as "this post cites this post" reads as a bug.
      if (doi.toLowerCase() === ownDoi) continue;
      if (references.some((r) => r.doi === doi)) continue;
      const ref = { url: `https://doi.org/${doi}`, doi };
      const cito = [];
      for (const c of entry.matchAll(/\[cito:([^\]]+)\]/g)) {
        for (const p of c[1].split(',')) {
          const t = p.trim();
          if (t && !cito.includes(t)) cito.push(t);
        }
      }
      if (cito.length) ref.cito = cito;
      references.push(ref);
    }

    return {
      html,
      references,
      // The first paragraph, tags out. The Quarto feed used the first paragraph
      // as the item summary; the truncated page meta description is a page
      // concern, not a feed one, so the feed gets the whole paragraph.
      firstParagraph: firstParagraphText(html),
      // The first figure's source, absolutized by the feed builder.
      image: firstImageSrc(html),
    };
  }

  eleventyConfig.addFilter('renderMarkdown', (body, frontmatter = {}) =>
    renderBody(body, frontmatter).html,
  );
  /** The first paragraph of a rendered body as plain text, for feed summaries. */
  eleventyConfig.addFilter('firstParagraph', (body, frontmatter = {}) =>
    renderBody(body, frontmatter).firstParagraph,
  );

  /**
   * The first `count` items of an array.
   *
   * A missing count means "all of them", so feeds that have no cap do not have
   * to carry a `limit` just to be sliced.
   */
  /**
   * The newest of the first matching field on each item, as a Date or null.
   *
   * Written as a filter taking field names rather than a function because the
   * call site is a Nunjucks template, which cannot pass a callback. Fields are
   * tried in order, so `latestOf(posts, 'updatedDate', 'pubDate')` prefers a
   * post's own modification date and falls back to its publication date.
   */
  eleventyConfig.addFilter('latestPostDate', (posts) => {
    let newest = null;
    for (const post of posts) {
      const date = new Date(post.data.updatedDate || post.data.pubDate);
      if (!Number.isNaN(date.valueOf()) && (!newest || date > newest)) newest = date;
    }
    return newest;
  });

  eleventyConfig.addFilter('latestOf', (items, ...keys) => {
    let newest = null;
    for (const item of items) {
      const value = keys.map((key) => item?.[key]).find((v) => v);
      const date = value instanceof Date ? value : new Date(value);
      if (!Number.isNaN(date.valueOf()) && (!newest || date > newest)) newest = date;
    }
    return newest;
  });

  /**
   * The most recent date among a set of items, as a Date or null.
   *
   * `pick` extracts the date from an item. Feeds need exactly one build date
   * and it has to be the newest item in them, which is a question about the
   * whole set rather than any single item.
   */
  eleventyConfig.addFilter('latestDate', (items, pick) => {
    let newest = null;
    for (const item of items) {
      const value = pick(item);
      const date = value instanceof Date ? value : value ? new Date(value) : null;
      if (date && !Number.isNaN(date.valueOf()) && (!newest || date > newest)) newest = date;
    }
    return newest;
  });

  /**
   * A string, percent-encoded for use in a query string.
   *
   * Post titles carry spaces, colons and ampersands, all of which would
   * otherwise change the meaning of the URL they are interpolated into.
   */
  eleventyConfig.addFilter('urlencode', (value) =>
    encodeURIComponent(String(value ?? '')),
  );

  eleventyConfig.addFilter('limitCount', (items, count) =>
    count ? items.slice(0, count) : items,
  );

  eleventyConfig.addFilter('readableDate', (value) => {
    const d = toDate(value);
    return Number.isNaN(d.valueOf()) ? '' : d.toISOString().slice(0, 10);
  });
  /** `2026-02-11` -> `02-11`, for the timeline's date column. */
  eleventyConfig.addFilter('monthDay', (value) => {
    const d = toDate(value);
    // Slice the *formatted* day, not the ISO timestamp: toISOString() returns
    // `2026-02-11T00:00:00.000Z`, so .slice(5) on it yields the whole tail.
    return Number.isNaN(d.valueOf()) ? '' : d.toISOString().slice(5, 10);
  });
  eleventyConfig.addFilter('year', (value) => toDate(value).getUTCFullYear());
  eleventyConfig.addFilter('isoDate', (value) => toDate(value).toISOString());
  /** The giscus configuration, copied verbatim from the Quarto output. */
  eleventyConfig.addGlobalData('giscusConfig', {
    repo: 'adafede/adafede.github.io',
    repoId: 'R_kgDON8Npdw',
    category: 'General',
    categoryId: 'DIC_kwDON8Npd84CuC86',
    mapping: 'title',
    reactionsEnabled: '1',
    emitMetadata: '0',
    inputPosition: 'top',
    theme: 'preferred_color_scheme',
    lang: 'en',
    loading: 'lazy',
  });

  eleventyConfig.addFilter('toRfc822', (value) => new Date(toDate(value)).toUTCString());
  eleventyConfig.addFilter('stripTags', (html) => stripTags(html));
  eleventyConfig.addFilter('json', (value) => JSON.stringify(value));

  // Nunjucks has no `map`, so the operations a component would do inline are
  // provided here instead.
  eleventyConfig.addFilter('joinNames', (items) =>
    (items ?? []).map((item) => item?.name).filter(Boolean).join(', '),
  );
  eleventyConfig.addFilter('mapProp', (items, prop) =>
    (items ?? []).map((item) => item?.[prop]).filter((v) => v !== undefined),
  );
  eleventyConfig.addFilter('uniq', (values) => [...new Set(values ?? [])]);
  eleventyConfig.addFilter('sortAttr', (items, attr) =>
    [...(items ?? [])].sort((a, b) => String(a[attr] ?? '').localeCompare(String(b[attr] ?? ''))),
  );
  eleventyConfig.addFilter('sliceYears', (items) =>
    [...new Set((items ?? []).map((i) => toDate(i.data?.date ?? i).getUTCFullYear()))].sort(
      (a, b) => b - a,
    ),
  );
  /** Varia cards grouped by their subdirectory, alphabetically. */
  eleventyConfig.addFilter('groupByVaria', (cards) => {
    const groups = new Map();
    for (const card of cards) {
      const key = card.data.group;
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(card);
    }
    return [...groups.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([id, items]) => ({
        id: id.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        label: id.replace(/[-_]/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase()),
        items: items.sort((a, b) => a.data.title.localeCompare(b.data.title)),
      }));
  });

  /**
   * Nunjucks' built-in `slice` is the *string* slice and returns nothing useful
   * for an array of objects, so `collections.posts | slice(0, 3)` yields an
   * empty loop. This is the array slice the templates actually mean.
   */
  eleventyConfig.addFilter('take', (items, n) => (items ?? []).slice(0, Number(n)));

  /** Merge two collections, so a page can show posts and articles together. */
  eleventyConfig.addFilter('concat', (a, b) => [...(a ?? []), ...(b ?? [])]);

  /**
   * Every distinct tag across a collection, most-used first, with counts.
   * Precomputed because Nunjucks cannot filter inside {% set %}.
   */
  eleventyConfig.addFilter('tagCounts', (items) => {
    const counts = new Map();
    for (const item of items ?? []) {
      for (const tag of item.data?.tags ?? []) counts.set(tag, (counts.get(tag) ?? 0) + 1);
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
  eleventyConfig.addFilter('tagKey', (item) =>
    `|${(item.data?.tags ?? []).map((t) => String(t).toLowerCase()).join('|')}|`,
  );

  eleventyConfig.addFilter('minus', (value, n) => (Number(value) || 0) - (Number(n) || 0));
  eleventyConfig.addFilter('where', (items, prop, value) =>
    (items ?? []).filter(
      (item) => String(String(prop).split('.').reduce((acc, k) => acc?.[k], item)) === String(value),
    ),
  );

  /** The CV's four sections, newest first, for the section loop. */
  eleventyConfig.addFilter('cvSections', (data) =>
    [data.experience, data.education, data.awards, data.sports]
      .filter((section) => section?.entries?.length)
      .map((section) => ({
        ...section,
        id: section.label.toLowerCase().replace(/[^a-z]+/g, '-'),
        // Newest first: Quarto ordered by filename, which reads oldest-first.
        entries: [...section.entries].sort((a, b) => (b.startYear ?? 0) - (a.startYear ?? 0)),
      })),
  );

  /**
   * Meta description for an article, derived when it has no abstract.
   *
   * A filter rather than a template expression because Nunjucks reads the `?`
   * of a ternary as part of its own syntax.
   */
  /**
   * Plain text for a meta description.
   *
   * A description ends up in a content attribute, and Nunjucks escapes it on
   * the way in. An abstract that carries Markdown autolinks (`<https://…>`)
   * arrives already escaped, so it would be escaped a second time and reach the
   * crawler as `&amp;lt;https://…`. Strip the markup here, before any
   * templating touches it.
   */
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
  eleventyConfig.addFilter('obfuscateContact', (value) => {
    const ZWSP = '\u200B';
    return escapeHtml(String(value ?? ''))
      .replace(/@/g, ' [at] ')
      .replace(/\d/g, (d) => `${d}${ZWSP}`);
  });

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
  eleventyConfig.addFilter('obfuscateContact', (value) => {
    const ZWSP = '\u200B';
    return escapeHtml(String(value ?? ''))
      .replace(/@/g, ' [at] ')
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
  eleventyConfig.addFilter('schemaProperty', (label) => {
    const value = String(label ?? '').toLowerCase();
    if (/position|role|title/.test(value)) return 'jobTitle';
    if (/language/.test(value)) return 'knowsLanguage';
    if (/expertise|specials|interest|field/.test(value)) return 'knowsAbout';
    return '';
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
  eleventyConfig.addFilter('obfuscate', (value) =>
    [...String(value ?? '')].map((c) => `&#${c.codePointAt(0)};`).join(''),
  );

  /**
   * An address spelled out for reading: "rutz [at] imsb [dot] …".
   *
   * For the visible text where the address itself has to be legible. The words
   * keep it copy-pasteable by hand and screen-reader legible, while the pattern a
   * harvester matches on — one run of characters, an @, a domain — does not
   * appear.
   */
  eleventyConfig.addFilter('spellEmail', (value) =>
    String(value ?? '').replace(/@/g, ' [at] ').replace(/\./g, ' [dot] ').replace(/\s+/g, ' ').trim(),
  );

  /**
   * The first `count` words of some text, cut at a word boundary.
   *
   * For feed summaries. Cut on a word rather than a character so the last word
   * is not cut in half, and an ellipsis is added only when there was more to
   * come, so a short description is not given a full stop it did not have.
   */
  eleventyConfig.addFilter('truncateWords', (value, count) => {
    const words = String(value ?? '').trim().split(/\s+/).filter(Boolean);
    if (words.length <= count) return words.join(' ');
    return `${words.slice(0, count).join(' ')}…`;
  });

  eleventyConfig.addFilter('plainText', (value) => {
    const text = String(value ?? '')
      .replace(/<[^>]+>/g, '') // Markdown autolinks and angle brackets
      .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // links
      .replace(/[*_`]/g, '') // emphasis and code markers
      // A description is prose, not code: quotes and apostrophes carry no
      // meaning here, and keeping them means the attribute is escaped twice
      // (once by eleventyComputed, once by the content attribute) and the
      // reader sees a literal &quot;.
      .replace(/["'\u2018\u2019]/g, '')
      .replace(/\s+/g, ' ')
      .trim();
    // Roughly what a search result will show; the rest is truncated by the
    // consumer anyway, and a description that fits is one that gets read.
    return truncateAtWord(text, 300);
  });

  eleventyConfig.addFilter('orDescription', (abstract, data) => {
    if (abstract) return abstract;
    const parts = [`${data.title}.`];
    if (data.venue) parts.push(`Published in ${data.venue}.`);
    if (data.authors?.length) {
      parts.push(`Authors: ${data.authors.map((a) => a.name).join(', ')}.`);
    }
    if (data.tags?.length) parts.push(`Topics: ${data.tags.join(', ')}.`);
    return truncateAtWord(parts.join(' '), 300);
  });

  /**
   * Resolve an author's affiliation id to its record, so templates can show the
   * name and link it to the ROR entry and Wikidata item Quarto linked to.
   */
  const affiliations = new Map(content.affiliations().map((a) => [a.id, a]));
  const affiliation = (id) => affiliations.get(id) ?? {};
  eleventyConfig.addFilter('affiliation', affiliation);
  /**
   * Marks for the registries this site links out to.
   *
   * All four are the publishers' own files, under static/logos/:
   *
   *   ORCID          ORCID/ORCID-Source, static/img/id-icon.svg
   *   ROR            ror-community/ror-logos
   *   Scholia        Wikimedia Commons, Scholia_Logo_Improved.svg. Note that
   *                   file's width/height attributes disagree with its
   *                   viewBox, so it must be sized by height alone.
   *   Google Scholar Wikimedia Commons
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
    orcid: 'orcid-id.svg',
    ror: 'ror-icon-rgb-transparent.svg',
    scholia: 'scholia.svg',
    scholar: 'google-scholar.svg',
    doi: 'doi.svg',
  };

  /** Drawn marks, for the places no registry publishes an icon. */
  const DRAWN = {
    // LinkedIn's own square badge is a solid blue tile that reads louder than
    // every other mark on the page. The "in" logotype on its own is the same
    // brand shape and takes the text colour, so it sits with the rest.
    linkedin:
      '<circle cx="4.4" cy="4.6" r="2.1" fill="currentColor"/>' +
      '<path fill="currentColor" d="M2.6 8.6h3.6v12.2H2.6zM9 8.6h3.45v1.67h.05a3.78 3.78 0 0 1 3.4-1.87c3.64 0 4.31 2.4 4.31 5.52v6.88h-3.6v-6.1c0-1.46-.03-3.34-2.03-3.34-2.04 0-2.35 1.59-2.35 3.23v6.21H9z"/>',
    email:
      '<path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M3 6.5h18v11H3z"/><path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" d="M3 7l9 6.5L21 7"/>',
    github:
      '<path fill="currentColor" d="M12 2a10 10 0 0 0-3.16 19.49c.5.09.68-.22.68-.48v-1.7c-2.78.6-3.37-1.34-3.37-1.34-.45-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.61.07-.61 1 .07 1.53 1.03 1.53 1.03.89 1.53 2.34 1.09 2.91.83.09-.65.35-1.09.63-1.34-2.22-.25-4.56-1.11-4.56-4.94 0-1.09.39-1.98 1.03-2.68-.1-.25-.45-1.27.1-2.64 0 0 .84-.27 2.75 1.02a9.5 9.5 0 0 1 5 0c1.91-1.29 2.75-1.02 2.75-1.02.55 1.37.2 2.39.1 2.64.64.7 1.03 1.59 1.03 2.68 0 3.84-2.34 4.68-4.57 4.93.36.31.68.92.68 1.85v2.74c0 .27.18.58.69.48A10 10 0 0 0 12 2"/>',
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
    ror: [400, 400],
    scholia: [512, 512],
    scholar: [512, 512],
    doi: [512, 512],
  };

  eleventyConfig.addShortcode('registryIcon', (name) => {
    if (LOGO_FILES[name]) {
      const [w, h] = LOGO_SIZES[name] ?? [512, 512];
      return `<img class="registry-icon registry-icon--${name}" src="/logos/${LOGO_FILES[name]}" alt="" width="${w}" height="${h}" loading="lazy" decoding="async">`;
    }
    switch (name) {
      case 'email':
      case 'linkedin':
      case 'github':
        return `<svg class="registry-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">${DRAWN[name]}</svg>`;
      case 'pdf':
        return (
          '<svg class="registry-icon" viewBox="0 0 24 24" aria-hidden="true" focusable="false">' +
          '<path fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" d="M6 2.8h8l4 4v14.4H6z"/>' +
          '<path fill="currentColor" d="M14 2.8v4h4z"/>' +
          '<path fill="currentColor" d="M8.4 16.2h7.2v1.5H8.4z"/>' +
          '</svg>'
        );
      default:
        return '';
    }
  });
  eleventyConfig.addShortcode('affiliationName', (id) => affiliation(id).name ?? id);

  /**
   * Prefer the locally cached copy of a remote cover image.
   *
   * scripts/site/fetch-artwork.mjs mirrors the artwork into
   * public/images/artwork/ and writes the mapping. The original URL is returned
   * when the image was not cached, so the page still works if the fetch step
   * has not run or a download failed.
   */
  const artworkManifest = (() => {
    const path = join(ROOT, 'public', 'images', 'artwork', 'manifest.json');
    if (!existsSync(path)) return {};
    try {
      return JSON.parse(readFileSync(path, 'utf-8'));
    } catch {
      return {};
    }
  })();
  eleventyConfig.addFilter('artwork', (url) => (url ? artworkManifest[url] ?? url : ''));
  const artworkThumbnails = (() => {
    const path = join(ROOT, 'public', 'images', 'artwork', 'thumbnails.json');
    if (!existsSync(path)) return {};
    try {
      return JSON.parse(readFileSync(path, 'utf-8'));
    } catch {
      return {};
    }
  })();
  eleventyConfig.addFilter('artworkThumb', (url) => (
    url ? artworkThumbnails[url] ?? artworkManifest[url] ?? url : ''
  ));

  /**
   * The intrinsic size of a cached artwork file, as { width, height }.
   *
   * Read from the file by scripts/site/artwork-size.mjs rather than guessed.
   * The point is the ratio: this artwork is a wide logo, that one is a tall
   * hexagon, and putting either behind the same fixed 16:9 box is what made the
   * varia cards look like they had failed to load.
   *
   * Falls back to a shape close to square so an unmeasured file still reserves
   * space rather than collapsing the layout while it loads.
   */
  const artworkSizes = (() => {
    const path = join(ROOT, 'public', 'images', 'artwork', 'sizes.json');
    if (!existsSync(path)) return {};
    try {
      return JSON.parse(readFileSync(path, 'utf-8'));
    } catch {
      return {};
    }
  })();

  eleventyConfig.addFilter('artworkSize', (url) => {
    const name = String(url ?? '').split('/').pop();
    return artworkSizes[name] ?? { width: 576, height: 576 };
  });

  return {
    dir: {
      input: 'src/eleventy',
      output: '_eleventy_site',
      includes: '_includes',
      data: '_data',
    },
    templateFormats: ['njk', 'md', '11ty.js'],
    markdownTemplateEngine: 'njk',
    htmlTemplateEngine: 'njk',
    pathPrefix: '/',
  };
}
