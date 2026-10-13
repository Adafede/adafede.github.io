const SITE = {
  author: 'Adriano Rutz',
  // The description is the one from _quarto.yml, which is what the published
  // feed has always carried: an en dash and "specialising", not the em dash and
  // spelling the Eleventy site data uses. A feed that has resolved for years
  // should not change its description under a new generator.
  description:
    'Personal website of Adriano Rutz - Swiss Pharmaceutical Scientist specializing in metabolomics, mass spectrometry, and natural products research.',
};

/** An ISO 8601 date with a numeric offset, e.g. `2026-01-20T00:00:00+00:00`.
 *
 * `toISOString()` yields `2026-01-20T00:00:00.000Z`, which is a different string
 * from what the Quarto feed published. The format here is the same one the old
 * feed carried, down to the `+00:00` offset rather than a `Z`.
 */
function isoOffset(date) {
  const d = new Date(date);
  if (Number.isNaN(d.valueOf())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}T${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}+00:00`;
}

/**
 * A JSON Feed 1.1 document for the posts, serialised.
 *
 * Quarto published posts.json and the address has been live for years, so it has
 * to keep resolving whether or not anything here reads it. Built in JS rather
 * than assembled in a template: a feed is JSON, and hand-building JSON in a
 * template is how you end up with an unescaped quote in a title.
 *
 * `renderBody` is passed in rather than imported, so this stays a pure function
 * of its arguments and the Markdown pipeline stays in eleventy.config.mjs.
 *
 * The fields below that are not part of the JSON Feed spec are the ones Quarto's
 * feed carried and its readers parse: `_references` (the DOIs a post cites,
 * each with its CiTO predicates), `_doi`, `image`, and `attachments`. They are
 * kept under underscore keys so spec-compliant readers ignore them.
 */
export function buildJsonFeed(posts, { url, renderBody }) {
  const base = url.replace(/\/[^/]*$/, '');
  const feed = {
    version: 'https://jsonfeed.org/version/1.1',
    title: SITE.author,
    description: SITE.description,
    home_page_url: url,
    feed_url: `${base}/posts.json`,
    language: 'en',
    items: posts.map((post) => {
      const link = `${base}${post.url}`;
      const body = renderBody(post);
      const item = {
        title: post.data.title,
        url: link,
        // JSON Feed wants a stable, globally unique id. The DOI is exactly
        // that, and every post here has one; the URL is the fallback.
        id: post.data.doi ? `https://doi.org/${post.data.doi}` : link,
        content_html: body.html,
        // Quarto's feed carried the first paragraph as the summary, not the
        // truncated meta description. The page's description is a page
        // concern; the feed's summary is the opening prose.
        summary: body.firstParagraph,
        date_published: isoOffset(post.data.pubDate),
        date_modified: isoOffset(post.data.updatedDate || post.data.pubDate),
        tags: post.data.tags ?? [],
        authors: (post.data.authors ?? []).map((author) => ({
          name: author.name,
          ...(author.qid ? { url: `https://www.wikidata.org/wiki/${author.qid}` } : {}),
        })),
      };
      if (post.data.doi) item._doi = post.data.doi;
      // Quarto's machine-readable citation list, under the same key its readers
      // and tooling already parse. Each entry carries the CiTO predicates the
      // post applies to that paper.
      if (body.references.length) item._references = body.references;
      // The first figure, as the feed's preview image. Quarto published the
      // source path of the first image; the body now carries the optimised
      // WebP, so the original format is restored here.
      if (body.image) {
        item.image = body.image.replace(/\.webp$/i, '.png').startsWith('/')
          ? `https://adafede.github.io${body.image.replace(/\.webp$/i, '.png')}`
          : body.image.replace(/\.webp$/i, '.png');
      }
      if (post.data.pdf) {
        item.attachments = [
          { url: `${base}${post.data.pdf}`, mime_type: 'application/pdf' },
        ];
      }
      return item;
    }),
  };
  return JSON.stringify(feed, null, 2);
}
