"""Guards on the colour-token blocks in src/styles/global.css.

The palette is two blocks: the light values in `:root` and the dark override in
`@media (prefers-color-scheme: dark)`. Two things go wrong silently:

  * a custom property declared twice in one block — the later wins and the
    earlier never ships. That happened with --expertise-stroke, whose light
    value was shadowed by a dark one left in the same :root block;
  * a colour token present in one block but not the other, which leaves that
    colour at the previous theme's value.

The contrast checker cannot see either: it reads the winning value and finds it
valid. Hence this guard.
"""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[1] / "src" / "styles" / "global.css"

# A declaration block, non-greedy, with its selector kept so a failure can name
# it. Nested at-rules (media, supports) are skipped deliberately: their inner
# rules are matched as blocks in their own right, which is where the property
# actually lives.
BLOCK = re.compile(r"([^{}]+)\{([^{}]*)\}")
COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)
CUSTOM_PROPERTY = re.compile(r"(--[a-z][a-z0-9-]*)\s*:")

# Tokens that are structural, not palette, and so need not appear in the dark
# block. Everything else that is a colour has to be redefined for dark.
NON_COLOUR_PREFIXES = (
    "--sans",
    "--serif",
    "--mono",
    "--step-",
    "--space-",
    "--measure",
    "--page",
    "--wide",
    "--radius",
)


def _normalise(selector: str) -> str:
    """Collapse a selector to one line so multi-line selectors still match."""
    return " ".join(COMMENT.sub(" ", selector).split())


def _blocks(css: str):
    for selector, body in BLOCK.findall(css):
        yield _normalise(selector), body


def _custom_properties(body: str) -> list[str]:
    return CUSTOM_PROPERTY.findall(body)


def test_no_custom_property_is_declared_twice_in_one_block():
    duplicates = []
    for selector, body in _blocks(CSS.read_text(encoding="utf-8")):
        seen: dict[str, int] = {}
        for prop in _custom_properties(body):
            seen[prop] = seen.get(prop, 0) + 1
        duplicates.extend(
            f"{prop} x{count} in `{selector}`"
            for prop, count in seen.items()
            if count > 1
        )
    assert not duplicates, "duplicate custom properties (the earlier is dead): " + (
        "; ".join(duplicates)
    )


def test_the_dark_block_redeclares_every_light_colour_token():
    """Every colour token in `:root` must be redeclared in the dark media block.

    A token the dark block omits keeps its light value on a dark page. The light
    block is the first `:root` in the file (the dark one is nested inside a media
    query, so the regex sees it as a second `:root`).
    """
    css = CSS.read_text(encoding="utf-8")
    light_body = _light_root(css)
    dark_body = _inner_root(css)
    assert light_body is not None, "no light :root found"
    assert dark_body is not None, "no :root inside prefers-color-scheme: dark"

    def colours(props):
        return {p for p in props if not p.startswith(NON_COLOUR_PREFIXES)}

    light_colours = colours(_custom_properties(light_body))
    dark_colours = colours(_custom_properties(dark_body))

    assert light_colours, "no colour tokens found in :root"
    assert light_colours == dark_colours, (
        "the dark block must redeclare every light colour token: "
        f"light-only {sorted(light_colours - dark_colours)}, "
        f"dark-only {sorted(dark_colours - light_colours)}"
    )


def _light_root(css: str) -> str | None:
    """The body of the first top-level `:root` (the light palette).

    The regex-based block splitter also reports the `:root` nested inside the
    dark media query, so the file's first `:root` is the light one.
    """
    match = re.search(r"(?:^|\n):root\s*\{([^{}]*)\}", css)
    return match.group(1) if match else None


def _inner_root(css: str) -> str | None:
    """The body of the `:root` declared inside the dark media query.

    There can be more than one `prefers-color-scheme: dark` block (the Shiki one
    has no tokens), so this finds the media block that actually wraps a `:root`.
    """
    for media in re.finditer(r"@media\s*\(prefers-color-scheme:\s*dark\)\s*\{", css):
        # From the media opening brace, walk to its matching brace, then look
        # for :root within that span.
        start = media.end()
        depth = 1
        index = start
        while index < len(css) and depth:
            if css[index] == "{":
                depth += 1
            elif css[index] == "}":
                depth -= 1
            index += 1
        inner = re.search(r":root\s*\{([^{}]*)\}", css[start:index])
        if inner:
            return inner.group(1)
    return None
