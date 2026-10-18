/*
  app.js: the page's behavior.
  1. Builds the age-group buttons.
  2. When you press "Check", reads your inputs, finds your age group in data.js,
     works out your percentile, and fills in the results.
  3. Draws the chart as an SVG (a picture made of shapes, written as text).
  4. Handles the optional "Compare against" filter (couple/single, kids, home,
     education, income, work). Only ONE filter at a time, on top of age.
  Nothing here sends data anywhere: there are no network requests in this file.
*/

// "use strict" makes JavaScript warn about common mistakes.
"use strict";

// ---------- Grab the page elements we need (by their id in index.html) ----------
const form = document.getElementById("checker");
const ageInput = document.getElementById("age");
const netWorthInput = document.getElementById("networth");
const bracketButtons = document.getElementById("bracket-buttons");
const errorBox = document.getElementById("form-error");
const results = document.getElementById("results");

const compareSelect = document.getElementById("compare");
const filterOptionsBox = document.getElementById("filter-options");
const filterNote = document.getElementById("filter-note");
const incomeField = document.getElementById("income-field");
const incomeInput = document.getElementById("income");
const incomeGroupText = document.getElementById("income-group");

// Which age group button is selected (null = none; we'll use the typed age instead)
let selectedBracketId = null;
// Which "Compare against" filter and which of its choices are picked ("" / null = none)
let selectedFilterId = "";
let selectedOptionId = null;

// ---------- Helpers ----------

// Format a number as dollars, e.g. 1234567 -> "$1,234,567"
function formatMoney(value) {
  const sign = value < 0 ? "-" : "";
  return sign + "$" + Math.abs(Math.round(value)).toLocaleString("en-US");
}

// Short format for chart labels, e.g. 1500000 -> "$1.5M"
function formatShort(value) {
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e6) return sign + "$" + trim(abs / 1e6) + "M";
  if (abs >= 1e3) return sign + "$" + trim(abs / 1e3) + "K";
  return sign + "$" + abs;
}
function trim(n) {
  // 1.0 -> "1", 1.25 -> "1.3"
  return (Math.round(n * 10) / 10).toString();
}

// Turn what the user typed into a number.
// Accepts "150000", "$150,000", "150k", "1.2m", "-20,000". Returns null if it can't.
function parseMoney(text) {
  let s = String(text).trim().toLowerCase().replace(/[$,\s]/g, "");
  if (s === "") return null;
  let multiplier = 1;
  if (s.endsWith("k")) { multiplier = 1e3; s = s.slice(0, -1); }
  else if (s.endsWith("m")) { multiplier = 1e6; s = s.slice(0, -1); }
  if (!/^-?\d+(\.\d+)?$/.test(s)) return null;
  return Number(s) * multiplier;
}

// "1st", "2nd", "3rd", "4th", "11th", "22nd"...
function ordinal(n) {
  const mod100 = n % 100;
  if (mod100 >= 11 && mod100 <= 13) return n + "th";
  switch (n % 10) {
    case 1: return n + "st";
    case 2: return n + "nd";
    case 3: return n + "rd";
    default: return n + "th";
  }
}

// Find the age group for a typed age. Returns undefined if none fits.
function bracketForAge(age) {
  return SCF_DATA.brackets.find(
    (b) => age >= b.minAge && (b.maxAge === null || age <= b.maxAge)
  );
}

// How many of the 99 percentile cut-offs is the value at or above?
// Example: if the value beats the 1st..62nd cut-offs, this returns 62,
// meaning "higher than about 62% of families in this group".
function percentileRank(value, cuts) {
  let count = 0;
  for (const cut of cuts) {
    if (value >= cut) count++;
  }
  return count;
}

// ---------- Build the age-group buttons from data.js ----------
SCF_DATA.brackets.forEach((b) => {
  const btn = document.createElement("button");
  btn.type = "button";
  btn.className = "chip";
  btn.textContent = b.label;
  btn.setAttribute("aria-pressed", "false");
  btn.dataset.id = b.id;
  btn.addEventListener("click", () => {
    selectedBracketId = b.id;
    ageInput.value = ""; // picking a group clears the typed age
    updateChips();
    renderFilterOptions(); // greyed-out choices depend on age
  });
  bracketButtons.appendChild(btn);
});

