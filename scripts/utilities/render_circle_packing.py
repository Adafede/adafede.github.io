"""Areas of Expertise Circle Packing Generator using Circlify and SPARQL.

Fetches topic expertise metrics via SPARQL QLever API and generates an
interactive SVG circle packing diagram for Quarto notebooks.
"""

from __future__ import annotations

import json
import math
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import matplotlib.colors as mcolors

if TYPE_CHECKING:
    # Type stubs for untyped third-party libraries
    from matplotlib.colors import Colormap

    class Circle:
        """Type stub for circlify.Circle at type-checking time."""

        def __init__(self, x: float = 0, y: float = 0, r: float = 0) -> None:
            self.x = x
            self.y = y
            self.r = r
            self.ex = {}

        x: float
        y: float
        r: float
        ex: dict[str, float | str] | str

    class _Circle(Protocol):
        """Protocol for circlify Circle objects."""

        x: float
        y: float
        r: float
        ex: dict[str, float | str] | str

    class _CirclifyModule(Protocol):
        """Protocol for circlify module."""

        def circlify(
            self,
            data: list[dict[str, float | str]],
            *,
            show_enclosure: bool = False,
            target_enclosure: _Circle | None = None,
            **kwargs: object,
        ) -> list[_Circle]: ...

    circlify: _CirclifyModule

    class _CmcrameriModule(Protocol):
        """Protocol for cmcrameri module."""

        batlowK: Colormap

    cm: _CmcrameriModule

else:
    import circlify
    from circlify import Circle
    from cmcrameri import cm

from IPython.display import HTML, display

# Add project root to path so `scripts` is importable as a package
root_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(root_dir))

from scripts.infrastructure import get_logger

logger = get_logger(__name__)

# Constants
DEFAULT_TARGET_QID = "Q97455964"
DEFAULT_SCALE_POWER = 2.0
DEFAULT_LIMIT = 16
DEFAULT_VIEW_BOX = 640
DEFAULT_MAP_HEIGHT = 600
DEFAULT_USER_AGENT = "CirclePackingGenerator/1.0"
QLEVER_API_URL = "https://qlever.dev/api/wikidata"


# SPARQL Fetching and Parsing


def build_sparql_query(target_qid: str, limit: int = 16) -> str:
    """Build SPARQL query string for topic expertise scores.

    Args:
        target_qid: Wikidata QID for the target entity
        limit: Max number of topics to retrieve

    Returns:
        Formatted SPARQL query string
    """
    return f"""
    PREFIX wdt: <http://www.wikidata.org/prop/direct/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX target: <http://www.wikidata.org/entity/{target_qid}>

    SELECT ?score ?topic ?topicLabel WHERE {{
      {{
        SELECT (SUM(?score_) AS ?score) ?topic WHERE {{
          {{ SELECT (64 AS ?score_) ?topic WHERE {{ target: wdt:P101 ?topic . }} }}
          UNION {{ SELECT (32 AS ?score_) ?topic WHERE {{ ?work wdt:P50 target: ; wdt:P921 ?topic . }} }}
          UNION {{ SELECT (16 AS ?score_) ?topic WHERE {{ ?work wdt:P50 target: ; (wdt:P921/wdt:P279) ?topic . }} }}
          UNION {{ SELECT (8 AS ?score_) ?topic WHERE {{ ?work wdt:P50 target: ; (wdt:P921/wdt:P279/wdt:P279) ?topic . }} }}
          UNION {{ SELECT (32 AS ?score_) ?topic WHERE {{ ?work wdt:P50 target: ; wdt:P4510 ?topic . }} }}
          UNION {{ SELECT (16 AS ?score_) ?topic WHERE {{ ?work wdt:P50 target: ; (wdt:P4510/wdt:P279) ?topic . }} }}
          UNION {{ SELECT (8 AS ?score_) ?topic WHERE {{ ?work wdt:P50 target: ; (wdt:P4510/wdt:P279/wdt:P279) ?topic . }} }}
        }}
        GROUP BY ?topic
      }}
      ?topic rdfs:label ?topicLabel .
      FILTER (LANG(?topicLabel) = "en")
    }}
    ORDER BY DESC(?score)
    LIMIT {limit}
    """


def fetch_topic_scores(
    target_qid: str,
    user_agent: str = DEFAULT_USER_AGENT,
    limit: int = DEFAULT_LIMIT,
) -> list[dict[str, dict[str, str]]]:
    """Fetch topic expertise data from QLever Wikidata endpoint."""
    query = build_sparql_query(target_qid, limit=limit)
    params = urllib.parse.urlencode({"query": query, "format": "json"})
    url = f"{QLEVER_API_URL}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": user_agent})

    try:
        with urllib.request.urlopen(req) as response:
            raw_data = json.loads(response.read().decode())
            return raw_data.get("results", {}).get("bindings", [])
    except (urllib.error.URLError, json.JSONDecodeError) as e:
        logger.error(f"Failed to fetch data for {target_qid}: {e}")
        return []


