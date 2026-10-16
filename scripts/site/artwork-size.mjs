/**
 * Records the intrinsic size of every cached artwork file.
 *
 * The varia cards render one artwork each, and the artwork is a mix of wide
 * logos, square app icons and tall diagrams. Every one of them was being given
 * the same 576x324 box, which is a shape none of them actually is: a square logo
 * in a 16:9 box is letterboxed into a wide band of empty background, and reads
 * as an image that failed to load rather than one that loaded correctly.
 *
 * So the size is measured here, from the file, and rendered onto the <img> as
 * the real width and height. That keeps the browser's layout reservation honest
 * and lets the card take the shape of the artwork instead of forcing the
 * artwork into a shape of the card's.
 *
 * Writes public/images/artwork/sizes.json, read by the `artworkSize` filter.
 * Measured from the files on disk every run, never from a previous record, so
 * an edited or re-fetched image cannot keep a stale size.
 */
import { existsSync, readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const OUT = 'public/images/artwork';
const SIZES = join(OUT, 'sizes.json');

/** Lengths inside an SVG can carry a unit; CSS absolute units all resolve against 96dpi. */
const UNITS = { '': 1, px: 1, pt: 96 / 72, pc: 16, in: 96, cm: 96 / 2.54, mm: 96 / 25.4 };

/**
 * The intrinsic size of an SVG.
 *
 * The viewBox is preferred over width/height: it is the coordinate system the
 * artwork is actually drawn in, so it is the ratio that survives resizing.
 * width/height are only consulted when there is no viewBox, and then only when
 * they are absolute lengths — a percentage width describes no fixed shape.
 */
function svgSize(buffer) {
  const text = buffer.toString('utf-8', 0, 4096);
  const root = /<svg\b[^>]*>/i.exec(text);
  if (!root) return null;
  const tag = root[0];

  const attr = (name) => {
    const m = new RegExp(`\\b${name}\\s*=\\s*["']([^"']*)["']`, 'i').exec(tag);
    return m ? m[1].trim() : null;
  };

  const viewBox = attr('viewBox');
  if (viewBox) {
    const parts = viewBox.split(/[\s,]+/).map(Number);
    if (parts.length === 4 && parts[2] > 0 && parts[3] > 0) {
      return { width: Math.round(parts[2]), height: Math.round(parts[3]) };
    }
  }

  const absolute = (value) => {
    if (!value) return null;
    const m = /^(-?[\d.]+)\s*([a-z%]*)$/i.exec(value);
    if (!m) return null;
    const unit = m[2].toLowerCase();
    if (!(unit in UNITS)) return null; // percentages and keywords: no fixed size
    return Number(m[1]) * UNITS[unit];
  };

  const width = absolute(attr('width'));
  const height = absolute(attr('height'));
  if (width > 0 && height > 0) return { width: Math.round(width), height: Math.round(height) };
  return null;
}

/**
 * The intrinsic size of a PNG, from the IHDR chunk.
 *
 * IHDR is always the first chunk and always 13 bytes, so this needs no image
 * library and no decode — just the header. Width and height are big-endian
 * uint32 at offsets 16 and 20.
 */
function pngSize(buffer) {
  const signature = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
  if (buffer.length < 24 || !buffer.subarray(0, 8).equals(signature)) return null;
  if (buffer.toString('ascii', 12, 16) !== 'IHDR') return null;
  return { width: buffer.readUInt32BE(16), height: buffer.readUInt32BE(20) };
}

/** Intrinsic dimensions for the lossy VP8 files emitted by cwebp. */
function webpSize(buffer) {
  if (buffer.toString('ascii', 0, 4) !== 'RIFF' || buffer.toString('ascii', 8, 12) !== 'WEBP') return null;
  let offset = 12;
  while (offset + 18 <= buffer.length) {
    const type = buffer.toString('ascii', offset, offset + 4);
    const length = buffer.readUInt32LE(offset + 4);
    const data = offset + 8;
    if (
      type === 'VP8 '
      && buffer[data + 3] === 0x9d
      && buffer[data + 4] === 0x01
      && buffer[data + 5] === 0x2a
    ) {
      return {
        width: buffer.readUInt16LE(data + 6) & 0x3fff,
        height: buffer.readUInt16LE(data + 8) & 0x3fff,
      };
    }
    offset = data + length + (length % 2);
  }
  return null;
}

const sizes = {};
let measured = 0;
let unmeasured = 0;

if (!existsSync(OUT)) {
  console.error(`  ! ${OUT} does not exist; run scripts/site/fetch-artwork.mjs first`);
  process.exit(1);
}

// Sorted so sizes.json has a stable key order across machines: the readdir
// order it would otherwise inherit is filesystem-dependent.
for (const name of readdirSync(OUT).sort()) {
  const lower = name.toLowerCase();
  const path = join(OUT, name);
  if (lower.endsWith('.json')) continue;
  let size = null;
  try {
    const buffer = readFileSync(path);
    size = lower.endsWith('.svg')
      ? svgSize(buffer)
      : lower.endsWith('.png')
        ? pngSize(buffer)
        : lower.endsWith('.webp')
          ? webpSize(buffer)
          : null;
  } catch {
    size = null;
  }
  if (size) {
    sizes[name] = size;
    measured++;
  } else {
    unmeasured++;
    console.log(`  ? no intrinsic size measured for ${name}`);
  }
}

writeFileSync(SIZES, `${JSON.stringify(sizes, null, 2)}\n`, 'utf-8');
console.log(`  artwork sizes: ${measured} measured${unmeasured ? `, ${unmeasured} unmeasured` : ''}`);