function updateChips() {
  bracketButtons.querySelectorAll(".chip").forEach((chip) => {
    chip.setAttribute("aria-pressed", chip.dataset.id === selectedBracketId ? "true" : "false");
  });
}

// Typing an age un-selects any group button
ageInput.addEventListener("input", () => {
  selectedBracketId = null;
  updateChips();
  renderFilterOptions();
});

// ---------- When the form is submitted ----------
form.addEventListener("submit", (event) => {
  event.preventDefault(); // stop the browser from reloading the page
  errorBox.hidden = true;

  // 1. Work out the age group
  let bracket;
  if (selectedBracketId) {
    bracket = SCF_DATA.brackets.find((b) => b.id === selectedBracketId);
  } else {
    const age = Number(ageInput.value);
    if (!ageInput.value || !Number.isFinite(age)) return showError("Enter your age or pick an age group.");
    if (age < 18) return showError("The survey covers families whose reference person is 18 or older.");
    if (age > 110) return showError("Please check the age you entered.");
    bracket = bracketForAge(Math.floor(age));
  }

  // 2. Read the net worth
  const netWorth = parseMoney(netWorthInput.value);
  if (netWorth === null) return showError("Enter your net worth as a number, like 150000 or 150k.");

  // 3. No filter picked: the normal age-only view
  if (!selectedFilterId) return showResults(bracket, netWorth);

  // 4. A filter is picked: find the right group of survey families
  const filter = getFilter(selectedFilterId);
  if (filter.input === "income") {
    const income = parseMoney(incomeInput.value);
    if (income === null) return showError("Enter your 2024 household income, like 85000 or 85k.");
    selectedOptionId = incomeOptionFor(filter, income).id;
  }
  if (!selectedOptionId) return showError("Pick one of the choices under \"Compare against\".");
  const option = filter.options.find((o) => o.id === selectedOptionId);
  const result = resolveCell(filter, option, bracket.id);
  if (!result.ok) return showError(unavailableMessage(filter, option, result));
  showFilteredResults(bracket, filter, option, result, netWorth);
});

