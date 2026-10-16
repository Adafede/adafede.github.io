// Simulate the full Eleventy flow
import { htmlText as extractHtmlText } from "./scripts/site/html.mjs";

function truncateAtWord(text, limit) {
  const value = String(text ?? "").trim();
  if (value.length <= limit) return value;
  const clipped = value.slice(0, limit);
  const lastSpace = clipped.lastIndexOf(" ");
  const cut = lastSpace > limit * 0.6 ? clipped.slice(0, lastSpace) : clipped;
  return `${cut.replace(/[\s,;:.—-]+$/, "")}…`;
}

function plainText(value) {
  const text = String(value ?? "")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/<https?:\/\/[^>\s]+>/gi, " ")
    .replace(/\[([^\]]*)\]\([^)]*\)/g, "$1")
    .replace(/[*_`]/g, "")
    .replace(/["'\u2018\u2019]/g, "")
    .replace(/\s+/g, " ")
    .trim();
  return truncateAtWord(text, 300);
}

// The abstract as it would come from article.data.abstract
const abstract = "microbeMASST, a taxonomically informed mass spectrometry (MS) search tool, tackles limited microbial metabolite annotation in untargeted metabolomics experiments. Leveraging a curated database of >60,000 microbial monocultures";

console.log("=== Testing plainText filter ===");
console.log("Input abstract contains >60,000:", abstract.includes(">60,000"));
console.log("Input abstract contains &gt;:", abstract.includes("&gt;"));

const result = plainText(abstract);
console.log("\nplainText result contains >60,000:", result.includes(">60,000"));
console.log("plainText result contains &gt;:", result.includes("&gt;"));
console.log("plainText result contains &amp;:", result.includes("&amp;"));

// Nunjucks would escape this for HTML attribute context
function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const escaped = escapeHtml(result);
console.log("\nAfter Nunjucks escape:");
console.log("Contains &amp;gt;:", escaped.includes("&amp;gt;"));
console.log("Example snippet:", escaped.slice(0, 150));
