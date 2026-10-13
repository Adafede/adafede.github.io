const SITE = {
  author: 'Adriano Rutz',
  description:
    'Personal website of Adriano Rutz — Swiss pharmaceutical scientist specialising in metabolomics, mass spectrometry, and natural products research.',
};

/**
 * A JSON Feed 1.1 document for the posts, serialised.
 *
 * Quarto published posts.json and the address has been live for years, so it has
 * to keep resolving whether or not anything here reads it. Built in JS rather
 * than assembled in a template: a feed is JSON, and hand-building JSON in
 * Nunjucks is how you end up with an unescaped quote in a title.
 *
 * `_references` is the Quarto feed's own extension, populated by the DOI and
 * CiTO injectors with the DOIs a post cites. It is what lets a reader go from a
 * post to the papers behind it without a second request.
 *
 * `renderBody` is passed in rather than imported, so this stays a pure function
 * of its arguments and the Markdown pipeline stays in eleventy.config.mjs.
 */
export function buildJsonFeed(posts, { url, renderBody }) {
  const feed = {
    version: 'https://jsonfeed.org/version/1.1',
    title: SITE.author,
    description: SITE.description,
    home_page_url: url,
    feed_url: `${url.replace(/\/[^/]*$/, '')}/posts.json`,
    language: 'en',
    items: posts.map((post) => {
      const link = `${url.replace(/\/[^/]*$/, '')}${post.url}`;
      const body = renderBody(post);
      const item = {
        title: post.data.title,
        url: link,
        // JSON Feed wants a stable, globally unique id. The DOI is exactly
        // that, and every post here has one; the URL is the fallback.
        id: post.data.doi ? `https://doi.org/${post.data.doi}` : link,
        content_html: body.html,
        summary: post.data.description || '',
        date_published: new Date(post.data.pubDate).toISOString(),
        date_modified: new Date(post.data.updatedDate || post.data.pubDate).toISOString(),
        tags: post.data.tags ?? [],
        authors: (post.data.authors ?? []).map((author) => ({
          name: author.name,
          ...(author.qid ? { url: `https://www.wikidata.org/wiki/${author.qid}` } : {}),
        })),
      };
      if (post.data.doi) item._doi = post.data.doi;
      // Quarto's machine-readable citation list, under the same key its readers
      // and tooling already parse.
      if (body.references.length) item._references = body.references;
      if (post.data.pdf) {
        item.attachments = [
          { url: `${url.replace(/\/[^/]*$/, '')}${post.data.pdf}`, mime_type: 'application/pdf' },
        ];
      }
      return item;
    }),
  };
  return JSON.stringify(feed, null, 2);
}
