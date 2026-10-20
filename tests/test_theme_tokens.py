"""Guards on the colour-token blocks in src/styles/global.css.

A custom property declared twice in the same block is silently dead: the
later declaration wins and the earlier one never ships. That happened with
--expertise-stroke, whose light value was shadowed by a dark one left in the
same :root block, so the light theme drew an invisible white outline. The
contrast checker cannot see this — it reads the winning value and finds it
perfectly valid — so it needs its own guard.
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
CUSTOM_PROPERTY = re.compile(r"(--[a-z][a-z0-9-]*)\s*:")


COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _normalise(selector: str) -> str:
    """Collapse a selector to one line so multi-line selectors still match."""
    without_comments = COMMENT.sub(" ", selector)
    return " ".join(without_comments.split())


def _blocks(css: str):
    for selector, body in BLOCK.findall(css):
        yield _normalise(selector), body


def test_no_custom_property_is_declared_twice_in_one_block():
    duplicates = []
    for selector, body in _blocks(CSS.read_text(encoding="utf-8")):
        seen: dict[str, int] = {}
        for prop in CUSTOM_PROPERTY.findall(body):
            seen[prop] = seen.get(prop, 0) + 1
        duplicates.extend(
            f"{prop} x{count} in `{selector}`"
            for prop, count in seen.items()
            if count > 1
        )
    assert not duplicates, "duplicate custom properties (the earlier is dead): " + (
        "; ".join(duplicates)
    )


def test_every_token_block_declares_the_theme_dependent_colours():
    """The three palette blocks must define the same colour tokens.

    A token present in `:root` and the dark media block but missing from an
    `html:has(#theme-*:checked)` override keeps its previous value when that
    theme is forced — the override silently does not cover it. The blocks are
    compared on the colour tokens they share, not on their full property sets,
    because the overrides intentionally omit layout tokens.
    """
    css = CSS.read_text(encoding="utf-8")
    blocks = list(_blocks(css))

    def colours(selector: str) -> set[str]:
        wanted = _normalise(selector)
        bodies = [body for sel, body in blocks if sel == wanted]
        assert bodies, f"no block matched `{wanted}`"
        return {
            prop
            for body in bodies
            for prop in CUSTOM_PROPERTY.findall(body)
            if not prop.startswith("--space")
        }

    light_override = colours("html:has(#theme-light:checked)")
    dark_override = colours("html:has(#theme-dark:checked)")

    assert light_override, "the light override block is missing"
    assert dark_override, "the dark override block is missing"
    assert light_override == dark_override, (
        "the light and dark overrides must set the same tokens: "
        f"light-only {sorted(light_override - dark_override)}, "
        f"dark-only {sorted(dark_override - light_override)}"
    )
