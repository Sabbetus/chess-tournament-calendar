import type { APIRoute } from 'astro';
import tournaments from '../../../public/data/tournaments.json';

// Slimmed feed for the client-side list: only the fields the filters, sorting,
// and row rendering actually use. Drops description, raw time control, source,
// id, and the registration/website URLs — roughly halving the payload.
export const GET: APIRoute = () => {
  const slim = (tournaments as any[]).map((t) => ({
    slug: t.slug,
    name: t.name,
    city: t.city,
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
