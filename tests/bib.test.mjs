import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import {
  detex,
  inlineCitation,
  parseAuthors,
  parseBib,
  renderReference,
} from '../src/lib/bib.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const bib = parseBib(readFileSync(join(here, '..', 'posts', 'references.bib'), 'utf-8'));

const entry = (body) => parseBib(body).get('k');

test('detex composes TeX accents to precomposed characters', () => {
  assert.equal(detex('R{\\"u}tz'), 'Rütz');
  // \v{s} is š; ő takes \H{o}. Worth pinning, because the two differ by one
  // character and both spellings turn up in Central European author names.
  assert.equal(detex('Erd{\\v{s}}ly'), 'Erdšly');
  assert.equal(detex('Erd{\\H{o}}ly'), 'Erdőly');
  assert.equal(detex('Schr{\\"o}dinger'), 'Schrödinger');
  // Normalised to NFC, so the rendered text matches Quarto's code point for
  // code point and not merely to the eye.
  assert.equal(detex('R{\\"u}tz').charCodeAt(1), 0x00fc);
});

test('detex drops the remaining TeX rather than printing it', () => {
  assert.equal(detex('X-ray \\emph{study}'), 'X-ray study');
  assert.equal(detex('a {b} c'), 'a b c');
});

test('an entry with no author renders its year alone', () => {
  assert.equal(inlineCitation({ fields: { year: '2024' } }), '2024');
});

test('an unknown citation says so rather than rendering undefined', () => {
  assert.equal(inlineCitation(undefined), '???');
});

test('author counts decide the citation form', () => {
  const one = entry('@article{k, author = {Rutz, Adriano}, year = {2024}}');
  const two = entry('@article{k, author = {Rutz, Adriano and Bach, Sara}, year = {2024}}');
  const many = entry(
    '@article{k, author = {Rutz, Adriano and Bach, Sara and Ott, Urs and Zen, Yan and Wu, Li}, year = {2024}}',
  );

  assert.equal(inlineCitation(one), 'Rutz 2024');
  assert.equal(inlineCitation(two), 'Rutz and Bach 2024');
  assert.equal(inlineCitation(many), 'Rutz et al. 2024');
});

test('a year-less entry falls back to n.d. rather than an empty year', () => {
  assert.equal(inlineCitation(entry('@misc{k, author = {Rutz, Adriano}}')), 'Rutz n.d.');
});

test('parseAuthors splits on the BibTeX author separator and detexes', () => {
  assert.deepEqual(parseAuthors('R{\\"u}tz, Adriano and Bach, Sara'), [
    'Rütz, Adriano',
    'Bach, Sara',
  ]);
  assert.deepEqual(parseAuthors(''), []);
  // A family name that is literally "and" survives, because the split needs
  // whitespace on both sides and `{and}` supplies a brace on the left.
  assert.deepEqual(parseAuthors('Rutz, Adriano and {and} Orr'), ['Rutz, Adriano', 'and Orr']);
});

test('an article renders author, year, title, journal and DOI', () => {
  const rendered = renderReference(
    entry(
      '@article{k, author = {Rutz, Adriano}, year = {2024}, title = {A small study}, ' +
        'journal = {Journal of Testing}, volume = {3}, doi = {10.1234/abc}}',
    ),
  );

  assert.match(rendered, /^Rutz, Adriano\. 2024\./);
  assert.match(rendered, /“A Small Study\.”/);
  assert.match(rendered, /<em class="csl-journal">Journal of Testing<\/em> 3\./);
  assert.match(rendered, /https:\/\/doi\.org\/10\.1234\/abc/);
});

test('a containerless entry puts its title in the italic container slot', () => {
  const rendered = renderReference(
    entry('@misc{k, author = {Rutz, Adriano}, year = {2024}, title = {A preprint}, publisher = {bioRxiv}}'),
  );
  assert.match(rendered, /<em class="csl-title">A Preprint\.<\/em>/);
});

test('page ranges elide the shared leading digits', () => {
  // The comparison is against what renderReference produces for 647--656
  // versus 647--700, which share a different number of leading digits.
  const elided = renderReference(
    entry('@inproceedings{k, author = {Rutz, Adriano}, year = {2024}, booktitle = {Proc}, pages = {647--656}}'),
  );
  const notElided = renderReference(
    entry('@inproceedings{k, author = {Rutz, Adriano}, year = {2024}, booktitle = {Proc}, pages = {647--700}}'),
  );

  assert.match(elided, /647–56/);
  assert.match(notElided, /647–700/);
});

test('every entry in the real .bib renders without an empty string', () => {
  for (const [key, value] of bib) {
    const rendered = renderReference(value);
    assert.ok(rendered.trim().length > 0, `${key} rendered empty`);
    assert.doesNotMatch(rendered, /undefined|NaN|\[object/, `${key} leaked a placeholder`);
  }
});
