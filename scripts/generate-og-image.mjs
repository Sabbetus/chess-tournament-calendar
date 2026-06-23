// Generates public/og-image.png (1200×630) — the social link-preview card.
// Run: node scripts/generate-og-image.mjs   (requires only `sharp`)
//
// The "CHESS TOURNAMENT CALENDAR" wordmark is baked in below as vector paths
// (Bebas Neue, the same font as the site header). It is pre-rendered to paths
// because librsvg — sharp's SVG renderer — ignores @font-face, so referencing
// the woff2 by name would silently fall back to a generic sans-serif.
//
// To regenerate the wordmark paths (e.g. if the title text changes), decode
// public/fonts/bebas-neue-latin.woff2 to TTF with fonttools and trace the
// string with fontTools.pens.svgPathPen, then paste the <g> fragment here.
//
// Keep SUBTITLE in sync with site_description (classical & rapid scope).
import sharp from 'sharp';
import { writeFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const outPath = fileURLToPath(new URL('../public/og-image.png', import.meta.url));

const SUBTITLE = 'Classical &amp; rapid chess tournaments worldwide';

// Bebas Neue "CHESS TOURNAMENT CALENDAR", centered on a 1200-wide canvas,
// baseline at y=400. See header comment for how this was produced.
const TITLE_PATHS = `<g fill="#f5f6f8" transform="translate(36.7,400) scale(0.103379,-0.103379)"><path transform="translate(0.0,0)" d="M34 162V538Q34 620 75.5 665.0Q117 710 196 710Q275 710 316.5 665.0Q358 620 358 538V464H254V545Q254 610 199 610Q144 610 144 545V154Q144 90 199 90Q254 90 254 154V261H358V162Q358 80 316.5 35.0Q275 -10 196 -10Q117 -10 75.5 35.0Q34 80 34 162Z"/><path transform="translate(441.0,0)" d="M41 700H151V415H269V700H379V0H269V315H151V0H41Z"/><path transform="translate(919.1,0)" d="M41 700H341V600H151V415H302V315H151V100H341V0H41Z"/><path transform="translate(1340.1,0)" d="M22 166V206H126V158Q126 90 183 90Q211 90 225.5 106.5Q240 123 240 160Q240 204 220.0 237.5Q200 271 146 318Q78 378 51.0 426.5Q24 475 24 536Q24 619 66.0 664.5Q108 710 188 710Q267 710 307.5 664.5Q348 619 348 534V505H244V541Q244 577 230.0 593.5Q216 610 189 610Q134 610 134 543Q134 505 154.5 472.0Q175 439 229 392Q298 332 324.0 283.0Q350 234 350 168Q350 82 307.5 36.0Q265 -10 184 -10Q104 -10 63.0 35.5Q22 81 22 166Z"/><path transform="translate(1770.2,0)" d="M22 166V206H126V158Q126 90 183 90Q211 90 225.5 106.5Q240 123 240 160Q240 204 220.0 237.5Q200 271 146 318Q78 378 51.0 426.5Q24 475 24 536Q24 619 66.0 664.5Q108 710 188 710Q267 710 307.5 664.5Q348 619 348 534V505H244V541Q244 577 230.0 593.5Q216 610 189 610Q134 610 134 543Q134 505 154.5 472.0Q175 439 229 392Q298 332 324.0 283.0Q350 234 350 168Q350 82 307.5 36.0Q265 -10 184 -10Q104 -10 63.0 35.5Q22 81 22 166Z"/><path transform="translate(2200.2,0)" d=""/><path transform="translate(2418.2,0)" d="M127 600H12V700H352V600H237V0H127Z"/><path transform="translate(2840.3,0)" d="M33 166V534Q33 618 76.0 664.0Q119 710 200 710Q281 710 324.0 664.0Q367 618 367 534V166Q367 82 324.0 36.0Q281 -10 200 -10Q119 -10 76.0 36.0Q33 82 33 166ZM257 159V541Q257 610 200 610Q143 610 143 541V159Q143 90 200 90Q257 90 257 159Z"/><path transform="translate(3298.3,0)" d="M37 166V700H147V158Q147 122 161.5 106.0Q176 90 203 90Q230 90 244.5 106.0Q259 122 259 158V700H365V166Q365 81 323.0 35.5Q281 -10 201 -10Q121 -10 79.0 35.5Q37 81 37 166Z"/><path transform="translate(3758.3,0)" d="M41 700H204Q289 700 328.0 660.5Q367 621 367 539V496Q367 387 295 358V356Q335 344 351.5 307.0Q368 270 368 208V85Q368 55 370.0 36.5Q372 18 380 0H268Q262 17 260.0 32.0Q258 47 258 86V214Q258 262 242.5 281.0Q227 300 189 300H151V0H41ZM191 400Q224 400 240.5 417.0Q257 434 257 474V528Q257 566 243.5 583.0Q230 600 201 600H151V400Z"/><path transform="translate(4219.4,0)" d="M41 700H179L286 281H288V700H386V0H273L141 511H139V0H41Z"/><path transform="translate(4704.4,0)" d="M126 700H275L389 0H279L259 139V137H134L114 0H12ZM246 232 197 578H195L147 232Z"/><path transform="translate(5163.5,0)" d="M41 700H198L268 199H270L340 700H497V0H393V530H391L311 0H219L139 530H137V0H41Z"/><path transform="translate(5759.5,0)" d="M41 700H341V600H151V415H302V315H151V100H341V0H41Z"/><path transform="translate(6180.5,0)" d="M41 700H179L286 281H288V700H386V0H273L141 511H139V0H41Z"/><path transform="translate(6665.6,0)" d="M127 600H12V700H352V600H237V0H127Z"/><path transform="translate(7087.6,0)" d=""/><path transform="translate(7305.7,0)" d="M34 162V538Q34 620 75.5 665.0Q117 710 196 710Q275 710 316.5 665.0Q358 620 358 538V464H254V545Q254 610 199 610Q144 610 144 545V154Q144 90 199 90Q254 90 254 154V261H358V162Q358 80 316.5 35.0Q275 -10 196 -10Q117 -10 75.5 35.0Q34 80 34 162Z"/><path transform="translate(7746.7,0)" d="M126 700H275L389 0H279L259 139V137H134L114 0H12ZM246 232 197 578H195L147 232Z"/><path transform="translate(8205.7,0)" d="M41 700H151V100H332V0H41Z"/><path transform="translate(8607.8,0)" d="M41 700H341V600H151V415H302V315H151V100H341V0H41Z"/><path transform="translate(9028.8,0)" d="M41 700H179L286 281H288V700H386V0H273L141 511H139V0H41Z"/><path transform="translate(9513.9,0)" d="M41 700H209Q291 700 332.0 656.0Q373 612 373 527V173Q373 88 332.0 44.0Q291 0 209 0H41ZM207 100Q234 100 248.5 116.0Q263 132 263 168V532Q263 568 248.5 584.0Q234 600 207 600H151V100Z"/><path transform="translate(9977.9,0)" d="M126 700H275L389 0H279L259 139V137H134L114 0H12ZM246 232 197 578H195L147 232Z"/><path transform="translate(10436.9,0)" d="M41 700H204Q289 700 328.0 660.5Q367 621 367 539V496Q367 387 295 358V356Q335 344 351.5 307.0Q368 270 368 208V85Q368 55 370.0 36.5Q372 18 380 0H268Q262 17 260.0 32.0Q258 47 258 86V214Q258 262 242.5 281.0Q227 300 189 300H151V0H41ZM191 400Q224 400 240.5 417.0Q257 434 257 474V528Q257 566 243.5 583.0Q230 600 201 600H151V400Z"/></g>`;

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630" viewBox="0 0 1200 630">
  <defs>
    <radialGradient id="bg" cx="50%" cy="42%" r="75%">
      <stop offset="0%" stop-color="#1d2331"/>
      <stop offset="100%" stop-color="#0f1219"/>
    </radialGradient>
  </defs>
  <rect width="1200" height="630" fill="url(#bg)"/>
  <rect x="540" y="120" width="120" height="120" rx="26" fill="#232a3a"/>
  <!-- y tuned so the glyph's inked bounding box centers on the square (box center y=180) -->
  <text x="600" y="202.5" font-size="74" text-anchor="middle" dominant-baseline="central" fill="#ffffff">♟</text>
  ${TITLE_PATHS}
  <text x="600" y="452" font-family="sans-serif" font-size="30"
        text-anchor="middle" fill="#8a93a6">${SUBTITLE}</text>
</svg>`;

const png = await sharp(Buffer.from(svg)).png().toBuffer();
writeFileSync(outPath, png);
console.log(`Wrote ${outPath} (${png.length} bytes)`);
