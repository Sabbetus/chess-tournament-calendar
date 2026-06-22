import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { readFileSync } from 'node:fs';

// Concluded tournaments are noindex'd and excluded from the sitemap — they are
// thin, stale pages (no results/standings) that would only dilute crawl budget.
const archive = JSON.parse(readFileSync(new URL('./public/data/archive.json', import.meta.url)));
const concludedSlugs = new Set(
  archive.filter((t) => t.status === 'concluded').map((t) => t.slug)
);

// Use the data refresh time as the sitemap lastmod for every page.
const meta = JSON.parse(readFileSync(new URL('./public/data/meta.json', import.meta.url)));
const lastmod = new Date(meta.lastUpdated).toISOString();

export default defineConfig({
  site: 'https://chesstournamentcalendar.com',
  base: '/',
  output: 'static',
  integrations: [
    sitemap({
      filter: (page) => {
        const m = page.match(/\/tournament\/([^/]+)\/?$/);
        if (!m) return true;
        return !concludedSlugs.has(decodeURIComponent(m[1]));
      },
      serialize: (item) => {
        item.lastmod = lastmod;
        return item;
      },
    }),
  ],
});
