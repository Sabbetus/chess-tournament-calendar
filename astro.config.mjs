import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://chesstournamentcalendar.com',
  base: '/',
  output: 'static',
  integrations: [sitemap()],
});
