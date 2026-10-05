import type { APIRoute } from 'astro';
import archive from '../../../public/data/archive.json';
import fideArchive from '../../../public/data/fide_archive.json';

// Every tournament ever seen, from both sources, for external consumers.
// The two archives stay separate on disk because each scraper owns its own
// file's miss-counting and safety-floor logic; tell entries apart by `source`.
export const GET: APIRoute = () => {
  const all = [...(archive as any[]), ...(fideArchive as any[])]
    .sort((a, b) => a.startDate.localeCompare(b.startDate));
  return new Response(JSON.stringify(all), {
    headers: { 'Content-Type': 'application/json' },
  });
};
