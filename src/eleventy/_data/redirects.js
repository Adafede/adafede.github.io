import buildData from "./sitecontent.js";

/**
 * The URLs that differ between the Quarto site and this one.
 *
 * Consumed by both `src/eleventy/redirects-netlify.njk` (`/_redirects`, for
 * hosts like Netlify and Cloudflare Pages) and `src/eleventy/redirect.njk`
 * (static HTML redirect pages for hosts that ignore `_redirects`, such as
 * GitHub Pages), keeping a single source of truth.
 */
export default function redirects() {
  return [
    { from: "/rss.html", to: "/rss.xml" },
    // Quarto has a standalone page at this URL. Its three identifiers are
    // already on /articles.html, so a separate page repeated them; the old URL
    // still has to resolve, because it has been published.
    { from: "/articles/profiles.html", to: "/articles.html" },
    { from: "/blog.html", to: "/posts.html" },
    // An earlier iteration served posts under /blog/. Those URLs were never
    // published, but they are cheap to keep resolving.
    ...buildData()
      .posts()
      .map((post) => ({
        from: `/blog/${post.id}.html`,
        to: `/posts/${post.id}.html`,
      })),
  ];
}
