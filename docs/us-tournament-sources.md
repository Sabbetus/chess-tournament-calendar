# Sourcing US tournaments

Working notes on an open problem. Nothing here is implemented yet.

## The problem

Analytics put the US as the #2 traffic country (behind India, #1), but the site
lists essentially no US tournaments. Measured against the current data:

| | count |
|---|---|
| Archive entries total | 4,917 |
| Archive entries with `countryCode == "US"` | 2 |
| Top archive countries | IN 913, BR 471, ES 202, GB 157, CZ 132 |

So this is not a scraping bug. US organizers simply don't post to
chess-results.com — they use the US Chess Federation's own systems. It's a
**sourcing** gap, and it needs a different source rather than a fix to the
existing scraper.

## What's off the table

**Scraping uschess.org is not an option.** The site is behind Cloudflare bot
protection, and working around that is circumventing a deliberate access
control — we're not doing it. Independently of that, it would also be a bad
engineering bet here:

- The scraper runs on GitHub Actions, i.e. Azure datacenter IP ranges, which
  are the most aggressively challenged address space there is.
- The scraper uses stock Playwright, which has well-known automation
  fingerprints. Anything that actually held up would need residential proxies
  and fingerprint spoofing — a permanent arms race, not a one-time build.
- This site has a real domain, brand, and commercial intent, which is exactly
  the profile where a ToS violation turns into a letter.

A secondary problem noted separately: US Chess's search results don't carry
enough detail anyway, so it would also require fetching each tournament's own
page.

## Candidate: FIDE rated-tournaments listing

`https://ratings.fide.com/rated_tournaments.phtml?country=USA`

FIDE's ratings site is public and has no bot protection, so it's a legitimate
source. Two things make it uncertain as a *calendar* feed:

### Open questions (resolve before building anything)

1. **Are the listed events past or upcoming?** The endpoint name suggests it
   reports tournaments already submitted and processed for rating — i.e.
   completed events. If so it's the wrong end of the timeline for an
   upcoming-events calendar, and no amount of link-matching fixes that.
2. **Is a FIDE tournament ID or link column present?** If yes, each event has a
   canonical FIDE URL and the "nowhere to link to" problem dissolves without
   touching uschess.org at all. This is the single highest-value thing to check.

### Known ceilings regardless

- **FIDE-rated is a subset of US chess.** Most weekend swisses, club events,
  and scholastics are US Chess rated but never FIDE rated. Coverage would skew
  to larger norm-eligible events. That may be acceptable — those are the events
  people travel for — but it caps the ceiling.
- **Linking to US Chess would be unverifiable.** Matching a FIDE record to a
  US Chess page is fuzzy record linkage (names drift, dates shift a day), and
  we can't validate that a generated URL resolves without fetching the site we
  can't reach. Publishing unverified outbound links at scale is worse than
  publishing no US listings — bad for users, and dead links hurt the SEO this
  is all in service of.

## Candidate: organizer submissions (recommended)

Let organizers submit their own tournaments. This is the route that solves all
three problems at once — upcoming dates, a canonical registration link, and
explicit permission — and it converts the hardest scraping target into inbound
content.

Why it fits here:

- US chess is organizer-driven: CCA/Continental Chess, Saint Louis Chess Club,
  Marshall, Charlotte Chess Center, plus ~50 state affiliates. They all want
  free promotion.
- **The data model already supports it.** `source` is a first-class field, and
  `data/featured.json` already uses `source: "manual"` with the country and
  continent pages filtering on it. The manual-entry path is half-built.
- Unique, non-scraped content is good for SEO, and it's a community hook.

Open design questions: submission mechanism (form → GitHub issue/PR vs. hosted
form → data pipeline), review/approval step, and spam handling.

## Other sources not yet explored

- **State affiliate sites** — ~50 separate calendars, mostly simple CMSes with
  no bot protection, many publishing iCal or RSS specifically for consumption.
- **Major organizers' own calendar feeds** — a handful of clubs account for a
  large share of significant US events; some publish iCal meant for syndication.
- **Asking US Chess directly** — cheapest unexplored option. A free calendar
  that drives entries to their events is aligned with their mission. Ask about
  a data feed, API, or partnership. Worst case is a no.

## Suggested sequencing

1. Answer the two open questions about the FIDE listing. Cheap, and decides
   whether there's a data source here at all.
2. If the FIDE data is retrospective-only, it's still valuable as a
   **prospecting list** — US FIDE-rated events are overwhelmingly annual with
   recurring organizers, giving a ranked roster of exactly who to invite to
   submit.
3. Build the submission pipeline; use (2) as the outreach target list.
4. Email US Chess in parallel — it costs a day and could moot the rest.