# Type alias for metadata dict
MetaDict = dict[str, float | str]


def process_items(
    bindings: list[dict[str, dict[str, str]]],
    scale_power: float,
) -> tuple[list[dict[str, float | str]], dict[str, MetaDict]]:
    """Process SPARQL results into circlify items and metadata lookup."""
    items: list[dict[str, float | str]] = []
    items_by_id: dict[str, MetaDict] = {}

    for b in bindings:
        topic_url = b["topic"]["value"]
        qid = topic_url.split("/")[-1]
        score = float(b["score"]["value"])
        label = b["topicLabel"]["value"]

        scaled_datum = math.pow(score, scale_power)

        # circlify only expects 'id' and 'datum'
        item: dict[str, float | str] = {
            "id": qid,
            "datum": scaled_datum,
        }
        items.append(item)

        # Store topic metadata separately in lookup map
        items_by_id[qid] = {
            "label": label,
            "url": topic_url,
            "score": score,
            "id": qid,
        }

    return items, items_by_id


# SVG Rendering Utilities


def compute_text_styling(
    label: str,
    r: float,
    _score: float,  # unused, kept for API compatibility
    rank_norm: float,
    cmap: mcolors.Colormap,
) -> tuple[str, str, list[str], int]:
    """Calculate color contrast, text wrapping, and optimal font size."""
    rgba = cmap(rank_norm)
    color = mcolors.to_hex(rgba)

    # W3C relative luminance contrast check
    luminance = 0.299 * rgba[0] + 0.587 * rgba[1] + 0.114 * rgba[2]
    text_color = "#FFF" if luminance < 0.5 else "#0F172A"

    # Word wrapping logic
    words = label.split(" ")
    lines = []
    curr = ""
    max_line_chars = max(4, int(r / 5.2))
    for w in words:
        if len(curr + " " + w) > max_line_chars:
            if curr:
                lines.append(curr)
            curr = w
        else:
            curr = (curr + " " + w).strip()
    if curr:
        lines.append(curr)

    # Dynamic font sizing calculation
    max_fs_height = (1.5 * r) / (len(lines) * 1.15)
    max_line_len = max(len(line) for line in lines) if lines else 1
    max_fs_width = (1.65 * r) / (max_line_len * 0.58)
    font_size = max(7, min(28, int(min(max_fs_height, max_fs_width))))

    return color, text_color, lines, font_size


if TYPE_CHECKING:
    # Runtime type for circles - protocol with needed attributes
    class _CircleProto(Protocol):
        x: float
        y: float
        r: float
        ex: dict[str, float | str] | str
else:
    _CircleProto = object


