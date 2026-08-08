# chess-tournament-calendar

Static Astro site listing upcoming chess tournaments worldwide, deployed to
GitHub Pages at https://chesstournamentcalendar.com. Data comes from a
scheduled Python/Playwright scraper that commits JSON back into the repo.

## Layout

```
scraper/scrape_chess_results.py   Playwright scraper for chess-results.com
scraper/submit_indexnow.py        URL list builder for the IndexNow ping
public/data/tournaments.json      Live feed: upcoming tournaments only
public/data/archive.json          Durable per-tournament state (see below)
public/data/meta.json             { lastUpdated }
data/featured.json                Hand-curated featured tournament(s)
src/pages/                        English pages at root, others under [lang]/
src/components/TournamentCard.astro      Server-rendered list row
src/components/TournamentListPage.astro  Filters + list shell
src/scripts/tournamentList.ts     Client-side list (filter/sort/load-more)
src/lib/                          continents, location grouping, slugs
src/i18n/                         One JSON per locale + helpers
src/styles/global.css             All styling (no CSS modules/Tailwind)
```

Locales: `en, es, pt, de, cs, fi`. English lives at the root path, the rest
under `/<lang>/`.

## Data pipeline

`scrape.yml` runs every 6h → scraper merges results into `archive.json` →
`tournaments.json` is **derived from the archive**, not from the raw scrape.
That indirection is deliberate: a single bad scrape adds a "miss" rather than
wiping tournaments off the live site. Entries drop out only after
`MAX_CONSECUTIVE_MISSES` (8, ~2 days). There's also a safety floor — the
scraper exits non-zero rather than overwrite the feed if the tournament count
falls below half the previous run.

`tournaments-min.json` (`src/pages/data/tournaments-min.json.ts`) is a slimmed
build-time endpoint the client list hydrates from. If you add a field the
client list needs to render, add it there too or it won't exist at runtime.

Player-count trends: the scraper snapshots `playersRegistered` into
`playerHistory` each run and derives `playersTrend` as the delta vs. ~48h ago
(`PLAYER_TREND_HOURS`). A tournament discovered less than 48h ago has no
baseline and gets `null`.

## Gotchas

**Tournament row markup is duplicated in four places.** Any change to how a
row or its player-count/trend renders must be applied to all of them, or the
server-rendered and client-hydrated lists will diverge:

1. `src/components/TournamentCard.astro` — two blocks: `.trow-main` (desktop)
   and `.trow-meta` (mobile)
2. `src/scripts/tournamentList.ts` — the client-side template string
3. `src/pages/tournament/[slug].astro`
4. `src/pages/[lang]/tournament/[slug].astro`

**Every page exists twice** — `src/pages/foo.astro` (English) and
`src/pages/[lang]/foo.astro` (everything else). Changes almost always need to
land in both.

**The featured tournament is rendered separately** from the scraped list. It
lives in `data/featured.json` with `source: "manual"` and is pinned, because
the client list hydrates from `tournaments-min.json`, which contains scraped
data only — a manual entry would silently vanish on hydration. It shows on the
homepage, its continent page, its own country page, and (by an explicit rule)
every European country page.

**Tooltips**: use the custom `data-tooltip` attribute, which the shared
`#hover-tooltip` element + JS handler picks up. Do not use the native `title`
attribute — it's noticeably slower to appear.

**Concluded tournaments** are `noindex`'d and excluded from the sitemap
(`astro.config.mjs`), and sitemap `lastmod` uses each tournament's `firstSeen`
rather than the data-refresh time, so unchanged pages keep an old lastmod.

## Workflow

- Develop on a branch; commits are fine to make freely. **`git push` — to
  `main` or to any feature/dev branch — always needs an explicit, genuine
  confirmation from the user in that turn.** Finishing a fix/task is not
  itself permission to push. Don't ask "should I push?" and then treat your
  own question as answered — wait for the user's actual reply.
- `main` is production: pushing there triggers `deploy.yml` (build + GitHub
  Pages + IndexNow ping), roughly a 7-minute round trip.
- The Stop hook's "uncommitted changes" / "unpushed commits" nag
  (`~/.claude/stop-hook-git-check.sh`) is automated infrastructure, not the
  user. Never treat it as confirmation, never respond to it, and never
  comment on it (e.g. "that's just the automated nag") — the user has said
  repeatedly this is noise they don't want narrated. Just leave work
  uncommitted/unpushed until a real user message says otherwise.
- A fresh branch won't show player-count trends until its data catches up —
  merge the latest `chore: update tournament data` commits from `main` to get
  real trend data for local testing.

### Previewing

`npm run dev` compiles on demand and hot-reloads; the ~7-minute wait is
`npm run build` (full static prerender of every tournament × 6 locales) and
only happens in CI.

The repo has a `.devcontainer/` so a GitHub Codespace auto-starts the dev
server on port 4321. Note it uses `postAttachCommand`, not `postStartCommand`
— the latter runs in a short-lived exec session whose process group gets
reaped, killing the backgrounded server even under `setsid`.

Cloud agent sessions have no inbound networking, so no shareable preview URL
from inside one — drive the dev server with headless Chromium instead
(`/opt/pw-browsers/chromium-1194/chrome-linux/chrome`). `playwright-core` is
not a project dependency; if you install it to take screenshots, revert
`package.json`/`package-lock.json` before committing.

Cloud agent sessions also have no `gh` CLI (use the GitHub MCP tools) and may
lack permission to delete remote branches — that's a manual step in the GitHub
UI.