function showError(message) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function showResults(bracket, netWorth) {
  const cuts = bracket.percentiles;
  const rank = percentileRank(netWorth, cuts);
  const groupName = bracket.id === "under35" ? "under 35" : bracket.id === "75plus" ? "75 or older" : "aged " + bracket.label;

  // Headline sentence. Neutral wording: describes the data, gives no advice.
  let headline, detail, youNote;
  if (rank === 0) {
    headline = "Below the 1st percentile";
    detail = `Your net worth is lower than the 1st-percentile cut-off for US families ${groupName}.`;
    youNote = "below the 1st percentile";
  } else if (rank === 99) {
    headline = "Top 1%";
    detail = `Your net worth is at or above the 99th-percentile cut-off for US families ${groupName}.`;
    youNote = "at or above the 99th percentile";
  } else {
    headline = `Higher than about ${rank}% of families`;
    detail = `That puts you around the ${ordinal(rank)} percentile for US families ${groupName}.`;
    youNote = `about the ${ordinal(rank)} percentile`;
  }

  document.getElementById("result-bracket").textContent = "Age group: " + bracket.label;
  document.getElementById("result-headline").textContent = headline;
  document.getElementById("result-detail").textContent = detail;
  document.getElementById("stat-median").textContent = formatMoney(bracket.median);
  document.getElementById("stat-mean").textContent = formatMoney(bracket.mean);
  document.getElementById("stat-you").textContent = formatMoney(netWorth);
  document.getElementById("stat-you-note").textContent = youNote;
  document.getElementById("chart-bracket").textContent = bracket.label;
  document.getElementById("report-footnote").textContent =
    `The Fed's summary report, which uses its full internal dataset, puts this group's median at ` +
    `${formatMoney(bracket.reportMedian)} and mean at ${formatMoney(bracket.reportMean)} (2025 dollars). ` +
    `The numbers above use the public dataset so the median, mean, and percentiles all come from the same data.`;

  // Undo anything a filtered view changed
  document.getElementById("stat-mean-box").hidden = false;
  document.getElementById("result-notice").hidden = true;
  document.getElementById("sample-note").hidden = true;
  document.getElementById("cuts-caption").textContent = "Percentile cut-offs for this age group";

  fillTable(cuts, netWorth, rank);
  drawChart(cuts, netWorth, bracket.median);

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- Percentile table ----------
function fillTable(cuts, netWorth, rank, shown = [10, 25, 50, 75, 90, 95, 99]) {
  // "shown" = which percentiles to list. Filtered views pass a shorter list.
  const rows = shown.map((p) => ({ label: ordinal(p) + (p === 50 ? " (median)" : ""), value: cuts[p - 1], p }));
  // Insert a "You" row in the right place
  rows.push({ label: "You", value: netWorth, p: rank + 0.5, you: true });
  rows.sort((a, b) => a.p - b.p);

  const body = document.getElementById("cuts-body");
  body.innerHTML = ""; // clear old rows
  rows.forEach((r) => {
    const tr = document.createElement("tr");
    if (r.you) tr.className = "you-row";
    tr.innerHTML = `<td>${r.label}</td><td>${formatMoney(r.value)}</td>`;
    body.appendChild(tr);
  });
}

// ---------- Chart (plain SVG, no library) ----------
// The y-axis uses a "compressed" scale: equal steps for $1K -> $10K -> $100K -> $1M.
// It also handles negative values, which a normal log scale can't.
function squash(v) {
  return Math.sign(v) * Math.log10(1 + Math.abs(v) / 1000);
}

// pLo / pHi: which percentiles the line covers. The age-only view uses 1st–99th;
// filtered views use 10th–90th or 25th–75th, because their tails are too noisy.
function drawChart(cuts, netWorth, median, pLo = 1, pHi = 99) {
  const W = 640, H = 340;                                     // drawing size (scales to fit the screen)
  const pad = { left: 62, right: 18, top: 18, bottom: 40 };   // room for axis labels
  const innerW = W - pad.left - pad.right;
  const innerH = H - pad.top - pad.bottom;

  // Your x position: between the cut-offs you sit between (kept inside the chart)
  const rawX = rank_interp(netWorth, cuts);
  const youX = Math.min(pHi, Math.max(pLo, rawX));
  // If you're outside the line's range, say so next to the dot
  const offChart = rawX < pLo ? ` (below the ${ordinal(pLo)})` : rawX > pHi ? ` (above the ${ordinal(pHi)})` : "";

  // y range covers the curve and your value
  const yMin = squash(Math.min(cuts[pLo - 1], netWorth));
  const yMax = squash(Math.max(cuts[pHi - 1], netWorth));
  const x = (p) => pad.left + ((p - pLo) / (pHi - pLo)) * innerW;
  const y = (v) => pad.top + innerH - ((squash(v) - yMin) / (yMax - yMin || 1)) * innerH;

  // The curve: one point per percentile
  const path = cuts
    .map((v, i) => ({ p: i + 1, v }))
    .filter((pt) => pt.p >= pLo && pt.p <= pHi)
    .map((pt, i) => (i === 0 ? "M" : "L") + x(pt.p).toFixed(1) + " " + y(pt.v).toFixed(1))
    .join(" ");

  // Y-axis gridlines at round numbers that fall inside the range
  const ticks = [-1e6, -1e5, -1e4, 0, 1e4, 1e5, 1e6, 1e7, 1e8]
    .filter((t) => squash(t) >= yMin - 0.01 && squash(t) <= yMax + 0.01);
  const grid = ticks.map((t) =>
    `<line x1="${pad.left}" x2="${W - pad.right}" y1="${y(t)}" y2="${y(t)}" stroke="#262626"/>` +
    `<text x="${pad.left - 8}" y="${y(t) + 4}" text-anchor="end" fill="#9a9a9a" font-size="12">${formatShort(t)}</text>`
  ).join("");

  // X-axis labels
  const xLabels = [...new Set([pLo, 25, 50, 75, pHi])].filter((p) => p >= pLo && p <= pHi).map((p) =>
    `<text x="${x(p)}" y="${H - pad.bottom + 18}" text-anchor="middle" fill="#9a9a9a" font-size="12">${ordinal(p)}</text>`
  ).join("") +
    `<text x="${pad.left + innerW / 2}" y="${H - 4}" text-anchor="middle" fill="#9a9a9a" font-size="12">Percentile within age group</text>`;

  // Median marker (dashed vertical line at the 50th percentile)
  const medianMark =
    `<line x1="${x(50)}" x2="${x(50)}" y1="${pad.top}" y2="${pad.top + innerH}" stroke="#ffffff" stroke-opacity="0.35" stroke-dasharray="4 4"/>` +
    `<text x="${x(50) + 6}" y="${pad.top + 12}" fill="#ffffff" fill-opacity="0.7" font-size="12">Median ${formatShort(median)}</text>`;

  // "You" marker (accent dot + label). Flip the label left if it's near the right edge.
  const yx = x(youX), yy = y(netWorth);
  const labelLeft = youX > pLo + 0.7 * (pHi - pLo);
  const youMark =
    `<circle cx="${yx}" cy="${yy}" r="7" style="fill: var(--accent)" stroke="#000" stroke-width="2"/>` +
    `<text x="${yx + (labelLeft ? -12 : 12)}" y="${yy - 10}" text-anchor="${labelLeft ? "end" : "start"}" style="fill: var(--accent)" font-size="14" font-weight="700">You${offChart}</text>`;

  document.getElementById("chart").innerHTML =
    `<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="Net worth by percentile for this age group, with a marker for you">
      ${grid}${medianMark}
      <path d="${path}" fill="none" stroke="#ffffff" stroke-width="2.5"/>
      ${youMark}${xLabels}
      <text x="${W - pad.right}" y="${H - pad.bottom - 6}" text-anchor="end" fill="#9a9a9a" font-size="11">@rogueiq · Source: Federal Reserve SCF 2025</text>
    </svg>`;
}

// Where you sit on the x-axis, blending between the two cut-offs around your value
function rank_interp(value, cuts) {
  if (value <= cuts[0]) return 1;
  if (value >= cuts[98]) return 99;
  for (let i = 0; i < 98; i++) {
    const lo = cuts[i], hi = cuts[i + 1];
    if (value >= lo && value < hi) return i + 1 + (value - lo) / (hi - lo);
  }
  return 99;
}

// ---------- Email signup placeholder ----------
// Not connected to anything. Pressing the button only shows a "coming soon" note.
document.getElementById("signup").addEventListener("submit", (event) => {
  event.preventDefault();
  document.getElementById("signup-msg").textContent =
    "Coming soon. This signup isn't connected yet, so your email was not sent or saved.";
});

// =====================================================================
// "Compare against" filters
// =====================================================================
// The numbers live in SCF_FILTERS (data.js). Each filter has options
// (e.g. "Couple" / "Single"), and each option has one "cell" per age group,
// with n = how many survey families are in it.
//
// The thin-cell rule: a cell needs at least SCF_FILTERS.minN (100) families.
// If it has fewer, we widen the age group: 6 groups -> 3 groups -> 2 groups.
// If it's still too small, the option is greyed out.

const LEVEL_ORDER = [6, 3, 2]; // narrowest to widest age grouping

function getFilter(id) {
  return SCF_FILTERS.filters.find((f) => f.id === id);
}

// Fill the "Compare against" dropdown from data.js
SCF_FILTERS.filters.forEach((f) => {
  const opt = document.createElement("option");
  opt.value = f.id;
  opt.textContent = f.label;
  compareSelect.appendChild(opt);
});

compareSelect.addEventListener("change", () => {
  selectedFilterId = compareSelect.value;
  selectedOptionId = null; // a new filter starts with nothing picked
  renderFilterOptions();
});

// Which 6-group age bracket the user is in right now (or null if not entered yet)
function currentBracketId() {
  if (selectedBracketId) return selectedBracketId;
  const age = Number(ageInput.value);
  if (!ageInput.value || !Number.isFinite(age) || age < 18 || age > 110) return null;
  const b = bracketForAge(Math.floor(age));
  return b ? b.id : null;
}

// Find the age group at a given level (6, 3 or 2) that contains a 6-group bracket.
// Every 10-year group fits inside exactly one wider group, so we test its lowest age.
function bandAtLevel(level, bracketId) {
  const minAge = SCF_DATA.brackets.find((b) => b.id === bracketId).minAge;
  return SCF_FILTERS.levels[level].find(
    (band) => minAge >= band.minAge && (band.maxAge === null || minAge <= band.maxAge)
  );
}

// The core rule. Returns { ok, cell, level, band, tried, forced }.
// "tried" lists every age group we looked at, so we can explain any widening.
function resolveCell(filter, option, bracketId) {
  if (filter.allowedAge6 && !filter.allowedAge6.includes(bracketId)) {
    return { ok: false, reason: "age" };
  }
  // Start at the filter's normal age grouping, unless this option merges ages by design
  const forcedLevel = option.forceLevel && option.forceLevel[bracketId];
  const start = forcedLevel || filter.startLevel;
  const tried = [];
  for (const level of LEVEL_ORDER.filter((l) => l <= start)) {
    const band = bandAtLevel(level, bracketId);
    const cell = option.cells[level + ":" + band.id];
    tried.push({ level, band, n: cell.n });
    if (cell.n >= SCF_FILTERS.minN && cell.p) {
      return { ok: true, cell, level, band, tried, forced: Boolean(forcedLevel) };
    }
  }
  return { ok: false, reason: "thin", tried };
}

// "under 45" or "aged 45–64", for use in sentences
function ageText(band) {
  return band.label.startsWith("under") ? band.label : "aged " + band.label;
}

function unavailableMessage(filter, option, result) {
  if (result.reason === "age") return `"${filter.label}" is only available for people under 55.`;
  const widest = result.tried[result.tried.length - 1];
  return `${option.label}: not enough survey data for your age group ` +
    `(only ${widest.n} survey families even ${ageText(widest.band)}). Pick another choice.`;
}

// Draw the choice chips for the picked filter, greying out any that can't be shown
function renderFilterOptions() {
  filterOptionsBox.innerHTML = "";
  filterNote.hidden = true;
  incomeField.hidden = true;
  if (!selectedFilterId) { filterOptionsBox.hidden = true; return; }

  const filter = getFilter(selectedFilterId);
  const bracketId = currentBracketId();
  const notes = [];

  // Income is typed in, not picked from chips
  if (filter.input === "income") {
    filterOptionsBox.hidden = true;
    incomeField.hidden = false;
    updateIncomeGroup();
    return;
  }

  filterOptionsBox.hidden = false;
  filter.options.forEach((option) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = option.label;
    chip.dataset.id = option.id;

    // We can only check thin cells once we know the age
    if (bracketId) {
      const result = resolveCell(filter, option, bracketId);
      if (!result.ok) {
        chip.disabled = true;
        if (selectedOptionId === option.id) selectedOptionId = null;
        if (result.reason === "age") {
          if (!notes.includes("age")) notes.push("age");
        } else {
          notes.push(`${option.label}: not enough survey data for your age group.`);
        }
      }
    }
    chip.setAttribute("aria-pressed", selectedOptionId === option.id ? "true" : "false");
    chip.addEventListener("click", () => {
      selectedOptionId = option.id;
      renderFilterOptions();
    });
    filterOptionsBox.appendChild(chip);
  });

  if (notes.length) {
    filterNote.textContent = notes.includes("age")
      ? "Number of kids is only available for people under 55 (too few survey families with kids at older ages)."
      : notes.join(" ");
    filterNote.hidden = false;
  }
}

