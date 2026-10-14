/** Global site metadata, mirroring _quarto.yml. */
import { PREFIXES } from '../../lib/prefixes.mjs';
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

export default {
  /** The site title used by <title> and og:title. */
  get title() {
    return this.author;
  },

  url: 'https://adafede.github.io',
  // The CV PDF is rendered by Quarto's LaTeX pipeline. On a branch that has
  // never run Quarto it does not exist, so templates check this rather than
  // linking to a 404. The path matches where stage-public.mjs puts it and where
  // Quarto publishes it: /cv.pdf. This used to look under public/pdf/, which is
  // where the PDFs lived before they were moved onto the Quarto URLs — the
  // button quietly stopped rendering when that changed.
  hasCvPdf: existsSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'public', 'cv.pdf')),
  hasAcademicCvPdf: existsSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', 'public', 'cv-academic.pdf')),
  author: 'Adriano Rutz',
  /**
   * The one place the contact address is written down.
   *
   * Templates render it through the `obfuscate` and `spellEmail` filters rather
   * than writing it out, so the address exists literally in exactly one file in
   * the source and nowhere in the published HTML.
   */
  contact: {
    email: 'rutz@imsb.biol.ethz.ch',
  },
  /**
   * Where the comments on a post live, for the link at the end of each one.
   *
   * This used to be repeated in every post's front matter, as a `giscusRepo`
   * key carried over from the Quarto source. Two reasons it is here instead: one
   * setting rather than the same string on every post, and the per-post copy was
   * not valid Quarto front matter, which broke `quarto render` when it walked
   * these generated files.
   */
  discussionsRepo: 'adafede/adafede.github.io',
  /**
   * The card image for link previews. A person's avatar is the honest choice
   * for a site with one author and no per-page artwork to speak of; the
   * per-article cover images are 352px wide and crop badly into a card.
   */
  ogImage: '/images/profile/avatar-520.webp',
  description:
    'Personal website of Adriano Rutz — Swiss pharmaceutical scientist specialising in metabolomics, mass spectrometry, and natural products research.',
  // Same RDFa prefix table the Quarto build emits.
  prefixes: Object.entries(PREFIXES).map(([prefix, iri]) => `${prefix}: ${iri}`).join('\n             '),
  // Assembled here because a literal `?` inside a Nunjucks tag reads as ternary.
  // `site` and `sitecontent` are separate data objects, so the profile id is read
  // from disk instead of from a sibling key.
  scholarUrl: `https://scholar.google.com/citations?user=${readFileSync(
    fileURLToPath(new URL('../../content/profiles.json', import.meta.url)),
    'utf-8',
  ).match(/"scholar":\s*"([^"]+)"/)?.[1] ?? ''}`,
  nav: [
    { url: '/articles.html', label: 'Articles' },
    { url: '/cv.html', label: 'CV' },
    { url: '/posts.html', label: 'Posts' },
    { url: '/talks.html', label: 'Talks' },
    { url: '/teaching.html', label: 'Teaching' },
    { url: '/varia.html', label: 'Varia' },
  ],
};
