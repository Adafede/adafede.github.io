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


def test_no_label_in_the_actual_colormap_gets_the_worse_ink():
    """Measured over every colour build_expertise renders, the chosen ink is
    always the better of the two — which is the property the threshold test
    did not have and could not state."""
    cmap = cm.__dict__["batlowK"]
    for index in range(18):
        colour = mcolors.to_rgba(mcolors.to_hex(cmap(1 - index / 17)))
        chosen = ink_for(colour)
        dark = contrast_ratio(colour, mcolors.to_rgba(INK_DARK))
        light = contrast_ratio(colour, mcolors.to_rgba(INK_LIGHT))
        expected = INK_DARK if dark >= light else INK_LIGHT
        assert chosen == expected


def test_ink_flips_across_the_colormap_range():
    assert ink_for(mcolors.to_rgba("#faccfa")) == INK_DARK
    assert ink_for(mcolors.to_rgba("#04050a")) == INK_LIGHT


def test_a_known_acronym_is_left_alone():
    assert display_label("metabolomics") == "Metabolomics"
    assert display_label("msConvert") == "msConvert"
    assert display_label("") == ""
