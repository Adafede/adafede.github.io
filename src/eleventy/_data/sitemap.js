/**
 * The URL inventory for sitemap.xml.
 *
 * `collections.all` is not usable for this: Eleventy puts only the *first* page
 * of a paginated template into a collection, so iterating it emitted one
 * `<loc>` per listing and silently dropped every individual article, talk,
 * teaching entry, varia page and post. Each listing names its own page plus
 * the items on it, so a reader subscribed to talks.xml sees the talks page
 * change underneath them.
 *
 * Pages that only redirect (blog.html, rss.html, the legacy /blog//* URLs) are
 * deliberately absent: they carry `noindex` and point somewhere else, and a
 * sitemap entry for a redirect is a sitemap that lies.
 */
import buildContent from "./sitecontent.js";

const content = buildContent();
const seen = new Set();
const urls = [];

const push = (loc, { lastmod, priority } = {}) => {
  if (!loc || seen.has(loc)) return;
  seen.add(loc);
  urls.push({ loc, lastmod, priority });
};

push("/", { priority: "1.0" });

const listing = (label, items, priority) => {
  push(label, { priority });
  for (const item of items) {
    push(item.url, {
      lastmod:
        (item.data.updatedDate ?? item.data.pubDate ?? item.data.date) ||
        undefined,
      priority,
    });
  }
};

listing("/posts.html", content.posts(), "0.9");
listing("/articles.html", content.articles(), "0.9");
listing("/talks.html", content.talks(), "0.7");
listing("/teaching.html", content.teaching(), "0.6");
listing("/varia.html", content.varia(), "0.5");

push("/cv.html", { priority: "0.8" });
push("/privacy.html", { priority: "0.3" });

export default urls;
