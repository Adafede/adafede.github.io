/**
 * Minimal BibTeX reader, just enough to render author/year/title/venue/DOI.
 * Quarto used pandoc-citeproc with the CSL files in the repo root; this is a
 * deliberate simplification so the Eleventy build stays dependency-light.
 */
/** `@article{Rutz2022,` -> key `Rutz2022`, type `article`. */
function* iterateEntries(bib) {
    const entryRe = /@(\w+)\s*\{\s*([^,]+),/g;
    let match;
    while ((match = entryRe.exec(bib))) {
        const type = match[1].toLowerCase();
        const key = match[2].trim();
        const fields = {};
        // Scan forward balancing braces so nested values survive.
        let depth = 1;
        let i = match.index + match[0].length;
        let inQuote = false;
        const start = i;
        while (i < bib.length && depth > 0) {
            const ch = bib[i];
            if (ch === '"' && bib[i - 1] !== '\\')
                inQuote = !inQuote;
            if (!inQuote) {
                if (ch === '{')
                    depth++;
                else if (ch === '}')
                    depth--;
            }
            i++;
        }
        const body = bib.slice(start, i - 1);
        for (const [name, value] of parseFields(body))
            fields[name] = value;
        yield { key, type, fields };
    }
}
function parseFields(body) {
    const out = [];
    // BibTeX values come in four shapes: braced {…}, quoted "…", a bare number,
    // and a bare word (e.g. `month = may`). All four appear in these files.
    const fieldRe = /(\w[\w-]*)\s*=\s*(\{(?:[^{}]|\{[^{}]*\})*\}|"[^"]*"|\d+|[A-Za-z][\w.-]*)\s*,?/g;
    let m;
    while ((m = fieldRe.exec(body))) {
        out.push([m[1].toLowerCase(), unwrap(m[2])]);
    }
    return out;
}
function unwrap(value) {
    const trimmed = value.trim();
    if (trimmed.startsWith('{') && trimmed.endsWith('}'))
        return trimmed.slice(1, -1);
    if (trimmed.startsWith('"'))
        return trimmed.slice(1, -1);
    return trimmed;
}
const ACCENTS = {
    '"': 'diaeresis', "'": 'acute', '`': 'grave', '^': 'circumflex',
    '~': 'tilde', '=': 'macron', '.': 'dotaccent', 'c': 'caron',
    'v': 'caron', 'u': 'breve', 'H': 'doubleacute', 'k': 'ogonek',
    'r': 'ring', 'd': 'stroke',
};
/** `{\"o}` -> `ö`, `{\v r}` -> `ř`, drop the remaining TeX braces. */
export function detex(input) {
    return (input
        // braced accent: \", \', \v{...}, or the { \"o } form
        .replace(/\\(["'`^~=.])\s*\{?\\?([A-Za-z])\}?/g, (m, acc, ch) => compose(ACCENTS[acc], ch) ?? m)
        .replace(/\\([cvurHkd])\s*\{([A-Za-z])\}/g, (m, acc, ch) => compose(ACCENTS[acc], ch) ?? m)
        .replace(/\\&/g, '&')
        .replace(/\\[a-zA-Z]+\s*/g, '')
        .replace(/[{}]/g, '')
        .replace(/\s+/g, ' ')
        .trim());
}
const COMBINING = {
    diaeresis: '̈', acute: '́', grave: '̀', circumflex: '̂',
    tilde: '̃', macron: '̄', dotaccent: '̇', caron: '̌',
    breve: '̆', doubleacute: '̋', ogonek: '̨', ring: '̊', stroke: '̸',
};
function compose(kind, ch) {
    const mark = kind ? COMBINING[kind] : undefined;
    // Compose the base + mark and then normalise to NFC, so "o" + U+0308 becomes
    // the single precomposed "ö" (U+00F6). Without this the rendered text differs
    // from Quarto's by code point even though it looks identical.
    return mark ? (ch + mark).normalize('NFC') : null;
}
export function parseAuthors(value) {
    if (!value)
        return [];
    return value
        .split(/\s+and\s+/i)
        .map((name) => detex(name))
        .filter(Boolean);
}
/** Family name only — enough for CSL-ish "Rutz et al. 2022". */
function familyName(author) {
    if (author.includes(','))
        return author.split(',')[0].trim();
    const parts = author.split(' ');
    return parts.length > 1 ? `${parts[parts.length - 1]}` : author;
}
export function inlineCitation(entry) {
    if (!entry)
        return '???';
    const authors = parseAuthors(entry.fields.author ?? '');
    const year = detex(entry.fields.year ?? '').slice(0, 4) || 'n.d.';
    if (!authors.length)
        return year;
    const [first, second] = authors.map(familyName);
    if (authors.length === 1)
        return `${first} ${year}`;
    if (authors.length === 2)
        return `${first} and ${second} ${year}`;
    return `${first} et al. ${year}`;
}
/**
 * Author list, following springer-basic-brackets.csl:
 * first author family-first and the rest
 * given-first, Oxford comma (`delimiter-precedes-last="always"`).
 *
 * The numeric CSLs truncate at five; Quarto's output lists three then "et al."
 * for Rutz2022 and lists all five for Willighagen2025b.
 */
// Calibrated against Quarto's actual output: fifteen authors rendered as
// "first, second, third, et al.", five authors rendered in full.
const ET_AL_MIN = 6;
const ET_AL_USE_FIRST = 3;
function formatAuthors(authors) {
    if (!authors.length)
        return '';
    const [first, ...rest] = authors;
    /** "Csefalvay, Chris" -> "Chris Csefalvay". */
    const givenFirst = (name) => {
        const [family, given] = name.includes(',') ? name.split(',').map((p) => p.trim()) : [name, ''];
        return given ? `${given} ${family}` : family;
    };
    /**
     * Nobility particles read as a suffix in an English-language reference:
     * "von Csefalvay" is rendered "Csefalvay, Chris von". The .bib stores this
     * author given-first ("von Csefalvay, Chris") while every other entry stores
     * family-first, so the particle is moved to keep the lead consistent.
     */
    const demoteParticle = (name) => {
        const [family = '', given = ''] = name.split(',').map((p) => p.trim());
        const particle = family.match(/^(van|von|de|del|della|di|da|le|la)\s+/i)?.[1];
        if (!particle || !given)
            return name;
        return `${family.slice(particle.length).trim()}, ${given} ${particle}`;
    };
    // The first author stays family-first; the rest flip to given-first.
    // A single author keeps the bare family-first form Quarto emits
    // ("Csefalvay, Chris von"); with co-authors it reads "Csefalvay, Chris von, and X".
    // A lone author is emitted given-first, as Quarto does for the injected
    // self-citation ("Adriano Rutz. 2026."). With co-authors the lead becomes
    // family-first ("Bast, Hannah, and ...").
    const leadText = rest.length === 0 && !first.includes(',')
        ? first
        : first;
    const parts = rest.length > 0 ? [leadText, ...rest.map(givenFirst).map(demoteParticle)] : [leadText];
    if (parts.length >= ET_AL_MIN) {
        return `${parts.slice(0, ET_AL_USE_FIRST).join(', ')}, et al.`;
    }
    if (parts.length === 1)
        return parts[0];
    return `${parts.slice(0, -1).join(', ')}, and ${parts[parts.length - 1]}`;
}
const MONTHS = [
    'january', 'february', 'march', 'april', 'may', 'june',
    'july', 'august', 'september', 'october', 'november', 'december',
];
/**
 * BibTeX months are three-letter abbreviations (`month = nov`) or bare numbers;
 * these files also carry full names. Map any of them to the full name, which
 * is what the CSL renders.
 */
const MONTH_ABBREVIATIONS = {
    jan: 'january', feb: 'february', mar: 'march', apr: 'april', may: 'may',
    jun: 'june', jul: 'july', aug: 'august', sep: 'september', oct: 'october',
    nov: 'november', dec: 'december',
};
/**
 * `may` -> `May`, `January 20` -> `January 20`, numeric months pass through.
 *
 * Both spellings occur: the shared .bib uses lowercase or numeric months, while
 * the synthesised self-citation uses "January 20".
 */
function monthName(raw) {
    const value = detex(raw);
    if (!value)
        return null;
    const named = value.toLowerCase().match(/^([a-z]+)/)?.[1] ?? '';
    const full = MONTH_ABBREVIATIONS[named] ?? named;
    const index = MONTHS.indexOf(full);
    if (index >= 0) {
        // Full month name, not the three-letter BibTeX abbreviation.
        const full = MONTHS[index][0].toUpperCase() + MONTHS[index].slice(1);
        const day = value.match(/\b(\d{1,2})\b/)?.[1];
        return day ? `${full} ${day}` : full;
    }
    if (/^\d{1,2}$/.test(value)) {
        const index = Number(value) - 1;
        return index >= 0 && index < MONTHS.length
            ? MONTHS[index][0].toUpperCase() + MONTHS[index].slice(1)
            : value;
    }
    return null;
}
/**
 * CSL title casing: capitalise each significant word, but leave acronyms
 * (all-caps) and their neighbours alone.
 *
 * Quarto's output title-cased the .bib values: "SPARQL+Text Search" became
 * "SPARQL+text Search" and "a lot is happening" became "A lot is happening".
 */
function titleCase(raw) {
    const SMALL = new Set([
        'a', 'an', 'and', 'as', 'at', 'but', 'by', 'for', 'from', 'in', 'into', 'nor',
        'of', 'on', 'or', 'over', 'per', 'the', 'to', 'up', 'via', 'with', 'yet',
    ]);
    const words = raw.split(/(\s+)/);
    // CSL capitalize-first also applies after a colon: "QLever: A Query Engine".
    // Indexed by word ordinal, not by position in `words` (which includes the
    // whitespace tokens), so both sets have to be counted the same way.
    const afterColon = new Set();
    let seenColon = true;
    let ordinal = 0;
    for (const w of words) {
        if (/^\s+$/.test(w))
            continue;
        if (seenColon)
            afterColon.add(ordinal);
        seenColon = /[:?+!]$/.test(w);
        ordinal++;
    }
    ordinal = 0;
    return words
        .map((word) => {
        if (/^\s+$/.test(word))
            return word;
        const index = ordinal++;
        const isFirst = index === 0;
        const isLast = index === words.filter((w) => !/^\s+$/.test(w)).length - 1;
        const force = afterColon.has(index);
        if (!isLast && !isFirst && !force && SMALL.has(word.toLowerCase())) {
            return word.toLowerCase();
        }
        // Hyphens join compound modifiers, and both halves are capitalised:
        // "small-molecule" -> "Small-Molecule". A "+" or "/" join instead marks a
        // new word that is not sentence-initial: "SPARQL+Text" -> "SPARQL+text".
        const cap = (chunk) => chunk.replace(/^([a-z])/, (c) => c.toUpperCase());
        return word
            .split('-')
            .map((part, i) => part
            .split(/([+/])/)
            .map((chunk, j) => {
            if (j % 2 === 1)
                return chunk;
            if (!chunk)
                return chunk;
            if (/^[A-Z0-9]{2,}$/.test(chunk))
                return chunk; // SPARQL, IUPAC
            if (j > 0)
                return chunk.toLowerCase(); // "SPARQL+text"
            // A small word after a hyphen stays lower case: "Blog-to-Blog".
            if (i > 0 && SMALL.has(chunk.toLowerCase()))
                return chunk.toLowerCase();
            return cap(chunk);
        })
            .join(''))
            .join('-');
    })
        .join('');
}
/**
 * Normalise a page range and apply CSL page-range elision:
 * `647--656` and `647–656` both become `647–56`.
 */
function pageRange(raw) {
    // Normalise every dash variant to an en dash, then elide.
    const text = detex(raw)
        .replace(/--+/g, '\u2013')
        .replace(/[\u2010\u2011\u2012\u2013\u2014\u2015]/g, '\u2013');
    return text.replace(/(\d+)\u2013(\d+)/g, (match, from, to) => {
        if (from.length !== to.length)
            return match;
        let shared = 0;
        while (shared < from.length && from[shared] === to[shared])
            shared++;
        // Elide whenever the two share a leading digit: 647-656 -> 647-56.
        return shared >= 1 && shared < from.length ? `${from}\u2013${to.slice(shared)}` : match;
    });
}
const escapeHtml = (value) => value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
/**
 * Render a reference the way the repository's Chicago author-date CSL does.
 *
 * This is not a general CSL processor: it covers the fields these .bib files
 * actually use (author, year, title, journal/booktitle, volume, number, pages,
 * publisher, doi, url, month) and omits anything outside that set.
 */
export function renderReference(entry, yearSuffix = '') {
    const f = (name) => detex(entry.fields[name] ?? '');
    const authors = parseAuthors(entry.fields.author ?? '');
    const year = f('year');
    const title = titleCase(f('title'));
    const doi = f('doi');
    const url = f('url');
    const journal = f('journal');
    const volume = f('volume');
    const issue = f('number') || f('issue');
    const pages = f('pages');
    const booktitle = f('booktitle');
    const publisher = f('publisher');
    const series = f('series');
    const month = monthName(entry.fields.month ?? '');
    // A containerless entry renders its title in the italic container slot.
    const containerless = !journal && !booktitle && Boolean(publisher);
    // @misc has neither container nor publisher: Quarto prints the title bare.
    const bare = entry.type === 'misc' && !journal && !booktitle && !publisher;
    const titleHtml = !title
        ? ''
        : containerless
            ? `<em class="csl-title">${escapeHtml(title)}.</em>`
            : bare
                ? `${escapeHtml(title)}.`
                : `“${escapeHtml(title)}.”`;
    const pieces = [];
    const add = (value) => {
        if (value)
            pieces.push(value);
    };
    // --- 1. author, year ------------------------------------------------
    const authorText = formatAuthors(authors);
    // A containerless entry has nothing to carry the date, so the month does.
    const authorLead = authorText.replace(/\.$/, '');
    const yearText = `${year}${yearSuffix}`;
    add(authorText ? `${authorLead}. ${yearText}.` : month ? `${escapeHtml(month)}. ${yearText}.` : `${yearText}.`);
    // --- 2. title --------------------------------------------------------
    if (title)
        add(titleHtml);
    // --- 3. container ----------------------------------------------------
    //
    // springer-basic-brackets.csl, as rendered by Quarto:
    //
    //   @article with journal   "Journal of Cheminformatics 13 (1)."
    //   @article with journal+vol and a month, as eLife does  "eLife 11 (May)."
    //   @inproceedings          "Proceedings of ..., CIKM '17, November, 647-56."
    //   @inbook                  "In Booktitle. Publisher."
    //   containerless preprint   "<title> May."
    if (journal) {
        const head = `<em class="csl-journal">${escapeHtml(journal)}</em>`;
        if (volume) {
            // The issue number wins; the month only fills the slot when there is no
            // issue (eLife publishes continuous article numbers, so "eLife 11 (May)").
            const parenthetical = issue || month;
            add(parenthetical
                ? `${head} ${escapeHtml(volume)} (${escapeHtml(parenthetical)}).`
                : `${head} ${escapeHtml(volume)}.`);
        }
        else {
            // No volume, but an issue number still qualifies the article.
            add(issue ? `${head} (${escapeHtml(issue)}).` : `${head}.`);
        }
    }
    else if (booktitle) {
        const isChapter = entry.type === 'inbook' || entry.type === 'incollection';
        const container = `<em class="csl-booktitle">${escapeHtml(booktitle)}</em>`;
        if (isChapter) {
            add(`In ${container}.`);
            if (publisher)
                add(`${escapeHtml(publisher)}.`);
        }
        else {
            // Proceedings: title, series, month, pages, publisher.
            add(`${container},`);
            const tail = [series, month, pageRange(pages)].filter(Boolean).join(', ');
            if (tail)
                add(`${escapeHtml(tail)}.`);
            else if (publisher)
                add(`${escapeHtml(publisher)}.`);
        }
    }
    else if (month && !bare) {
        // Nothing else to attach the month to. This CSL omits it for @misc.
        add(`${escapeHtml(month)}.`);
    }
    else if (publisher) {
        add(`${escapeHtml(publisher)}.`);
    }
    // --- 4. locator ------------------------------------------------------
    add(doi
        ? `<a href="https://doi.org/${escapeHtml(doi)}">https://doi.org/${escapeHtml(doi)}</a>.`
        : url
            ? `<a href="${escapeHtml(url)}">${escapeHtml(url)}</a>.`
            : '');
    return pieces.join(' ');
}
export function parseBib(bib) {
    const map = new Map();
    for (const entry of iterateEntries(bib))
        map.set(entry.key, entry);
    return map;
}
