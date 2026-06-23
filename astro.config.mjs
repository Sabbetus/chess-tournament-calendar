import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { readFileSync } from 'node:fs';

// Concluded tournaments are noindex'd and excluded from the sitemap — they are
// thin, stale pages (no results/standings) that would only dilute crawl budget.
const archive = JSON.parse(readFileSync(new URL('./public/data/archive.json', import.meta.url)));
const concludedSlugs = new Set(
  archive.filter((t) => t.status === 'concluded').map((t) => t.slug)
);

// Sitemap lastmod: tournament pages use the tournament's own "first seen" date
// (a stable, truthful published-on date that never churns), so an unchanged
// tournament keeps an old lastmod and Google deprioritises re-crawling it.
// Non-tournament pages (homepages, contact, etc.) fall back to the data refresh
// time, which is the best signal we have for those.
const meta = JSON.parse(readFileSync(new URL('./public/data/meta.json', import.meta.url)));
const lastmod = new Date(meta.lastUpdated).toISOString();

const firstSeenBySlug = new Map(
  archive
    .filter((t) => t.slug && t.firstSeen)
    .map((t) => [t.slug, new Date(t.firstSeen + 'T00:00:00Z').toISOString()])
);

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
        const m = item.url.match(/\/tournament\/([^/]+)\/?$/);
        const firstSeen = m && firstSeenBySlug.get(decodeURIComponent(m[1]));
        item.lastmod = firstSeen || lastmod;
        return item;
      },
    }),
  ],
});