// ---------- Income: turn a typed 2024 income into one of the 5 groups ----------
// incomeCutoffs2024 = lower edges of the 20th, 40th, 60th and 80th percentiles.
function incomeOptionFor(filter, income) {
  const index = SCF_FILTERS.incomeCutoffs2024.filter((cut) => income >= cut).length;
  return filter.options[index];
}

function incomeRangeText(index) {
  const cuts = SCF_FILTERS.incomeCutoffs2024;
  if (index === 0) return "under " + formatMoney(cuts[0]);
  if (index === cuts.length) return formatMoney(cuts[cuts.length - 1]) + " or more";
  return formatMoney(cuts[index - 1]) + " to " + formatMoney(cuts[index] - 1);
}

function updateIncomeGroup() {
  const filter = getFilter("income");
  const income = parseMoney(incomeInput.value);
  if (income === null) { incomeGroupText.textContent = ""; return; }
  const option = incomeOptionFor(filter, income);
  const index = filter.options.indexOf(option);
  incomeGroupText.textContent = `2024 income group: ${option.label} of US families (${incomeRangeText(index)}).`;
}
incomeInput.addEventListener("input", updateIncomeGroup);

// ---------- Filtered results ----------
function showFilteredResults(bracket, filter, option, result, netWorth) {
  const { cell, band, tried } = result;
  const cuts = cell.p;
  const n = cell.n;
  const group = `US families ${ageText(band)} ${option.phrase}`;

  // Rank, rounded to the nearest 5 because smaller groups give rougher answers
  const rounded = Math.round(percentileRank(netWorth, cuts) / 5) * 5;
  let headline, detail, youNote;
  if (rounded <= 0) {
    headline = "Below about the 5th percentile";
    detail = `Your net worth is below about the 5th percentile for ${group}.`;
    youNote = "below about the 5th percentile";
  } else if (rounded >= 100) {
    headline = "Above about the 95th percentile";
    detail = `Your net worth is above about the 95th percentile for ${group}.`;
    youNote = "above about the 95th percentile";
  } else {
    headline = `Higher than about ${rounded}% of these families`;
    detail = `That puts you around the ${ordinal(rounded)} percentile for ${group}.`;
    youNote = `about the ${ordinal(rounded)} percentile`;
  }

  // Plain-language notice when the age group isn't the user's own 10-year group
  const notice = document.getElementById("result-notice");
  const widenedForThinCell = tried.length > 1;
  if (result.forced) {
    notice.textContent = `${option.forceNote} This compares you with ${group} (${n} survey families).`;
  } else if (widenedForThinCell) {
    const first = tried[0];
    notice.textContent = `Only ${first.n} survey families ${ageText(first.band)} ${option.phrase} are in the data. ` +
      `That's too few for a reliable answer, so we widened the age group: this compares you with ${group} (${n} survey families).`;
  } else if (result.level < 6) {
    notice.textContent = `This filter uses wider age groups so each group has enough survey families. ` +
      `You're compared with ${group}.`;
  } else {
    notice.textContent = "";
  }
  notice.hidden = notice.textContent === "";

  document.getElementById("result-bracket").textContent = `Age group: ${band.label} · ${filter.label}: ${option.label}`;
  document.getElementById("result-headline").textContent = headline;
  document.getElementById("result-detail").textContent = detail;
  document.getElementById("stat-median").textContent = formatMoney(cuts[49]);
  document.getElementById("stat-mean-box").hidden = true; // means are too noisy in small groups
  document.getElementById("stat-you").textContent = formatMoney(netWorth);
  document.getElementById("stat-you-note").textContent = youNote;
  document.getElementById("chart-bracket").textContent = `${band.label}, ${option.label.toLowerCase()}`;
  document.getElementById("cuts-caption").textContent = "Percentile cut-offs for this group";

  // 10th and 90th only when the group is big enough; never the 95th or 99th
  const fullRange = n >= SCF_FILTERS.fullRangeN;
  const shown = fullRange ? [10, 25, 50, 75, 90] : [25, 50, 75];
  fillTable(cuts, netWorth, percentileRank(netWorth, cuts), shown);
  drawChart(cuts, netWorth, cuts[49], shown[0], shown[shown.length - 1]);

  const sample = document.getElementById("sample-note");
  sample.textContent = `Based on ${n} survey families. Smaller groups give rougher answers, so your rank is rounded ` +
    `to the nearest 5, the average (mean) isn't shown, and ` +
    (fullRange ? "the 95th and 99th percentiles are left out." : "only the 25th to 75th percentiles are shown (fewer than 200 families).");
  sample.hidden = false;

  // Official Fed figures (all ages, not by age) where the Fed publishes them
  const footnote = document.getElementById("report-footnote");
  if (option.official) {
    footnote.textContent = "Fed's official all-ages figures (Table 4, 2025 dollars; not split by age): " +
      option.official.map(([label, med, mean]) => `${label}: median ${formatMoney(med)}, mean ${formatMoney(mean)}`).join("; ") + ".";
  } else {
    footnote.textContent = "The Fed doesn't publish official figures for this group. These numbers are computed from its public 2025 data.";
  }

  results.hidden = false;
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}
