import assert from "node:assert/strict";
import test from "node:test";
import { buildJsonFeed } from "../src/lib/jsonFeed.mjs";
import { PREFIXES } from "../src/lib/prefixes.mjs";

test("PREFIXES maps core semantic web namespaces to http(s) IRIs", () => {
  for (const key of ["wd", "wdt", "schema", "cito", "orcid", "ror", "xsd"]) {
    assert.ok(PREFIXES[key], `expected prefix ${key}`);
    assert.match(PREFIXES[key], /^https?:\/\//);
  }
});

test("buildJsonFeed serialises JSON Feed 1.1 with DOI ids, CiTO references, and +00:00 dates", () => {
  const raw = buildJsonFeed(
    [
      {
        url: "/posts/example.html",
        data: {
          title: "Example Post",
          doi: "10.59350/abc-123",
          pubDate: "2026-01-20",
          tags: ["Metabolomics"],
          authors: [{ name: "Adriano Rutz", qid: "Q97455964" }],
          pdf: "/posts/example.pdf",
        },
      },
    ],
    {
      url: "https://adafede.github.io/",
      renderBody: () => ({
        html: "<p>Hello world.</p>",
        firstParagraph: "Hello world.",
        image: "/images/fig1.webp",
        references: [
          {
            url: "https://doi.org/10.7554/eLife.70780",
            doi: "10.7554/eLife.70780",
            cito: ["citesAsDataSource"],
          },
        ],
      }),
    },
  );

  const feed = JSON.parse(raw);
  assert.equal(feed.version, "https://jsonfeed.org/version/1.1");
  assert.equal(feed.feed_url, "https://adafede.github.io/posts.json");
  assert.equal(feed.items.length, 1);

  const item = feed.items[0];
  assert.equal(item.id, "https://doi.org/10.59350/abc-123");
  assert.equal(item._doi, "10.59350/abc-123");
  assert.equal(item.date_published, "2026-01-20T00:00:00+00:00");
  assert.equal(item.image, "https://adafede.github.io/images/fig1.png");
  assert.deepEqual(item.attachments, [
    {
      url: "https://adafede.github.io/posts/example.pdf",
      mime_type: "application/pdf",
    },
  ]);
  assert.deepEqual(item._references, [
    {
      url: "https://doi.org/10.7554/eLife.70780",
      doi: "10.7554/eLife.70780",
      cito: ["citesAsDataSource"],
    },
  ]);
});
