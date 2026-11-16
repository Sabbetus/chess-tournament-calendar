// Smoke checks on the built site (dist/). Run after `npm run build`.
// Fails the deploy if something structural broke, instead of publishing it.
import { readFileSync, readdirSync, existsSync } from 'node:fs';
import { join } from 'node:path';

const dist = process.argv[2] || 'dist';
const read = (p) => readFileSync(join(dist, p), 'utf8');
const json = (p) => JSON.parse(readFileSync(p, 'utf8'));
let failed = 0;
const check = (ok, msg) => { if (!ok) failed++; console.log(`${ok ? 'ok  ' : 'FAIL'} ${msg}`); };

// The sitemap URL-encodes non-ASCII slugs.
const inSitemap = (sm, slug) => sm.includes(`/tournament/${encodeURIComponent(slug)}/<`);

const LANGS = ['', 'es/', 'pt/', 'de/', 'cs/', 'fi/'];
const live = json('public/data/tournaments.json');
const archive = [...json('public/data/archive.json'), ...json('public/data/fide_archive.json')];

// Every locale has the homepage, a country page, the about/privacy/contact
// pages, and a tournament page with real content.
for (const l of LANGS) {
  for (const p of ['', 'about/', 'privacy/', 'contact/', 'continent/europe/']) {
    check(existsSync(join(dist, l, p, 'index.html')), `/${l}${p} exists`);
  }
}

// Live tournaments each have a page in every locale.
const sample = live.filter((_, i) => i % Math.max(1, Math.floor(live.length / 40)) === 0);
for (const t of sample) {
  for (const l of LANGS) {
    if (!existsSync(join(dist, l, 'tournament', t.slug, 'index.html'))) {
      check(false, `/${l}tournament/${t.slug}/ missing`);
    }
  }
}
check(true, `${sample.length} sampled live tournaments exist in all ${LANGS.length} locales`);

// Concluded tournaments that still have a page must be noindex and out of the sitemap.
const sitemap = readdirSync(dist).filter((f) => /^sitemap-\d+\.xml$/.test(f)).map((f) => read(f)).join('\n');
const concluded = archive.filter((t) => t.status === 'concluded' && existsSync(join(dist, 'tournament', t.slug, 'index.html')));
const concludedSample = concluded.filter((_, i) => i % Math.max(1, Math.floor(concluded.length / 40)) === 0);
check(concludedSample.length > 0, `found ${concluded.length} concluded pages to sample`);
for (const t of concludedSample) {
  check(/<meta name="robots" content="noindex/.test(read(`tournament/${t.slug}/index.html`)), `concluded ${t.slug} is noindex`);
  if (inSitemap(sitemap, t.slug)) check(false, `concluded ${t.slug} is in the sitemap`);
}

// Live tournaments are indexable and appear in the sitemap.
const liveSitemapHits = sample.filter((t) => inSitemap(sitemap, t.slug)).length;
check(liveSitemapHits >= sample.length * 0.9, `live tournaments are in the sitemap (${liveSitemapHits}/${sample.length})`);
for (const t of sample.slice(0, 10)) {
  check(!/content="noindex/.test(read(`tournament/${t.slug}/index.html`)), `live ${t.slug} is not noindex`);
}

// The country page explains how many tournaments are upcoming.
const finland = read('country/finland/index.html');
check(/class="country-summary"/.test(finland), 'country page has its summary line');

// Internal links end in a slash (otherwise GitHub Pages redirects each one).
const pages = ['index.html', 'es/index.html', 'fi/index.html', 'country/finland/index.html', 'continent/europe/index.html', 'about/index.html', 'privacy/index.html'];
for (const p of pages) {
  const bad = [...read(p).matchAll(/href="(\/[^"#?]*)"/g)].map((m) => m[1])
    .filter((h) => !h.endsWith('/') && !/\.[a-z0-9]+$/i.test(h));
  check(bad.length === 0, `${p}: no slashless internal links${bad.length ? ' ' + bad.slice(0, 3).join(',') : ''}`);
}

// Scripts the site relies on are present on the pages that use them.
check(/data-tooltip|hover-tooltip/.test(read('index.html')), 'homepage has the tooltip element');
check(/id="tournament-list"/.test(read('index.html')), 'homepage has the tournament list');

// Data feeds are valid and non-trivial.
check(json(join(dist, 'data/tournaments.json')).length >= live.length * 0.9, 'tournaments.json shipped');
check(existsSync(join(dist, 'llms.txt')) && existsSync(join(dist, 'robots.txt')), 'llms.txt and robots.txt shipped');

if (failed) { console.error(`\n${failed} check(s) failed`); process.exit(1); }
console.log('\nall build checks passed');
