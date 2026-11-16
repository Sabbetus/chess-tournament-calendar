// The sentence under a country page's heading: how many tournaments are
// coming up and how many of them are classical and rapid. Written out per
// language because number agreement differs (Finnish partitive, Spanish and
// Portuguese gender and plural), which one template can't express.
//
// c = classical count, r = rapid count, n = c + r (always > 0 here).
type Writer = (country: string, c: number, r: number) => string;

const one = (n: number, a: string, b: string) => (n === 1 ? a : b);

const WRITERS: Record<string, Writer> = {
  en: (X, c, r) => {
    const n = c + r;
    const noun = one(n, 'tournament', 'tournaments');
    if (c && r) return `${X} has ${n} upcoming chess ${noun}: ${c} classical and ${r} rapid.`;
    const kind = c ? 'classical' : 'rapid';
    return n === 1 ? `${X} has 1 upcoming chess tournament, and it is ${kind}.` : `${X} has ${n} upcoming chess tournaments, all ${kind}.`;
  },
  es: (X, c, r) => {
    const n = c + r;
    const noun = one(n, 'torneo', 'torneos');
    if (c && r) return `En ${X} hay ${n} ${noun} de ajedrez próximos: ${c} ${one(c, 'clásico', 'clásicos')} y ${r} ${one(r, 'rápido', 'rápidos')}.`;
    const kind = c ? 'clásico' : 'rápido';
    return n === 1 ? `En ${X} hay 1 torneo de ajedrez próximo, y es ${kind}.` : `En ${X} hay ${n} torneos de ajedrez próximos, todos ${kind}s.`;
  },
  pt: (X, c, r) => {
    const n = c + r;
    const noun = one(n, 'torneio', 'torneios');
    if (c && r) return `Em ${X} há ${n} ${noun} de xadrez por realizar: ${c} ${one(c, 'clássico', 'clássicos')} e ${r} ${one(r, 'rápido', 'rápidos')}.`;
    const kind = c ? 'clássico' : 'rápido';
    return n === 1 ? `Em ${X} há 1 torneio de xadrez por realizar, e é ${kind}.` : `Em ${X} há ${n} torneios de xadrez por realizar, todos ${kind}s.`;
  },
  de: (X, c, r) => {
    const n = c + r;
    const verb = one(n, 'steht', 'stehen');
    const noun = one(n, 'Schachturnier', 'Schachturniere');
    if (c && r) return `In ${X} ${verb} ${n} ${noun} an, davon ${c} mit klassischer und ${r} mit Schnellschach-Bedenkzeit.`;
    const tail = c ? 'klassischer Bedenkzeit' : 'Schnellschach-Bedenkzeit';
    return n === 1 ? `In ${X} steht 1 Schachturnier an, es hat ${c ? 'klassische' : 'Schnellschach-'}${c ? ' Bedenkzeit' : 'Bedenkzeit'}.` : `In ${X} stehen ${n} Schachturniere an, alle mit ${tail}.`;
  },
  cs: (X, c, r) => {
    const n = c + r;
    if (c && r) return `${X} – nadcházející šachové turnaje: celkem ${n}, z toho klasických ${c} a rapid ${r}.`;
    const kind = c ? 'klasický' : 'rapid';
    return n === 1 ? `${X} – nadcházející šachové turnaje: celkem 1 (${kind}).` : `${X} – nadcházející šachové turnaje: celkem ${n}, všechny ${c ? 'klasické' : 'rapid'}.`;
  },
  fi: (X, c, r) => {
    const n = c + r;
    const noun = one(n, 'shakkiturnaus', 'shakkiturnausta');
    if (c && r) return `Maassa ${X} on tulossa ${n} ${noun}: ${c} ${one(c, 'klassinen', 'klassista')} ja ${r} ${one(r, 'nopea', 'nopeaa')}.`;
    if (n === 1) return `Maassa ${X} on tulossa 1 shakkiturnaus, ja se on ${c ? 'klassinen' : 'nopea'}.`;
    return `Maassa ${X} on tulossa ${n} shakkiturnausta, kaikki ${c ? 'klassisia' : 'nopeita'}.`;
  },
};

export function countrySummary(lang: string, country: string, classical: number, rapid: number): string {
  if (classical + rapid === 0) return '';
  return (WRITERS[lang] ?? WRITERS.en)(country, classical, rapid);
}
