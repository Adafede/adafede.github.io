/**
 * The per-listing feeds.
 *
 * Quarto emits an RSS feed for every listing on the site — posts.xml,
 * articles.xml, talks.xml, teaching.xml, varia.xml — because its listing
 * widget reads them. Those URLs have been live for years, so dropping them
 * would break every subscription made against them, whatever the widget does.
 *
 * Each entry names its own listing page and the items on it. The items are
 * resolved lazily, so a feed is only ever built for a collection that exists.
 */
import buildContent from "./sitecontent.js";

export default function listingFeeds() {
  // Imported rather than read off the data cascade: a global-data function is
  // called with the cascade as `this` only in some Eleventy versions, and this
  // one must not depend on that.
  const content = buildContent();
  return [
    {
      slug: "articles",
      title: "Articles",
      url: "/articles.html",
      items: () => content.articles(),
      date: (item) => item.data.date,
      category: () => undefined,
    },
    {
      slug: "talks",
      title: "Talks",
      url: "/talks.html",
      items: () => content.talks(),
      date: (item) => item.data.date,
      category: (item) => (item.data.tags ?? [])[0] ?? undefined,
    },
    {
      slug: "teaching",
      title: "Teaching",
      url: "/teaching.html",
      items: () => content.teaching(),
      date: (item) => item.data.date,
      category: (item) => (item.data.tags ?? [])[0] ?? undefined,
    },
    {
      slug: "posts",
      title: "Posts",
      url: "/posts.html",
      items: () => content.posts(),
      date: (item) => item.data.date || item.data.pubDate,
      category: (item) => (item.data.tags ?? [])[0] ?? undefined,
    },
    {
      slug: "varia",
      title: "Varia",
      url: "/varia.html",
      items: () => content.varia(),
      date: () => undefined,
      category: (item) => (item.data.tags ?? [])[0] ?? undefined,
    },
    {
      // Quarto's catch-all listing. It has no page of its own, but the address
      // and its shape are part of the published site, so it is reproduced here.
      slug: "rss",
      title: "All items",
      // /rss.html redirects to this very feed, so linking the channel at it
      // would point a reader at a feed from the feed. The site root is the
      // page this feed actually describes.
      url: "/",
      date: (item) => item.data.date || item.data.pubDate,
      category: (item) => (item.data.tags ?? [])[0] ?? undefined,
      // Newest first, so that the cap below keeps the 20 most recent items
      // rather than the first 20 articles and nothing else. Undated items (the
      // varia listings) sort last.
      items: () => {
        const all = [
          ...content.articles(),
          ...content.talks(),
          ...content.teaching(),
          ...content.varia(),
          ...content.posts(),
        ];
        const stamp = (item) => {
          const when = item.data.date || item.data.pubDate;
          if (!when) return 0;
          const time = new Date(when).getTime();
          return Number.isNaN(time) ? 0 : time;
        };
        return all.sort((a, b) => stamp(b) - stamp(a));
      },
      // Quarto published the 20 most recent here, not all 80. Keeping the cap
      // matters: a reader on this feed has a bounded backlog, and a feed that
      // silently grows to every talk ever given is a different feed.
      limit: 20,
    },
  ];
}
