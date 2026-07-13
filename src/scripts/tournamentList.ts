import { CONTINENT_MAP } from '../lib/continents';
import { CONTINENT_SLUGS } from '../lib/locationSlug';

function getContinent(cc: string) {
  return (cc && CONTINENT_MAP[cc]) || 'XX';
}

interface ListConfig {
  dataUrl: string;
  pageSize: number;
  basePath: string;
  tDays: string;
  tClassical: string;
  tRapid: string;
  tTrendTooltip: string;
  tMonths: string[];
  dateLocale: string;
  tCountries: Record<string, string>;
  // Localized pages re-render the SSR rows on load so country names etc. match
  // the page language; the English page keeps its server-rendered rows as-is.
  renderOnLoad: boolean;
  // English name -> slug, used to navigate the country dropdown to /country/x/.
  countrySlugs: Record<string, string>;
  // If set, this page is permanently scoped to one country/continent (its own
  // hub page) -- the country dropdown and continent tabs are always
  // navigation controls, never in-place filters, so this constraint can't be
  // removed by the user, only added to by month/duration/tc/search.
  lockedCountry?: string;
  lockedContinent?: string;
  lockedLabel?: string;
}

export function initTournamentList(cfg: ListConfig) {
  const PAGE_SIZE = cfg.pageSize;
  const { basePath, tDays, tClassical, tRapid, tTrendTooltip, tMonths, dateLocale, tCountries, countrySlugs, lockedCountry, lockedContinent, lockedLabel } = cfg;
  const prefix = basePath ? `/${basePath}` : '';

  const list = document.getElementById('tournament-list')!;
  const noResults = document.getElementById('no-results')!;
  const noResultsSummary = document.getElementById('no-results-summary');
  const defaultNoResultsText = noResultsSummary?.textContent || '';
  const countEl = document.getElementById('visible-count')!;
  const totalEl = document.getElementById('total-count')!;
  const loadMoreBtn = document.getElementById('load-more') as HTMLButtonElement;

  const continentTabsEl = document.getElementById('continent-tabs');
  continentTabsEl?.querySelectorAll('.ctab').forEach((tab) => {
    tab.addEventListener('click', () => {
      const code = (tab as HTMLElement).dataset.continent || '';
      window.location.href = code ? `${prefix}/continent/${CONTINENT_SLUGS[code]}/` : `${prefix}/`;
    });
  });

  const fCountry = document.getElementById('f-country')!;
  const fMonth = document.getElementById('f-month')!;
  const fDurationEl = document.getElementById('f-duration');
  const fTcEl = document.getElementById('f-tc');
  const fSearch = document.getElementById('f-search')!;
  const resetBtn = document.getElementById('filter-reset');

  function activeValue(groupEl: HTMLElement | null) {
    return (groupEl?.querySelector('.filter-btn.active') as HTMLElement)?.dataset.value ?? '';
  }

  // Option/tab labels have a "(count)" suffix baked in for the dropdown/tabs
  // themselves -- strip it when reusing the same label in a summary sentence.
  function stripCount(s: string) {
    return s.replace(/\s*\(\d+\)\s*$/, '').trim();
  }

  function activeFiltersSummary(): string {
    const parts: string[] = [];
    if (lockedLabel) parts.push(lockedLabel);
    const monthOpt = (fMonth as HTMLSelectElement).selectedOptions?.[0];
    if (monthOpt?.value) parts.push(stripCount(monthOpt.textContent || ''));
    const durationBtn = fDurationEl?.querySelector('.filter-btn.active[data-value]:not([data-value=""])');
    if (durationBtn) parts.push(durationBtn.textContent?.trim() || '');
    const tcBtn = fTcEl?.querySelector('.filter-btn.active[data-value]:not([data-value=""])');
    if (tcBtn) parts.push(tcBtn.textContent?.trim() || '');
    const search = (fSearch as HTMLInputElement).value.trim();
    if (search) parts.push(`"${search}"`);
    return parts.join(' · ');
  }

  function setupBtnGroup(groupEl: HTMLElement | null) {
    groupEl?.querySelectorAll('.filter-btn').forEach((btn) => {
      btn.addEventListener('click', () => {
        groupEl.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
        btn.classList.add('active');
        whenReady(renderFromScratch);
      });
    });
  }
  setupBtnGroup(fDurationEl);
  setupBtnGroup(fTcEl);

  let allData: any[] = [];
  let dataReady = false;
  let pendingFn: (() => void) | null = null;
  let renderedCount = PAGE_SIZE;
  let sortKey = 'date';
  let sortDir = 'asc';
  let lastRenderedMonth = '';

  function whenReady(fn: () => void) {
    if (dataReady) fn();
    else pendingFn = fn;
  }

  function escapeHTML(str: any) {
    return String(str ?? '').replace(/[&<>"']/g, (c) => (({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' } as any)[c]));
  }

  function formatDateRange(start: string, end: string) {
    const s = new Date(start + 'T00:00:00');
    const e = new Date(end + 'T00:00:00');
    const sStr = s.toLocaleDateString(dateLocale, { day: 'numeric', month: 'short' });
    const eStr = e.toLocaleDateString(dateLocale, { day: 'numeric', month: 'short', year: 'numeric' });
    return `${sStr} – ${eStr}`;
  }

  function durationDays(start: string, end: string) {
    const s = new Date(start + 'T00:00:00');
    const e = new Date(end + 'T00:00:00');
    return Math.round((e.getTime() - s.getTime()) / (1000 * 60 * 60 * 24)) + 1;
  }

  function flagUrl(t: any) {
    return t.countryCode ? `/flags/${t.countryCode.toLowerCase()}.png` : null;
  }

  function rowHTML(t: any) {
    const days = durationDays(t.startDate, t.endDate);
    const dateRange = formatDateRange(t.startDate, t.endDate);
    const detailUrl = t.slug ? `${prefix}/tournament/${t.slug}/` : null;
    const flag = flagUrl(t);
    const name = escapeHTML(t.name);
    const city = escapeHTML(t.city);
    const country = escapeHTML(tCountries[t.country] || t.country);
    const nameInner = detailUrl ? `<a href="${detailUrl}">${name}</a>` : name;
    const flagImg = flag ? `<img src="${flag}" alt="" width="14" height="11" loading="lazy">` : '';
    const hasPlayers = t.playersRegistered !== null && t.playersRegistered !== undefined;
    const trend = typeof t.playersTrend === 'number' && t.playersTrend !== 0 ? t.playersTrend : null;
    const trendClass = trend !== null ? (trend > 0 ? 'trend-up' : 'trend-down') : '';
    const trendArrow = trend !== null ? (trend > 0 ? '▲' : '▼') : '';
    const trendSign = trend !== null && trend > 0 ? '+' : '';
    const trendHTML = trend !== null
      ? ` <span class="trend ${trendClass}" title="${escapeHTML(tTrendTooltip)}">(${trendSign}${trend} <span class="trend-arrow">${trendArrow}</span>)</span>`
      : '';
    const playersText = hasPlayers ? t.playersRegistered : '—';
    const playersMeta = hasPlayers ? `<span>👥 ${t.playersRegistered}${trendHTML}</span>` : '';
    const tcLabel = t.timeControl === 'Rapid' ? tRapid : tClassical;
    const tcClass = t.timeControl === 'Rapid' ? 'badge-rapid' : 'badge-classical';
    const badge = `<span class="tc-badge ${tcClass}">${tcLabel}</span>`;

    return `<li class="trow">
      <div class="trow-main">
        <span class="trow-name"><span class="trow-name-text">${nameInner}</span></span>
        <span class="trow-tc">${badge}</span>
        <span class="trow-dates">${dateRange}</span>
        <span class="trow-location" data-tooltip="${city}, ${country}">${flagImg}${city}, ${country}</span>
        <span class="trow-duration">${days} ${tDays}</span>
        <span class="trow-players">${playersText}${trendHTML}</span>
      </div>
      <div class="trow-meta">
        <span class="trow-dates">${dateRange}</span>
        <span class="trow-location">${flagImg}<span class="trow-location-city">${city}, </span><span class="trow-location-country">${country}</span></span>
        <span class="trow-info"><span>${days} ${tDays}</span>${badge}${playersMeta}</span>
      </div>
    </li>`;
  }

  function getValue(t: any, key: string) {
    if (key === 'date') return new Date(t.startDate + 'T00:00:00').getTime();
    if (key === 'duration') return durationDays(t.startDate, t.endDate);
    if (key === 'players') return t.playersRegistered ?? -1;
    if (key === 'tc') return t.timeControl === 'Rapid' ? 1 : 0;
    return 0;
  }

  function getFilteredSorted() {
    const month = (fMonth as HTMLSelectElement).value;
    const duration = activeValue(fDurationEl);
    const tc = activeValue(fTcEl);
    const search = (fSearch as HTMLInputElement).value.toLowerCase().trim();

    const result = allData.filter((t: any) => {
      const matchLockedCountry = !lockedCountry || t.country === lockedCountry;
      const matchLockedContinent = !lockedContinent || getContinent(t.countryCode) === lockedContinent;
      const matchMonth = !month || new Date(t.startDate + 'T00:00:00').getMonth() + 1 === parseInt(month);
      const days = durationDays(t.startDate, t.endDate);
      const matchDuration = !duration || (duration === 'long' ? days >= 7 : days < 7);
      const matchTc = !tc || t.timeControl === tc;
      const matchSearch = !search || `${t.name} ${t.city} ${t.country}`.toLowerCase().includes(search);
      return matchLockedCountry && matchLockedContinent && matchMonth && matchDuration && matchTc && matchSearch;
    });

    result.sort((a: any, b: any) => {
      const av = getValue(a, sortKey);
      const bv = getValue(b, sortKey);
      if (sortKey === 'players') {
        if (av === -1 && bv === -1) return 0;
        if (av === -1) return 1;
        if (bv === -1) return -1;
      }
      return sortDir === 'asc' ? av - bv : bv - av;
    });

    return result;
  }

  function monthSeparatorHTML(t: any) {
    const d = new Date(t.startDate + 'T00:00:00');
    const monthIndex = d.getMonth() + 1;
    const year = d.getFullYear();
    const monthName = tMonths[monthIndex] || d.toLocaleDateString(dateLocale, { month: 'long' });
    const label = `${monthName} ${year}`;
    return `<li class="month-separator"><span class="month-separator-label">${label}</span></li>`;
  }

  function renderFromScratch() {
    list.querySelectorAll('.trow:not(.trow-featured), .month-separator').forEach((el) => el.remove());
    renderedCount = 0;
    lastRenderedMonth = '';
    renderMore();
  }

  function renderMore() {
    const filtered = getFilteredSorted();
    const next = filtered.slice(renderedCount, renderedCount + PAGE_SIZE);
    // Month separators only make sense while the list is in chronological order.
    // When sorting by player count the rows aren't grouped by month, so the
    // separators become noise — suppress them in that view.
    const showSeparators = sortKey !== 'players';
    const html = next
      .map((t: any) => {
        let sep = '';
        if (showSeparators) {
          const d = new Date(t.startDate + 'T00:00:00');
          const monthKey = `${d.getFullYear()}-${d.getMonth()}`;
          if (monthKey !== lastRenderedMonth) {
            sep = monthSeparatorHTML(t);
            lastRenderedMonth = monthKey;
          }
        }
        return sep + rowHTML(t);
      })
      .join('');
    list.insertAdjacentHTML('beforeend', html);
    renderedCount += next.length;

    countEl.textContent = String(Math.min(renderedCount, filtered.length));
    totalEl.textContent = String(filtered.length);
    loadMoreBtn.style.display = renderedCount < filtered.length ? '' : 'none';
    noResults.style.display = filtered.length === 0 ? 'block' : 'none';
    if (filtered.length === 0 && noResultsSummary) {
      const summary = activeFiltersSummary();
      noResultsSummary.textContent = summary ? summary : defaultNoResultsText;
    }
  }

  function arrowFor(key: string, dir: string) {
    if (key === 'players') return dir === 'desc' ? ' ↓' : ' ↑';
    if (key === 'date') return dir === 'asc' ? ' ↓' : ' ↑';
    if (key === 'duration') return dir === 'desc' ? ' ↓' : ' ↑';
    if (key === 'tc') return dir === 'asc' ? ' ↓' : ' ↑';
    return '';
  }

  function updateSortIcons() {
    document.querySelectorAll('.th-sortable').forEach((th) => {
      const icon = th.querySelector('.sort-icon');
      if (!icon) return;
      if ((th as HTMLElement).dataset.sort === sortKey) {
        icon.textContent = arrowFor(sortKey, sortDir);
        th.classList.add('th-sorted');
      } else {
        icon.textContent = '';
        th.classList.remove('th-sorted');
      }
    });
  }

  document.querySelectorAll('.th-sortable').forEach((th) => {
    th.addEventListener('click', () => {
      const key = (th as HTMLElement).dataset.sort!;
      if (sortKey === key) {
        sortDir = sortDir === 'asc' ? 'desc' : 'asc';
      } else {
        sortKey = key;
        sortDir = key === 'players' || key === 'duration' ? 'desc' : 'asc';
        if (key === 'tc') sortDir = 'asc';
      }
      updateSortIcons();
      whenReady(renderFromScratch);
    });
    th.addEventListener('keydown', (e) => {
      const ke = e as KeyboardEvent;
      if (ke.key === 'Enter' || ke.key === ' ') {
        ke.preventDefault();
        (th as HTMLElement).click();
      }
    });
  });
  updateSortIcons();

  const mSort = document.getElementById('m-sort') as HTMLSelectElement | null;
  mSort?.addEventListener('change', () => {
    const [k, d] = mSort.value.split('-');
    sortKey = k;
    sortDir = d;
    updateSortIcons();
    whenReady(renderFromScratch);
  });

  loadMoreBtn?.addEventListener('click', () => whenReady(renderMore));

  fCountry?.addEventListener('change', () => {
    const val = (fCountry as HTMLSelectElement).value;
    window.location.href = val ? `${prefix}/country/${countrySlugs[val]}/` : `${prefix}/`;
  });
  fMonth?.addEventListener('change', () => whenReady(renderFromScratch));
  let searchDebounce: ReturnType<typeof setTimeout> | undefined;
  fSearch?.addEventListener('input', () => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => whenReady(renderFromScratch), 150);
  });
  function resetAllFilters() {
    // Country dropdown and continent tabs are navigation, not filters -- reset
    // only clears the removable in-place filters, never the current page's
    // own country/continent scope.
    (fMonth as HTMLSelectElement).value = '';
    (fSearch as HTMLInputElement).value = '';
    [fDurationEl, fTcEl].forEach((groupEl) => {
      groupEl?.querySelectorAll('.filter-btn').forEach((b) => b.classList.remove('active'));
      groupEl?.querySelector('.filter-btn[data-value=""]')?.classList.add('active');
    });
    whenReady(renderFromScratch);
  }
  resetBtn?.addEventListener('click', resetAllFilters);
  document.getElementById('no-results-reset')?.addEventListener('click', resetAllFilters);

  if (cfg.renderOnLoad) whenReady(renderFromScratch);

  function loadData() {
    fetch(cfg.dataUrl)
      .then((r) => r.json())
      .then((data) => {
        allData = data;
        dataReady = true;
        if (lastRenderedMonth === '' && allData[renderedCount - 1]) {
          const d = new Date(allData[renderedCount - 1].startDate + 'T00:00:00');
          lastRenderedMonth = `${d.getFullYear()}-${d.getMonth()}`;
        }
        if (pendingFn) {
          const fn = pendingFn;
          pendingFn = null;
          fn();
        }
      })
      .catch((err) => console.error('Failed to load tournament data', err));
  }

  if (cfg.renderOnLoad) {
    // Localized pages need this data immediately to re-render the SSR rows
    // (which were rendered in the wrong language) as soon as possible.
    loadData();
  } else {
    // The English page's SSR rows are already final, so this feed is only
    // needed for search/filter/sort/load-more -- none of which happen
    // before the user interacts. Deferring to an idle moment keeps it off
    // the critical path for first paint without meaningfully delaying
    // readiness for whenever the user actually does interact.
    const schedule = window.requestIdleCallback || ((fn: () => void) => setTimeout(fn, 200));
    schedule(loadData);
  }

  // ── Hover tooltip (location column) ──
  const tooltip = document.getElementById('hover-tooltip')!;
  let tooltipTarget: Element | null = null;

  function positionTooltip(e: MouseEvent) {
    const offset = 14;
    let x = e.clientX + offset;
    let y = e.clientY + offset;
    const rect = tooltip.getBoundingClientRect();
    if (x + rect.width > window.innerWidth) x = e.clientX - rect.width - offset;
    if (y + rect.height > window.innerHeight) y = e.clientY - rect.height - offset;
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
  }

  document.addEventListener('mouseover', (e) => {
    const target = (e.target as Element).closest('[data-tooltip]');
    if (!target || target === tooltipTarget) return;
    tooltipTarget = target;
    tooltip.textContent = (target as HTMLElement).dataset.tooltip!;
    tooltip.classList.add('visible');
    positionTooltip(e as MouseEvent);
  });

  document.addEventListener('mousemove', (e) => {
    if (tooltipTarget) positionTooltip(e as MouseEvent);
  });
  document.addEventListener('mouseout', (e) => {
    if (tooltipTarget && !(e as MouseEvent).relatedTarget?.closest?.('[data-tooltip]')) {
      tooltipTarget = null;
      tooltip.classList.remove('visible');
    }
  });
}
