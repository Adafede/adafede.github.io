"""Label-ink choice for the expertise circle packing."""

import matplotlib.colors as mcolors
import pytest
from cmcrameri import cm

from scripts.site.build_expertise import (
    INK_DARK,
    INK_LIGHT,
    contrast_ratio,
    display_label,
    ink_for,
    relative_luminance,
)


def test_black_and_white_are_the_extremes():
    assert contrast_ratio((0, 0, 0), (1, 1, 1)) == 21.0


def test_a_colour_is_contrasted_against_itself():
    assert contrast_ratio((0.4, 0.4, 0.4), (0.4, 0.4, 0.4)) == 1.0


def test_relative_luminance_linearises_the_channels():
    """A weighted sum of gamma-encoded values is an NTSC luma approximation.

    It puts the black/white crossover in the wrong place, and on a colormap
    that spends its range in the mid-tones that showed up as a label with the
    worse of the two inks.
    """
    mid = (0.5, 0.5, 0.5)
    naive = 0.2126 * 0.5 + 0.7152 * 0.5 + 0.0722 * 0.5
    assert relative_luminance(mid) < naive
    assert relative_luminance((0, 0, 0)) == 0.0
    assert relative_luminance((1, 1, 1)) == pytest.approx(1.0)


def test_ink_is_whichever_reads_better_not_which_side_of_a_threshold():
    """#938839 is where the old `luminance > 0.55` cut-off went wrong.

    It read as dark to the un-linearised weighted sum and picked white ink, which
    measures 3.61:1 on it. Dark ink measures 4.95:1. This colormap spends most of
    its range in exactly the band the approximation gets wrong.
    """
    mid = mcolors.to_rgba("#938839")
    assert ink_for(mid) == INK_DARK
    assert contrast_ratio(mid, mcolors.to_rgba(INK_DARK)) > contrast_ratio(
        mid,
        mcolors.to_rgba(INK_LIGHT),
    )


def test_every_label_meets_wcag_aa_contrast():
    """Over every colour build_expertise renders, and a sweep of the whole grey
    range, the chosen ink reaches 4.5:1. With a near-black ink the worst
    circle was at 4.35:1."""
    cmap = cm.__dict__["batlowK"]
    colours = [mcolors.to_rgba(mcolors.to_hex(cmap(1 - i / 17))) for i in range(18)]
    colours += [(v / 255, v / 255, v / 255, 1.0) for v in range(256)]
    for colour in colours:
        ratio = contrast_ratio(colour, mcolors.to_rgba(ink_for(colour)))
        assert ratio >= 4.5, (mcolors.to_hex(colour), round(ratio, 2))


def test_ink_flips_across_the_colormap_range():
    assert ink_for(mcolors.to_rgba("#faccfa")) == INK_DARK
    assert ink_for(mcolors.to_rgba("#04050a")) == INK_LIGHT


def test_a_known_acronym_is_left_alone():
    assert display_label("metabolomics") == "Metabolomics"
    assert display_label("msConvert") == "msConvert"
    assert display_label("") == ""


def test_css_text_rule_does_not_override_svg_fill_attribute():
    """An author `fill` rule on `text` beats SVG `fill="#ffffff"` presentation
    attributes; default ink must sit on `.expertise__pack` so `<text>` inherits
    it only when no `fill` attribute is present."""
    import re
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "src/styles/global.css").read_text(
        encoding="utf-8",
    )
    match = re.search(r"\.expertise__pack\s+a\s+text\s*\{([^}]*)\}", css)
    assert match is not None
    assert "fill:" not in match.group(1)


def test_css_default_ink_is_ink_dark():
    """Dark-ink labels carry no fill attribute and take the CSS default, so the
    stylesheet and INK_DARK must agree or the contrast test checks the wrong
    colour."""
    import re
    from pathlib import Path

    css = (Path(__file__).resolve().parents[1] / "src/styles/global.css").read_text(
        encoding="utf-8",
    )
    match = re.search(r"\.expertise__pack\s*\{([^}]*)\}", css)
    assert match is not None
    fill = re.search(r"fill:\s*(#[0-9a-fA-F]{3,8})", match.group(1))
    assert fill is not None
    assert mcolors.to_hex(fill.group(1)) == mcolors.to_hex(INK_DARK)
