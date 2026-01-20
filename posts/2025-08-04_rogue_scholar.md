---
affiliations:
- address: Otto-Stern-Weg, 3
  city: Zürich
  country: Switzerland
  department: Institute for Molecular Systems Biology
  group: Zamboni
  id: imsb
  name: ETH Zürich
  postal-code: 8093
  qid: Q115117760
  ror: "https://ror.org/03j5gm982"
author:
- Adriano Rutz
authors:
- id: AdrianoRutz
  name:
    family: Rutz
    given: Adriano
    literal: Adriano Rutz
  orcid: 0000-0003-0443-9902
  qid: Q97455964
  url: "https://adafede.github.io"
bibliography:
- references.bib
categories:
- Open Science
citation:
  available-date:
    date-parts:
    - - 2025
      - 8
      - 4
    iso-8601: 2025-08-04
    literal: 2025-08-04
    raw: 2025-08-04
  issued:
    date-parts:
    - - 2025
      - 8
      - 4
    iso-8601: 2025-08-04
    literal: 2025-08-04
    raw: 2025-08-04
comments:
  giscus:
    repo: adafede/adafede.github.io
  hypothesis:
    showHighlights: always
creative_commons: CC BY
date: 2025-08-04
doi: 10.59350/yckwd-9vm79
google-scholar: true
kernel: ../.venv
license:
- type: creative-commons
  url: "https://creativecommons.org/licenses/by/4.0/"
link-citations: true
title: "Open Science Upgrade: Adding Blog Posts to my Website and
  Linking to Rogue Scholar"
toc-title: Table of contents
---

I have finally opened a `Posts` section on my website! Every post should
now automatically get a DOI.

This is something I have wanted to do for a long time, largely inspired
by the tireless and consistent example set by [Egon
Willighagen](https://scholia.toolforge.org/author/Q20895241)
[@cites:willighagen2024a; @cites:willighagen2024b; @cites:willighagen2025].

It was today's post of [@obtains_background_from:fenner2025] that
finally motivated me to look into it again. That led me down a
productive rabbit hole to set up Rogue Scholar: first landing on
[@obtains_background_from:voncsefalvay2023]'s excellent guide, and then
[@uses_method_in:fruehwald2025]'s clear write-up, both of which made the
process of integrating Rogue Scholar into a Quarto-based site
surprisingly smooth.

All the changes are documented in the following commit:

<https://github.com/Adafede/adafede.github.io/commit/bc2dfe6f>

If you care about attribution, long-term archiving, DOIs and metadata, I
highly recommend looking into [Rogue
Scholar](https://rogue-scholar.org/).

**Edit (1):** I realized that integrating
[CiTO](https://sparontologies.github.io/cito/current/cito.html) could be
a significant enhancement. With some effort (and thanks again to Egon),
I managed to implement a working solution for the HTML and PDF outputs,
see [@uses_method_in:willighagen2023]. However, the solution for the XML
feed still feels suboptimal.

**Edit (2):** After some help from Egon and
[Martin](https://scholia.toolforge.org/author/Q30532925), I could
improve my feed with correct CiTO annotations and their cool custom json
feed, see: <https://adafede.github.io/posts.json>!

### References
