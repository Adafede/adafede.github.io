/**
 * Loads the generated Markdown/JSON from src/content/, which
 * scripts/site/migrate_posts.py writes from the Quarto sources. Both builds read
 * the same .qmd tree, so they render the same content; this file is the only
 * place the Eleventy build trusts that generated content, and it normalises the
 * shapes the templates rely on.
 */
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join, basename, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { load, JSON_SCHEMA } from 'js-yaml';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTENT = join(HERE, '..', '..', 'content');

/** Split a `---\n...\n---\n` frontmatter block off a Markdown file. */
function parseDoc(raw) {
  if (!raw.startsWith('---')) return { data: {}, body: raw };
  const close = raw.indexOf('\n---', 3);
  // An unterminated block is not frontmatter: without this the closing `---`
  // is searched for in the body as well, so a stray horizontal rule half way
  // down the document silently becomes the end of the frontmatter and the
  // YAML above it is handed to the parser as a document.
  if (close === -1) return { data: {}, body: raw };
  const head = raw.slice(4, close);
  const body = raw.slice(close + 4);
  return { data: load(head, { schema: JSON_SCHEMA }) ?? {}, body };
}

/**
 * The `.md` files in a directory, sorted.
 *
 * Sorted because readdir order is whatever the filesystem hands back, and a
 * collection whose order depends on that is not reproducible across machines.
 */
function readDir(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir).filter((f) => f.endsWith('.md')).sort();
}

function loadCollection(dir, extra = () => ({})) {
  const full = join(CONTENT, dir);
  return readDir(full).map((file) => {
    const raw = readFileSync(join(full, file), 'utf-8');
    const { data, body } = parseDoc(raw);
    const id = basename(file, '.md');
    return { id, url: '', data: { ...data, ...extra(data) }, body, inputPath: join(full, file) };
  });
}


function readJson(name, fallback) {
  const p = join(CONTENT, name);
  return existsSync(p) ? JSON.parse(readFileSync(p, 'utf-8')) : fallback;
}

const subdirs = (dir) =>
  readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name));

/** Nested groups, e.g. articles/first/*.md. */
function loadNested(dir) {
  const base = join(CONTENT, dir);
  if (!existsSync(base)) return [];
  const out = [];
  for (const group of subdirs(base)) {
    if (!group.isDirectory()) continue;
    for (const file of readDir(join(base, group.name))) {
      const raw = readFileSync(join(base, group.name, file), 'utf-8');
      const { data, body } = parseDoc(raw);
      const stem = basename(file, '.md');
      // A group holding a single file named after itself is one document, not
      // a listing: articles/thesis/thesis.md is the doctoral thesis, which
      // Quarto publishes at articles/thesis.html. Publishing it at
      // articles/thesis/thesis.html would put the two builds at different URLs,
      // and the URL is what has to stay put.
      const only = readDir(join(base, group.name)).length === 1 && stem === group.name;
      out.push({
        id: only ? group.name : `${group.name}/${stem}`,
        url: only ? `/articles/${group.name}.html` : `/articles/${group.name}/${stem}.html`,
        data,
        body,
      });
    }
  }
  return out;
}

/**
 * Meta description derived from the opening prose.
 *
 * The posts carry no `description` field; one is computed from the body at
 * render time. Eleventy's eleventyComputed passes the body through a template
 * string, which escapes it, so deriving the summary here — where the Markdown
 * is still plain — is both simpler and more accurate.
 */
function summaryFrom(body) {
  const text = String(body ?? '')
    .replace(/```[\s\S]*?```/g, ' ')            // code fences
    .replace(/\[@[^\]]+\]/g, '')               // citations
    .replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/g, '') // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')  // links
    .replace(/<[^>]+>/g, ' ')                     // inline RDFa anchors
    .replace(/^#+\s+.*$/gm, ' ')                  // headings
    .replace(/\s+/g, ' ')
    .trim();
  // Break at a word, never mid-word: a description cut through the middle of a
  // word reads as a rendering fault rather than as an ellipsis.
  if (text.length <= 175) return text;
  const clipped = text.slice(0, 175);
  const lastSpace = clipped.lastIndexOf(' ');
  const cut = lastSpace > 100 ? clipped.slice(0, lastSpace) : clipped;
  return `${cut.replace(/[\s,;:.—-]+$/, '')}…`;
}

const byPubDateDesc = (a, b) => new Date(b.data.pubDate) - new Date(a.data.pubDate);
const byDateDesc = (a, b) => new Date(b.data.date) - new Date(a.data.date);

export default function buildData() {
  return {
    posts: () =>
      loadCollection('posts', (d) => ({ pubDate: new Date(d.pubDate) }))
        .map((p) => ({
          ...p,
          url: `/posts/${p.id}.html`,
          data: { ...p.data, description: p.data.description || summaryFrom(p.body) },
        }))
        .sort(byPubDateDesc),

    articles: () => loadNested('articles').sort(byDateDesc),
    // Talks and teaching each get their own page; the listing links to them.
    talks: () =>
      loadCollection('talks')
        .map((t) => ({ ...t, url: `/talks/${t.id}.html` }))
        .sort(byDateDesc),
    teaching: () =>
      loadCollection('teaching')
        .map((t) => ({ ...t, url: `/teaching/${t.id}.html` }))
        .sort(byDateDesc),
    varia: () => {
      const base = join(CONTENT, 'varia');
      if (!existsSync(base)) return [];
      const out = [];
      for (const group of subdirs(base)) {
        if (!group.isDirectory()) continue;
        for (const file of readDir(join(base, group.name))) {
          const raw = readFileSync(join(base, group.name, file), 'utf-8');
          const { data, body } = parseDoc(raw);
          const id = `${group.name}/${basename(file, '.md')}`;
          out.push({ id, url: `/varia/${id}.html`, data, body });
        }
      }
      return out;
    },

    affiliations: () => readJson('affiliations.json', []),
    profiles: () => readJson('profiles.json', {}),

    cv: () => ({
      bio: existsSync(join(CONTENT, 'cv/bio.md'))
        ? parseDoc(readFileSync(join(CONTENT, 'cv/bio.md'), 'utf-8')).body
        : '',
      experience: readJson('cv/experience.json', { label: '', entries: [] }),
      education: readJson('cv/education.json', { label: '', entries: [] }),
      awards: readJson('cv/awards.json', { label: '', entries: [] }),
      sports: readJson('cv/sports.json', { label: '', entries: [] }),
      meta: readJson('cv/meta.json', { profession: '', footer: {}, meta: [] }),
    }),
  };
}
