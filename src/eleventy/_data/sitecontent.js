/**
 * Loads the generated Markdown/JSON from src/content/, which
 * scripts/site/migrate_posts.py writes from the Quarto sources. Both builds read
 * the same .qmd tree, so they render the same content; this file is the only
 * place the Eleventy build trusts that generated content, and it normalises the
 * shapes the templates rely on.
 */
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { join, basename, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseFrontmatter, truncateAtWord } from "../../lib/frontmatter.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTENT = join(HERE, "..", "..", "content");

/**
 * The `.md` files in a directory, sorted.
 *
 * Sorted because readdir order is whatever the filesystem hands back, and a
 * collection whose order depends on that is not reproducible across machines.
 */
function readDir(dir) {
  if (!existsSync(dir)) return [];
  return readdirSync(dir)
    .filter((f) => f.endsWith(".md"))
    .sort();
}

function loadCollection(dir, extra = () => ({})) {
  const full = join(CONTENT, dir);
  return readDir(full).map((file) => {
    const raw = readFileSync(join(full, file), "utf-8");
    const { data, body } = parseFrontmatter(raw);
    const id = basename(file, ".md");
    return {
      id,
      url: "",
      data: { ...data, ...extra(data) },
      body,
      inputPath: join(full, file),
    };
  });
}

function readJson(name, fallback) {
  const p = join(CONTENT, name);
  return existsSync(p) ? JSON.parse(readFileSync(p, "utf-8")) : fallback;
}

const subdirs = (dir) =>
  readdirSync(dir, { withFileTypes: true }).sort((a, b) =>
    a.name.localeCompare(b.name),
  );

/** Nested groups, e.g. articles/first/*.md. */
function loadNested(dir) {
  const base = join(CONTENT, dir);
  if (!existsSync(base)) return [];
  const out = [];
  for (const group of subdirs(base)) {
    if (!group.isDirectory()) continue;
    const files = readDir(join(base, group.name));
    for (const file of files) {
      const raw = readFileSync(join(base, group.name, file), "utf-8");
      const { data, body } = parseFrontmatter(raw);
      const stem = basename(file, ".md");
      // A group holding a single file named after itself is one document, not
      // a listing: articles/thesis/thesis.md is the doctoral thesis, which
      // Quarto publishes at articles/thesis.html. Publishing it at
      // articles/thesis/thesis.html would put the two builds at different URLs,
      // and the URL is what has to stay put.
      const only = files.length === 1 && stem === group.name;
      out.push({
        id: only ? group.name : `${group.name}/${stem}`,
        url: only
          ? `/articles/${group.name}.html`
          : `/articles/${group.name}/${stem}.html`,
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
export function summaryFrom(body) {
  const text = String(body ?? "")
    .replace(/```[\s\S]*?```/g, " ") // code fences
    .replace(/\[@[^\]]+\]/g, "") // citations
    .replace(/\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)/g, "") // linked images
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "") // images
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1") // links
    .replace(/<[^>]+>/g, " ") // inline RDFa anchors
    .replace(/^#+\s+.*$/gm, " ") // headings
    .replace(/\s+/g, " ")
    .trim();
  return truncateAtWord(text, 175);
}

const byPubDateDesc = (a, b) =>
  new Date(b.data.pubDate) - new Date(a.data.pubDate);
const byDateDesc = (a, b) => new Date(b.data.date) - new Date(a.data.date);

/** A dated listing collection (talks, teaching): flat directory, one page each. */
function loadEvents(dir) {
  return loadCollection(dir)
    .map((item) => ({ ...item, url: `/${dir}/${item.id}.html` }))
    .sort(byDateDesc);
}

let singleton;

export function resetSiteContent() {
  singleton = undefined;
}

export default function buildData() {
  if (singleton) return singleton;
  const memo = (fn) => {
    let cached;
    return () => (cached ??= fn());
  };
  singleton = {
    posts: memo(() =>
      loadCollection("posts", (d) => ({ pubDate: new Date(d.pubDate) }))
        .map((p) => ({
          ...p,
          url: `/posts/${p.id}.html`,
          data: {
            ...p.data,
            description: p.data.description || summaryFrom(p.body),
          },
        }))
        .sort(byPubDateDesc),
    ),

    articles: memo(() => loadNested("articles").sort(byDateDesc)),
    // Talks and teaching each get their own page; the listing links to them.
    talks: memo(() => loadEvents("talks")),
    teaching: memo(() => loadEvents("teaching")),
    varia: memo(() => {
      const base = join(CONTENT, "varia");
      if (!existsSync(base)) return [];
      const out = [];
      for (const group of subdirs(base)) {
        if (!group.isDirectory()) continue;
        for (const file of readDir(join(base, group.name))) {
          const raw = readFileSync(join(base, group.name, file), "utf-8");
          const { data, body } = parseFrontmatter(raw);
          const id = `${group.name}/${basename(file, ".md")}`;
          out.push({ id, url: `/varia/${id}.html`, data, body });
        }
      }
      return out;
    }),

    affiliations: memo(() => readJson("affiliations.json", [])),
    profiles: memo(() => readJson("profiles.json", {})),

    cv: memo(() => ({
      bio: existsSync(join(CONTENT, "cv/bio.md"))
        ? parseFrontmatter(readFileSync(join(CONTENT, "cv/bio.md"), "utf-8")).body
        : "",
      experience: readJson("cv/experience.json", { label: "", entries: [] }),
      education: readJson("cv/education.json", { label: "", entries: [] }),
      awards: readJson("cv/awards.json", { label: "", entries: [] }),
      sports: readJson("cv/sports.json", { label: "", entries: [] }),
      meta: readJson("cv/meta.json", { profession: "", footer: {}, meta: [] }),
    })),
  };
  return singleton;
}
