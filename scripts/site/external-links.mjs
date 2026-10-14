import { readdirSync, readFileSync, writeFileSync, statSync } from 'fs';
import { join } from 'path';

function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (p.endsWith('.html')) {
      let html = readFileSync(p, 'utf8');
      html = html.replace(/<a\b([^>]*?)href="(https?:\/\/[^"]+)"([^>]*?)>/g, (m, pre, url, post) => {
        let host;
        try { host = new URL(url).hostname; } catch { return m; }
        if (host === 'adafede.github.io' || host === 'localhost') return m;
        if (/target=/.test(m)) return m;
        return `<a${pre}href="${url}"${post} target="_blank" rel="noopener noreferrer">`;
      });
      writeFileSync(p, html);
    }
  }
}
walk('_eleventy_site');
