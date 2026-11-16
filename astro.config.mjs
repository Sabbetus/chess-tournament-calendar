import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';
import { readFileSync } from 'node:fs';
import { retentionCutoff, isRetained } from './src/lib/retention.js';
import { isDelisted } from './src/lib/tournamentStatus.js';

// Concluded tournaments are noindex'd and excluded from the sitemap — they are
// thin, stale pages (no results/standings) that would only dilute crawl budget.
const archive = JSON.parse(readFileSync(new URL('./public/data/archive.json', import.meta.url)));
const fideArchive = JSON.parse(readFileSync(new URL('./public/data/fide_archive.json', import.meta.url)));
const concludedSlugs = new Set(
  [...archive, ...fideArchive].filter((t) => t.status === 'concluded').map((t) => t.slug)
);
// Same for tournaments their source no longer lists (see isDelisted).
const delistedSlugs = new Set(
  [...archive, ...fideArchive].filter(isDelisted).map((t) => t.slug)
);

// Sitemap lastmod: tournament pages use the tournament's own "first seen" date
// (a stable, truthful published-on date that never churns), so an unchanged
// tournament keeps an old lastmod and Google deprioritises re-crawling it.
// Non-tournament pages (homepages, contact, etc.) fall back to the data refresh
// time, which is the best signal we have for those.
const meta = JSON.parse(readFileSync(new URL('./public/data/meta.json', import.meta.url)));
const lastmod = new Date(meta.lastUpdated).toISOString();

// Slugs that still get a tournament page (see src/lib/retention.js). Redirects
// are only kept when both ends exist, otherwise they would send visitors to a
// page that is no longer built.
const cutoff = retentionCutoff(meta.lastUpdated);
const retainedSlugs = new Set(
  [...archive, ...fideArchive]
    .filter((t) => t.slug && isRetained(t, cutoff))
    .map((t) => t.slug)
);

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
const mergeRedirects = Object.fromEntries(
  archive
    .filter((t) => t.mergedInto && t.slug && retainedSlugs.has(t.slug) && retainedSlugs.has(t.mergedInto))
    .flatMap((t) => [
      [`/tournament/${t.slug}`, `/tournament/${t.mergedInto}/`],
      ...LANGS.map((lang) => [
        `/${lang}/tournament/${t.slug}`,
        `/${lang}/tournament/${t.mergedInto}/`,
      ]),
    ])
);

// One-time backfill for URLs broken before slugs were frozen at first-sight
// (scrape_chess_results.py's merge_into_archive no longer updates "slug" on a
// rename). Built from archive.json's git history — see the redirect-backfill
// discussion — mapping each slug a tournament used to have to the slug it has
// now. This map only grows if slugs are un-frozen again, so it's a fixed
// snapshot rather than something the scraper maintains.
const slugRedirects = JSON.parse(
  readFileSync(new URL('./public/data/slug_redirects.json', import.meta.url))
);
const historicalRedirects = Object.fromEntries(
  Object.entries(slugRedirects)
    .filter(([, newSlug]) => retainedSlugs.has(newSlug))
    .flatMap(([oldSlug, newSlug]) => [
    [`/tournament/${oldSlug}`, `/tournament/${newSlug}/`],
    ...LANGS.map((lang) => [
      `/${lang}/tournament/${oldSlug}`,
      `/${lang}/tournament/${newSlug}/`,
    ]),
  ])
);

// Merge redirects take priority: if a slug is both an old (pre-freeze) name
// and happened to also get absorbed into a merge, it must point at the merge
// survivor, not at whatever the archive shows for its own id.
const tournamentRedirects = { ...historicalRedirects, ...mergeRedirects };

export default defineConfig({
  site: 'https://chesstournamentcalendar.com',
  base: '/',
  output: 'static',
  // Astro 7 defaults to 'jsx', which drops whitespace between inline elements the way
  // React does; the templates rely on the HTML behavior ("Sources: <a>x</a> and <a>y</a>").
  compressHTML: true,
  // Astro 5+ inlines small scripts into every page; with 60k tournament pages that
  // adds ~100 MB to the published site, so keep them as shared cacheable files.
  vite: { build: { assetsInlineLimit: 0 } },
  redirects: tournamentRedirects,
  integrations: [
    sitemap({
      filter: (page) => {
        const m = page.match(/\/tournament\/([^/]+)\/?$/);
        if (!m) return true;
        const slug = decodeURIComponent(m[1]);
        return !concludedSlugs.has(slug) && !delistedSlugs.has(slug) && !mergedSlugs.has(slug);
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
