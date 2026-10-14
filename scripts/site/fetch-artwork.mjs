/**
 * Caches article and varia artwork locally.
 *
 * Those images are declared in the Quarto sources as absolute URLs on
 * Wikimedia, GitHub raw, arXiv's CDN and publisher sites. Hotlinking them means
 * page loads trigger requests to unrelated third parties, including one source
 * serving a 690 KB GIF, and Lighthouse rightly dings the pages for third-party
 * cookies.
 *
 * So the files are fetched once at build time into public/images/artwork/ and
 * the templates prefer the local copy. Falls back to the remote URL when the
 * fetch failed or has not run, so an offline build still produces a working
 * page rather than a broken image.
 *
 * Writes public/images/artwork/manifest.json, read by the `artwork` filter.
 *
 * Run: node scripts/site/fetch-artwork.mjs
 */
import { createHash } from 'node:crypto';
import {
  existsSync,
  mkdirSync,
  mkdtempSync,
  readFileSync,
  readdirSync,
  rmSync,
  statSync,
  unlinkSync,
  writeFileSync,
} from 'node:fs';
import { dirname, extname, join } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const CONTENT = join(ROOT, 'src', 'content');
const OUT = join(ROOT, 'public', 'images', 'artwork');
const MANIFEST = join(OUT, 'manifest.json');
const THUMBNAILS = join(OUT, 'thumbnails.json');

/** Only these are cached; anything else is not ours to mirror. */
const CACHEABLE = /^https:\/\/(upload\.wikimedia\.org|raw\.githubusercontent\.com|ars\.els-cdn\.com|media\.springernature\.com|pharma\.unibas\.ch)\//;

/**
 * Trims a vector file to the precision the page actually needs.
 *
 * The artwork is exported from Illustrator and Inkscape at full precision: a
 * 56-path logo comes to 540 KB because every coordinate carries a dozen
 * significant figures. Rendered into a 350px-wide box, all of that is below a
 * device pixel. Rounding path coordinates to one decimal cuts the file roughly
 * in half with no visible difference, and it is the only reduction available
 * without adding a rasteriser as a build dependency.
 *
 * Only `d` attributes on <path> are touched. Transforms, gradients and ids are
 * left exactly as they were, because rounding those is where this kind of
 * optimisation quietly breaks an image.
 */
/**
 * SVGs are cached byte for byte as downloaded.
 *
 * This used to round every number in a <path d> to a fixed number of decimals,
 * which is a real saving and quietly corrupts artwork. Rounding perturbs each
 * vertex independently, and the outlines here are traced glyphs and text-as-
 * paths: a perturbed outline self-intersects, and the default nonzero fill rule
 * then paints the interior solid. The TIMA logo lost its lettering to black
 * blobs, and the LOTUS and Wikidata marks went with it.
 *
 * Making the precision depend on the viewBox did not rescue it either — it only
 * moved the damage. Anything that rewrites path data has this failure mode, so
 * the coordinates are left exactly as authored.
 *
 * There is little left to reclaim: these files are already minified, and their
 * comments are worth well under 1% of their size. The honest trade is a larger
 * file, not a mangled logo. Rasterising would shrink them further but needs a
 * native dependency, and would lose the scaling these are used at.
 */
function keepSvg(source) {
  return { text: source, saved: 0 };
}

const contentFiles = [];
for (const section of ['articles', 'varia']) {
  const dir = join(CONTENT, section);
  if (!existsSync(dir)) continue;
  const walk = (d) => {
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      const path = join(d, entry.name);
      if (entry.isDirectory()) walk(path);
      else if (path.endsWith('.md')) contentFiles.push(path);
    }
  };
  walk(dir);
}

const urls = new Set();
const thumbnailUrls = new Set();
for (const file of contentFiles) {
  const image = readFileSync(file, 'utf-8').match(/^image:\s*"?([^"\n]+)"?\s*$/m)?.[1];
  if (image && CACHEABLE.test(image)) {
    urls.add(image);
    if (file.includes('/articles/') || file.includes('/varia/')) thumbnailUrls.add(image);
  }
}

mkdirSync(OUT, { recursive: true });

// Reuse a previous run's manifest so a failed fetch does not lose a good copy.
let manifest = {};
if (existsSync(MANIFEST)) {
  try {
    manifest = JSON.parse(readFileSync(MANIFEST, 'utf-8'));
  } catch {
    manifest = {};
  }
}
let thumbnails = {};
if (existsSync(THUMBNAILS)) {
  try {
    thumbnails = JSON.parse(readFileSync(THUMBNAILS, 'utf-8'));
  } catch {
    thumbnails = {};
  }
}

let fetched = 0;
let failed = 0;