def generate_svg_markup(
    circles: Sequence[_CircleProto],
    items_by_id: dict[str, MetaDict],
    view_box: int = DEFAULT_VIEW_BOX,
    height: int = DEFAULT_MAP_HEIGHT,
) -> str:
    """Generate accessible, SEO-optimized interactive SVG markup from layout circles."""
    center = view_box / 2
    cmap = cm.batlowK

    all_scores = sorted(
        {meta["score"] for meta in items_by_id.values()},
        reverse=True,
    )
    num_ranks = max(1, len(all_scores))

    # Calculate summary statistics for AI/Crawler description
    total_nodes = len(circles)
    if circles:
        first_ex = circles[0].ex
        # Extract ID depending on whether .ex is a dict or string
        top_qid = first_ex.get("id", "") if isinstance(first_ex, dict) else first_ex
        if not isinstance(top_qid, str):
            top_qid = ""
        top_label = items_by_id.get(top_qid, {}).get("label", "Unknown")
    else:
        top_label = "N/A"

    svg_parts = [
        '<div itemscope itemtype="https://schema.org/VisualArtwork" class="circle-pack-container">',
        '  <meta itemprop="name" content="Areas of Expertise Circle Packing Diagram" />',
        f'  <meta itemprop="description" content="Interactive circle packing visualization featuring {total_nodes} topics of expertise, led by {top_label}." />',
        (
            f'  <svg viewBox="0 0 {view_box} {view_box}" width="{view_box}" height="{view_box}" role="graphics-document" '
            'aria-labelledby="circle-pack-title circle-pack-desc" '
            'style="width: 100%; max-width: 100%; height: auto; display: block; margin: 0 auto; background: #FFF; border-radius: 16px; font-family: system-ui, -apple-system, sans-serif;">'
        ),
        '    <title id="circle-pack-title">Areas of Expertise Circle Packing Diagram</title>',
        (
            '    <desc id="circle-pack-desc">'
            f"A hierarchical circle chart showing {total_nodes} top research topics sourced from Wikidata. "
            f"Larger circles indicate higher relative impact scores. Primary topic: {top_label}."
            "    </desc>"
        ),
        "    <style>",
        "    a { text-decoration: none; }",
        "    .node-circle { transition: transform 0.2s ease, fill-opacity 0.2s ease; cursor: pointer; }",
        "    .node-circle:hover, .node-circle:focus { fill-opacity: 1.0; stroke: #FFF; stroke-width: 3px; outline: none; }",
        "    .node-text { pointer-events: none; user-select: none; font-weight: 700; }",
        "    @media (prefers-reduced-motion: reduce) { .node-circle { transition: none; } }",
        "  </style>",
    ]

    for c in circles:
        cx, cy, r = center + c.x, center + c.y, c.r

        node_id = c.ex if isinstance(c.ex, str) else getattr(c, "id", None)
        if isinstance(c.ex, dict):
            node_id = c.ex.get("id", node_id)
        if not isinstance(node_id, str):
            node_id = ""

        meta = items_by_id.get(node_id, {})
        if not isinstance(meta, dict):
            meta = {}
        if not meta and isinstance(c.ex, dict):
            meta = c.ex.get("data", c.ex) or {}

        score = meta.get("score", 0) if isinstance(meta, dict) else 0
        label = meta.get("label", "") if isinstance(meta, dict) else ""
        url_link = meta.get("url", "#") if isinstance(meta, dict) else "#"
        qid = meta.get("id", "") if isinstance(meta, dict) else ""

        rank_norm = (
            1.0 - (all_scores.index(float(score)) / (num_ranks - 1))
            if float(score) in all_scores and num_ranks > 1
            else 0.5
        )

        color, text_color, lines, font_size = compute_text_styling(
            str(label),
            r,
            float(score),
            rank_norm,
            cmap,
        )

        # Accessible text attributes
        aria_label = f"{label}, score: {int(score)}"
        tooltip_text = f"{label}\nScore: {int(score)}\nQID: {qid}"

        svg_parts.append(
            f'    <a href="{url_link}" target="_blank" rel="noopener" aria-label="{aria_label}">',
        )
        svg_parts.append(
            '      <g role="graphics-object" aria-roledescription="node" tabindex="0">',
        )
        svg_parts.append(f"        <title>{tooltip_text}</title>")
        svg_parts.append(
            f'        <circle class="node-circle" cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
            + f'fill="{color}" fill-opacity="0.88" stroke="#FFF" stroke-width="2" />',
        )
        svg_parts.append(
            f'        <text class="node-text" x="{cx:.2f}" y="{cy:.2f}" font-size="{font_size}px" '
            + f'fill="{text_color}" text-anchor="middle" dominant-baseline="central">',
        )

        line_height = font_size * 1.15
        start_y = cy - ((len(lines) - 1) * line_height / 2)

        for idx, line in enumerate(lines):
            ly = start_y + (idx * line_height)
            svg_parts.append(
                f'          <tspan x="{cx:.2f}" y="{ly:.2f}">{line}</tspan>',
            )

        svg_parts.append("        </text>")
        svg_parts.append("      </g>")
        svg_parts.append("    </a>")

    svg_parts.append("  </svg>")
    svg_parts.append("</div>")

    return "\n".join(svg_parts)


# Main Exported Function


def render_circle_packing(
    target_qid: str = DEFAULT_TARGET_QID,
    scale_power: float = DEFAULT_SCALE_POWER,
    limit: int = DEFAULT_LIMIT,
    display_output: bool = True,
) -> HTML | None:
    """Generate and display interactive circle packing diagram of topic expertise."""
    logger.info("Generating circle packing map")

    bindings = fetch_topic_scores(target_qid, limit=limit)
    if not bindings:
        logger.warning(f"No results found for target QID: {target_qid}")
        return None

    items, items_by_id = process_items(bindings, scale_power)

    circles = circlify.circlify(
        items,
        show_enclosure=False,
        target_enclosure=Circle(x=0, y=0, r=300),
    )

    svg_html = generate_svg_markup(circles, items_by_id)
    html_object = HTML(svg_html)

    logger.info("Circle packing map generated successfully")

    if display_output:
        _ = display(html_object)
        return None

    return html_object


def main() -> None:
    """CLI entry point."""
    _ = render_circle_packing()


if __name__ == "__main__":
    main()
