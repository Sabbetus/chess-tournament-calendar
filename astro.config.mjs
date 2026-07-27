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

// Sections absorbed into another entry (scraper/scrape_chess_results.py's
// mark_merged_sections) keep their URL but must not compete with the entry
// they were merged into — 20 near-identical pages splitting the same search
// intent helps nobody. Astro emits these as meta-refresh pages in a static
// build, which is the closest a GitHub Pages site gets to a 301. They are also
// kept out of the sitemap below.
const LANGS = ['es', 'pt', 'de', 'cs', 'fi'];
const mergedSlugs = new Set(
  archive.filter((t) => t.mergedInto && t.slug).map((t) => t.slug)
);
const tournamentRedirects = Object.fromEntries(
  archive
    .filter((t) => t.mergedInto && t.slug)
    .flatMap((t) => [
      [`/tournament/${t.slug}`, `/tournament/${t.mergedInto}/`],
      ...LANGS.map((lang) => [
        `/${lang}/tournament/${t.slug}`,
        `/${lang}/tournament/${t.mergedInto}/`,
      ]),
    ])
);

export default defineConfig({
  site: 'https://chesstournamentcalendar.com',
  base: '/',
  output: 'static',
  redirects: tournamentRedirects,
  integrations: [
    sitemap({
      filter: (page) => {
        const m = page.match(/\/tournament\/([^/]+)\/?$/);
        if (!m) return true;
        const slug = decodeURIComponent(m[1]);
        return !concludedSlugs.has(slug) && !mergedSlugs.has(slug);
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