for (const url of urls) {
  const stem = createHash('sha256').update(url).digest('hex').slice(0, 16);
  const extension = extname(new URL(url).pathname) || '.img';
  const cachedName = manifest[url]?.replace(/^\/images\/artwork\//, '');
  const cached = cachedName ? join(OUT, cachedName) : null;
  const needsRasterThumb = thumbnailUrls.has(url) && (
    extension === '.png'
    || (
      extension === '.svg'
      && (!cached || !existsSync(cached) || statSync(cached).size >= 100_000)
    )
  );
  const thumbnailName = `${stem}-thumb-320-fit.webp`;
  const cachedThumbnailName = thumbnails[url]?.replace(/^\/images\/artwork\//, '');
  const hasThumbnail = cachedThumbnailName === thumbnailName
    && existsSync(join(OUT, thumbnailName));

  let buffer;
  if (
    cached
    && existsSync(cached)
    && (extension !== '.gif' || cachedName === `${stem}-thumb.webp`)
    && (!needsRasterThumb || hasThumbnail)
  ) {
    continue;
  }
  if (needsRasterThumb && !hasThumbnail) delete thumbnails[url];
  if (
    cached
    && existsSync(cached)
    && (extname(cached) === '.gif' || needsRasterThumb)
  ) {
    buffer = readFileSync(cached);
  } else {
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(30_000) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      buffer = Buffer.from(await response.arrayBuffer());
    } catch (error) {
      failed++;
      console.log(`  ! could not cache ${url}: ${error.message}`);
      delete manifest[url];
      continue;
    }
  }

  let name = `${stem}${extension}`;
  try {
    if (name.endsWith('.svg')) {
      buffer = Buffer.from(keepSvg(buffer.toString('utf-8')).text, 'utf-8');
      if (needsRasterThumb) {
        const temporaryDirectory = mkdtempSync(join(tmpdir(), 'site-artwork-'));
        const source = join(temporaryDirectory, `${stem}.svg`);
        const thumbnail = join(OUT, thumbnailName);
        try {
          writeFileSync(source, buffer);
          const result = spawnSync(
            'uv',
            ['run', 'python', 'scripts/site/optimize_artwork.py', source, thumbnail],
            { cwd: ROOT, encoding: 'utf-8' },
          );
          if (result.error) throw result.error;
          if (result.status === 0) {
            thumbnails[url] = `/images/artwork/${thumbnailName}`;
          } else if (result.status !== 2) {
            throw new Error(`Artwork thumbnail generation failed: ${result.stderr || result.status}`);
          } else if (buffer.length >= 100_000) {
            console.log(`  = kept original SVG (rsvg-convert unavailable): ${url}`);
          }
        } finally {
          rmSync(temporaryDirectory, { recursive: true, force: true });
        }
      }
    } else if (extension === '.png' && needsRasterThumb) {
      const temporaryDirectory = mkdtempSync(join(tmpdir(), 'site-artwork-'));
      const source = join(temporaryDirectory, `${stem}.png`);
      const thumbnail = join(OUT, thumbnailName);
      try {
        writeFileSync(source, buffer);
        const result = spawnSync(
          'uv',
          ['run', 'python', 'scripts/site/optimize_artwork.py', source, thumbnail],
          { cwd: ROOT, encoding: 'utf-8' },
        );
        if (result.error) throw result.error;
        if (result.status === 0) {
          thumbnails[url] = `/images/artwork/${thumbnailName}`;
        } else if (result.status !== 2) {
          throw new Error(`Artwork thumbnail generation failed: ${result.stderr || result.status}`);
        } else {
          console.log(`  = kept original PNG (no smaller WebP preview): ${url}`);
        }
      } finally {
        rmSync(temporaryDirectory, { recursive: true, force: true });
      }
    } else if (extension === '.gif') {
      const temporaryDirectory = mkdtempSync(join(tmpdir(), 'site-artwork-'));
      const source = join(temporaryDirectory, `${stem}.gif`);
      const optimizedName = `${stem}-thumb.webp`;
      const optimized = join(OUT, optimizedName);
      try {
        writeFileSync(source, buffer);
        const result = spawnSync(
          'uv',
          ['run', 'python', 'scripts/site/optimize_artwork.py', source, optimized],
          { cwd: ROOT, encoding: 'utf-8' },
        );
        if (result.error) throw result.error;
        if (result.status === 0) {
          name = optimizedName;
        } else if (result.status !== 2) {
          throw new Error(`GIF optimization failed: ${result.stderr || result.status}`);
        } else {
          console.log(`  = kept original GIF (animated or cwebp unavailable): ${url}`);
        }
        if (cached && cached !== join(OUT, name) && existsSync(cached)) unlinkSync(cached);
      } finally {
        rmSync(temporaryDirectory, { recursive: true, force: true });
      }
    }

    if (name.endsWith('.gif')) writeFileSync(join(OUT, name), buffer);
    else if (!name.endsWith('.webp')) writeFileSync(join(OUT, name), buffer);

    manifest[url] = `/images/artwork/${name}`;
    fetched++;
    console.log(`  + ${name} (${Math.round(statSync(join(OUT, name)).size / 1024)} KB) <- ${url}`);
  } catch (error) {
    throw new Error(`Could not store artwork ${url}: ${error.message}`, { cause: error });
  }
}

writeFileSync(MANIFEST, `${JSON.stringify(manifest, null, 2)}\n`, 'utf-8');
writeFileSync(THUMBNAILS, `${JSON.stringify(thumbnails, null, 2)}\n`, 'utf-8');
console.log(`  artwork: ${Object.keys(manifest).length} cached (${fetched} new, ${failed} failed)`);
