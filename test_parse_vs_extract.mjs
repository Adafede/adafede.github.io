import { parseFragment, serialize } from "parse5";
import { htmlText as extractHtmlText } from "./scripts/site/html.mjs";

const text = "Leveraging a curated database of >60,000 microbial monocultures";

try {
  const fragment = parseFragment(text);
  console.log("parseFragment succeeded");
  console.log("serialize output:", serialize(fragment));
} catch (e) {
  console.log("parseFragment error:", e.message);
}

console.log("\nextractHtmlText output:", extractHtmlText(text));
