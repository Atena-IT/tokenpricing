/**
 * AA scrape spike — extraction snippets, exactly as used to produce ./data/*.csv
 *
 * These run in the page context (DevTools console, Playwright page.evaluate, or an
 * MCP browser javascript_exec). They are the *proof of approach*, not production code —
 * a real workload should live in services/sync with tested parsers over saved fixtures.
 *
 * Source: artificialanalysis.ai. Credit AA when publishing anything derived from this.
 */

const csvEscape = (v) => {
  v = (v == null ? '' : String(v)).replace(/—|--/g, ''); // AA renders "no data" as an em dash
  return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
};

const cellText = (el) => el.innerText.trim().replace(/\s+/g, ' ');

// ---------------------------------------------------------------------------
// (a) Provider leaderboard — https://artificialanalysis.ai/leaderboards/providers
// ---------------------------------------------------------------------------

/**
 * The expanded column view is client-side React state. There is no URL param and no
 * network fetch — the full dataset is already in the DOM on first paint, and expanding
 * only changes which columns are rendered.
 *
 * A plain `button.click()` does NOT work; React does not pick it up. A full synthetic
 * pointer sequence does. This is the single most important mechanical detail in this spike.
 */
async function expandColumns() {
  const btn = [...document.querySelectorAll('button')]
    .find((b) => b.innerText.trim() === 'Expand Columns');
  if (!btn) return false; // already expanded — the label flips to "Collapse Columns"

  btn.scrollIntoView({ block: 'center' });
  const r = btn.getBoundingClientRect();
  const init = {
    bubbles: true, cancelable: true, composed: true,
    clientX: r.x + r.width / 2, clientY: r.y + r.height / 2,
    button: 0, isPrimary: true, pointerId: 1, pointerType: 'mouse',
  };
  for (const type of ['pointerover', 'pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click']) {
    const Ctor = type.startsWith('pointer') ? PointerEvent : MouseEvent;
    btn.dispatchEvent(new Ctor(type, init));
  }
  await new Promise((res) => setTimeout(res, 1500));
  return document.querySelectorAll('table thead th').length > 20; // 20 collapsed -> 60 expanded
}

/**
 * Header row is 2-deep: a group row (Features / Model Intelligence / Price / Speed /
 * Latency / End-to-End Response Time) then the real column row. Slicing the flattened
 * th list at 9 drops the group cells and lands on "API Provider".
 */
function providerRows() {
  const table = document.querySelector('table');
  const headers = [...table.querySelectorAll('thead th')].map(cellText).slice(9);

  const rows = [...table.querySelectorAll('tbody tr')].map((tr) => {
    const cells = [...tr.querySelectorAll('td')].map(cellText);
    const hrefs = [...tr.querySelectorAll('a')].map((a) => a.getAttribute('href') || '');

    // The ONLY stable identity on this page. Display names are ambiguous — see README.
    const modelSlug = (hrefs.find((h) => h.startsWith('/models/')) || '').slice(8);
    const providerSlug = (hrefs.find((h) => h.startsWith('/providers/')) || '').slice(11);

    return { modelSlug, providerSlug, cells };
  });

  return { headers, rows };
}

function providerCsv() {
  const { headers, rows } = providerRows();
  return [
    ['model_slug', 'provider_slug', ...headers].map(csvEscape).join(','),
    ...rows.map((r) => [r.modelSlug, r.providerSlug, ...r.cells].map(csvEscape).join(',')),
  ].join('\n');
}

// ---------------------------------------------------------------------------
// (b) Openness Index
//     https://artificialanalysis.ai/evaluations/artificial-analysis-openness-index
// ---------------------------------------------------------------------------

/**
 * Single-depth header, all 298 rows in the DOM, and — critically — NO anchors anywhere
 * in the table body. There are no slugs on this page, so the join key is the rendered
 * model name plus the Creator column. See README "The join is the hard part".
 */
function opennessCsv() {
  const table = document.querySelector('table');
  const headers = [...table.querySelectorAll('thead th')].map(cellText).slice(1);
  const rows = [...table.querySelectorAll('tbody tr')]
    .map((tr) => [...tr.querySelectorAll('td')].map(cellText));

  return [
    ['rank', ...headers].map(csvEscape).join(','),
    ...rows.map((cells) => cells.map(csvEscape).join(',')),
  ].join('\n');
}

// ---------------------------------------------------------------------------
// Parsing gotchas the consumer MUST handle (all observed in the captured sample)
// ---------------------------------------------------------------------------

/** Negative scores use U+2212 MINUS SIGN, not ASCII hyphen. `parseFloat('−31')` -> NaN. */
const parseNumber = (s) => {
  if (s == null) return null;
  const t = String(s).trim()
    .replace(/−/g, '-')   // − -> -
    .replace(/[$,%]/g, '')     // $2.34 / 67%
    .replace(/,/g, '')         // "1,715"
    .replace(/\*$/, '');       // "33*" -> estimated/partial, see isEstimated
  return t === '' || t === '--' || t === '—' ? null : Number(t);
};

/** A trailing asterisk marks an estimated / incomplete score. Preserve the flag. */
const isEstimated = (s) => /\*\s*$/.test(String(s ?? ''));

/** Context window is rendered human-readable: "1M", "1.05M", "262k", "205k". */
const parseContext = (s) => {
  const m = /^([\d.]+)\s*([kM])$/.exec(String(s ?? '').trim());
  if (!m) return null;
  return Math.round(parseFloat(m[1]) * (m[2] === 'M' ? 1e6 : 1e3));
};

export { expandColumns, providerCsv, opennessCsv, parseNumber, isEstimated, parseContext };
