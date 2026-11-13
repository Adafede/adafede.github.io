import assert from "node:assert/strict";
import test from "node:test";

import { summaryFrom } from "../src/eleventy/_data/sitecontent.js";

test("a leading image does not leak into the summary", () => {
  assert.equal(
    summaryFrom("![A chart](/a.png)\n\nWe use a chart."),
    "We use a chart.",
  );
  assert.equal(
    summaryFrom("[![Badge](/b.svg)](https://x.org) Text [link](/y)."),
    "Text link.",
  );
});
