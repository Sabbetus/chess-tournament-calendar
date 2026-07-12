import type { APIRoute } from 'astro';
import tournaments from '../../../public/data/tournaments.json';

// Slimmed feed for the client-side list: only the fields the filters, sorting,
// and row rendering actually use. Drops description, raw time control, source,
// id, and the registration/website URLs — roughly halving the payload.
export const GET: APIRoute = () => {
  const slim = (tournaments as any[]).map((t) => ({
    slug: t.slug,
    name: t.name,
    // Some organizers put a full street address in the city field; only the
    // first comma-separated segment is meaningful as a "city" label, and
    // trimming it shaves a meaningful chunk off this feed's payload.
    city: t.city ? t.city.split(',')[0].trim() : t.city,
    country: t.country,
    countryCode: t.countryCode,
    startDate: t.startDate,
    endDate: t.endDate,
    timeControl: t.timeControl,
    playersRegistered: t.playersRegistered,
  }));
  return new Response(JSON.stringify(slim), {
    headers: { 'Content-Type': 'application/json' },
  });
};
