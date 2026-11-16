// How many scrapes in a row an upcoming tournament may be missing from its
// source before it stops being listed. Mirrors MAX_CONSECUTIVE_MISSES in the
// scrapers (scraper/scrape_chess_results.py, scraper/scrape_fide_ratings.py).
export const MAX_CONSECUTIVE_MISSES = 8;

// A tournament that is still in the future by date but has dropped out of the
// live feed because its source stopped listing it (cancelled or removed). Its
// page still exists for old links, but is noindex, out of the sitemap, and
// says so, rather than presenting it as a confirmed upcoming event.
export function isDelisted(tournament) {
  return tournament.status === 'upcoming'
    && (tournament.consecutiveMisses ?? 0) >= MAX_CONSECUTIVE_MISSES;
}
