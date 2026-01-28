
function getAccessToken() {
  return localStorage.getItem("mv_access_token") || "";
}

function requireLogin() {
  const page = (location.pathname.split("/").pop() || "ratings.html");
  const next = encodeURIComponent(page);
  location.replace(`/auth.html?next=${next}`);
}

(function guard() {
  const token = getAccessToken();
  if (!token) {
    requireLogin();
  }
})();

const isRatePage = document.body?.classList.contains("mv-rate");
const isOverviewPage = document.body?.classList.contains("mv-ratings");

function getMatchIdFromQuery() {
  const params = new URLSearchParams(location.search || "");
  return params.get("match_id") || "";
}

function getMatchById(matchId) {
  const key = String(matchId || "");
  if (!key) return null;
  if (matchCache[key]) return matchCache[key];
  return allMatches.find(m => String(m.match_id || "") === key) || null;
}

function goToRateId(matchId) {
  if (!matchId) return;
  const encoded = encodeURIComponent(String(matchId));
  location.href = `/rate.html?match_id=${encoded}`;
}

function goToRateMatch(match) {
  if (!match || typeof match !== "object") return;
  const id = String(match.match_id || "");
  if (!id) {
    alert("Dieses Spiel hat keine Match-ID.");
    return;
  }
  goToRateId(id);
}

function getApiBase() {
  const v = localStorage.getItem("mv_api_base");
  return v ? v : "/api";
}
function normalizeBase(v) {
  if (!v) return "/api";
  v = v.trim();
  if (v.endsWith("/")) v = v.slice(0, -1);
  return v;
}
async function apiFetch(path, options = {}) {
  const base = getApiBase();
  const url = normalizeBase(base) + path;

  const token = getAccessToken();
  const headers = new Headers(options.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (!headers.has("Accept-Language")) headers.set("Accept-Language", getPreferredLanguage());
  if (options.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const res = await fetch(url, { ...options, headers });

  if ((res.status === 401 || res.status === 403) && !suppressAuthRedirect) {
    localStorage.removeItem("mv_access_token");
    requireLogin();
  }

  const txt = await res.text();
  let data = null;
  try { data = txt ? JSON.parse(txt) : null; } catch { data = txt; }
  return { res, data, url };
}

function logOut(id, obj) {
  document.getElementById(id).textContent =
    typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

function normalizeList(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.data)) return data.data;
  if (data && Array.isArray(data.items)) return data.items;
  return null;
}

const SCENE_TYPE_LABELS_DE = {
  "PENALTY":"Elfmeter",
  "PENALTY_REVIEW":"Elfmeter-Check",
  "PENALTY_OVERTURNED":"Elfmeter zurückgenommen",
  "FREE_KICK":"Freistoß",
  "INDIRECT_FREE_KICK":"Indirekter Freistoß",
  "DROP_BALL":"Schiedsrichterball",
  "FOUL":"Foul",
  "YELLOW_CARD":"Gelbe Karte",
  "SECOND_YELLOW":"Zweite Gelbe",
  "RED_CARD":"Rote Karte",
  "OFFSIDE":"Abseits",
  "GOAL":"Tor",
  "OFFSIDE_GOAL":"Tor im Abseits",
  "GOAL_DISALLOWED":"Tor aberkannt",
  "VAR_REVIEW":"VAR-Check",
  "VAR_DECISION":"VAR-Entscheidung",
  "HANDBALL":"Handspiel",
  "DENIED_GOALSCORING_OPPORTUNITY":"Notbremse (DOGSO)",
  "SUBSTITUTION":"Wechsel",
  "INJURY_STOPPAGE":"Verletzungspause",
  "TIME_WASTING":"Zeitspiel",
  "DISSENT":"Unsportliches Verhalten",
  "CORNER":"Ecke",
  "GOAL_KICK":"Abstoß",
  "THROW_IN":"Einwurf",
  "OTHER":"Sonstiges"
};

function getSceneTypeLabel(scene) {
  if (!scene || typeof scene !== "object") return "";
  if (scene.scene_type_label) return scene.scene_type_label;
  const key = scene.scene_type || "";
  if (!key) return "";
  const lang = getPreferredLanguage().toLowerCase();
  if (lang.startsWith("de")) return SCENE_TYPE_LABELS_DE[key] || key;
  return key;
}

function getPreferredLanguage() {
  if (navigator.languages && navigator.languages.length) return navigator.languages[0];
  return navigator.language || "en";
}

function getChannelLabel(key) {
  const lang = getPreferredLanguage().toLowerCase();
  const de = {
    "TV": "TV",
    "STADIUM": "Stadion",
    "STREAM": "Stream",
    "HIGHLIGHT": "Highlight",
    "UNKNOWN": "Unbekannt"
  };
  const en = {
    "TV": "TV",
    "STADIUM": "Stadium",
    "STREAM": "Stream",
    "HIGHLIGHT": "Highlight",
    "UNKNOWN": "Unknown"
  };
  const map = lang.startsWith("de") ? de : en;
  return map[key] || key;
}

function getTimeLabel(key) {
  const lang = getPreferredLanguage().toLowerCase();
  const de = {
    "LIVE": "Live",
    "AFTER_REPLAY": "Nach Wiederholung",
    "AFTER_VAR": "Nach VAR",
    "LATER": "Später",
    "UNKNOWN": "Unbekannt"
  };
  const en = {
    "LIVE": "Live",
    "AFTER_REPLAY": "After replay",
    "AFTER_VAR": "After VAR",
    "LATER": "Later",
    "UNKNOWN": "Unknown"
  };
  const map = lang.startsWith("de") ? de : en;
  return map[key] || key;
}

function getSceneDescription(scene) {
  if (!scene || typeof scene !== "object") return "";
  const lang = getPreferredLanguage().toLowerCase();
  if (lang.startsWith("de")) return scene.description_de || scene.description_en || scene.description || "";
  return scene.description_en || scene.description_de || scene.description || "";
}

let suppressAuthRedirect = false;
const matchCache = {};
const allMatches = [];
const sceneCache = {};
let scenesLoadedMatchId = "";
let currentTab = "match";
const matchVoteCountCache = {};

function getMatchdayKey(match) {
  if (!match || typeof match !== "object") return "";
  const season = String(match.season || "");
  const number = Number(match.matchday_number);
  if (season && Number.isFinite(number) && number > 0) return `${season}|${number}`;
  const name = match.matchday_name || match.matchday_name_en || "";
  if (season && name) return `${season}|${name}`;
  if (Number.isFinite(number) && number > 0) return `|${number}`;
  if (name) return `|${name}`;
  return "";
}

function matchdayKeyToSortValue(key) {
  const parts = String(key || "").split("|");
  const season = parts[0] || "";
  const seasonStart = Number((season.match(/\d{4}/) || [0])[0]) || 0;
  const number = Number(parts[1] || 0);
  const numValue = Number.isFinite(number) && number > 0 ? number : 999;
  return (seasonStart * 1000) + numValue;
}

function formatMatchdayLabelFromMatch(match) {
  const lang = getPreferredLanguage().toLowerCase();
  const season = String(match?.season || "").trim();
  const number = Number(match?.matchday_number);
  let label = "";
  if (lang.startsWith("de")) {
    label = match?.matchday_name || (Number.isFinite(number) && number > 0 ? `Spieltag ${number}` : "");
  } else {
    label = match?.matchday_name_en || (Number.isFinite(number) && number > 0 ? `Matchday ${number}` : "");
  }
  if (!label) label = lang.startsWith("de") ? "Spieltag unbekannt" : "Matchday unknown";
  if (!season) return label;
  const seasonPrefix = lang.startsWith("de") ? "Saison" : "Season";
  const seasonShort = formatSeasonShort(season);
  return `${seasonPrefix} ${seasonShort} · ${label}`;
}

function formatSeasonShort(season) {
  const raw = String(season || "").trim();
  if (!raw) return raw;
  const years = raw.match(/\d{4}/g) || [];
  if (years.length >= 2) {
    const y1 = years[0];
    const y2 = years[1];
    return `${y1.slice(-2)}/${y2.slice(-2)}`;
  }
  if (years.length === 1) {
    const y1 = Number(years[0]);
    if (Number.isFinite(y1)) {
      const y2 = y1 + 1;
      return `${String(y1).slice(-2)}/${String(y2).slice(-2)}`;
    }
  }
  const short = raw.match(/\b(\d{2})\s*\/\s*(\d{2})\b/);
  if (short) return `${short[1]}/${short[2]}`;
  return raw;
}

let weekOptions = [];
let currentWeekIndex = 0;
let matchdayLabelMap = {};

function formatWeekLabelSafe(key) {
  if (!key) return "-";
  return matchdayLabelMap[key] || key;
}

function updateWeekLabel() {
  const label = document.getElementById("weekLabel");
  if (!label) return;
  if (!weekOptions.length) {
    label.textContent = "Keine Spieltage";
    return;
  }
  const key = weekOptions[currentWeekIndex] || "";
  label.textContent = formatWeekLabelSafe(key);
}

function stepWeek(dir) {
  if (!weekOptions.length) return;
  currentWeekIndex = Math.max(0, Math.min(weekOptions.length - 1, currentWeekIndex + dir));
  const sel = document.getElementById("matchWeekFilter");
  if (sel) sel.value = weekOptions[currentWeekIndex] || "";
  updateWeekLabel();
  onWeekFilterChange();
}

function initWeekNav() {
  const prev = document.getElementById("weekPrevBtn");
  const next = document.getElementById("weekNextBtn");
  if (prev) prev.addEventListener("click", () => stepWeek(-1));
  if (next) next.addEventListener("click", () => stepWeek(1));
}
function setSelectOptions(sel, options, allLabel, selectedValue = "", labelFormatter = null) {
  if (!sel) return;
  sel.innerHTML = "";
  if (allLabel != null && allLabel !== "") {
    const optAll = document.createElement("option");
    optAll.value = "";
    optAll.textContent = allLabel;
    sel.appendChild(optAll);
  }

  for (const v of options) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = labelFormatter ? labelFormatter(v) : v;
    sel.appendChild(opt);
  }

  if (selectedValue && options.includes(selectedValue)) {
    sel.value = selectedValue;
  } else if (options.length) {
    sel.value = options[0];
  }
}

function updateButtonGroupState(containerId, selectedValue) {
  const container = document.getElementById(containerId);
  if (!container) return;
  container.querySelectorAll("button[data-value]").forEach(btn => {
    const active = (btn.dataset.value || "") === (selectedValue || "");
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function renderFilterButtons(containerId, options, selectedValue, allLabel, selectId, onChange, labelFormatter = null) {
  const container = document.getElementById(containerId);
  const selectEl = document.getElementById(selectId);
  if (!container || !selectEl) return;

  container.innerHTML = "";
  const items = [{ label: allLabel, value: "" }, ...options.map(v => ({ label: labelFormatter ? labelFormatter(v) : v, value: v }))];

  for (const item of items) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip";
    btn.dataset.value = item.value;
    btn.textContent = item.label;
    btn.addEventListener("click", () => {
      selectEl.value = item.value;
      onChange();
      updateButtonGroupState(containerId, selectEl.value);
    });
    container.appendChild(btn);
  }

  updateButtonGroupState(containerId, selectedValue);
}

function syncFilterButtons() {
  const league = document.getElementById("matchLeagueFilter")?.value || "";
  updateButtonGroupState("leagueButtonGroup", league);
}

function buildLeagueOptions(matches) {
  const sel = document.getElementById("matchLeagueFilter");
  const leagues = [...new Set(matches.map(m => m.league).filter(Boolean))].sort();
  setSelectOptions(sel, leagues, "Alle Ligen", sel?.value || "");
  renderFilterButtons("leagueButtonGroup", leagues, sel?.value || "", "Alle Ligen", "matchLeagueFilter", onLeagueFilterChange);
}

function buildWeekOptions(matches, selectedWeek = "") {
  const sel = document.getElementById("matchWeekFilter");
  matchdayLabelMap = {};
  const keys = [];
  for (const m of matches) {
    const key = getMatchdayKey(m);
    if (!key) continue;
    if (!matchdayLabelMap[key]) {
      matchdayLabelMap[key] = formatMatchdayLabelFromMatch(m);
      keys.push(key);
    }
  }
  const weeks = keys.sort((a, b) => matchdayKeyToSortValue(a) - matchdayKeyToSortValue(b));
  weekOptions = weeks;

  let selected = selectedWeek || sel?.value || "";
  if (!selected) {
    const now = new Date();
    const sorted = [...matches].sort((a, b) => new Date(a.match_date) - new Date(b.match_date));
    for (const m of sorted) {
      const dt = new Date(m.match_date);
      if (!Number.isFinite(dt.getTime())) continue;
      if (dt <= now) selected = getMatchdayKey(m);
      if (dt > now) break;
    }
  }
  setSelectOptions(sel, weekOptions, "", selected, formatWeekLabelSafe);

  let idx = weekOptions.indexOf(selected);
  if (idx < 0) idx = weekOptions.length ? 0 : -1;
  currentWeekIndex = idx >= 0 ? idx : 0;
  if (sel) sel.value = weekOptions[currentWeekIndex] || "";
  updateWeekLabel();
}

function updateMatchListActive(matchId) {
  const listEl = document.getElementById("matchList");
  if (!listEl) return;
  if (!matchId) {
    listEl.querySelectorAll("[data-match-id]").forEach(btn => {
      btn.classList.remove("active");
    });
    return;
  }
  listEl.querySelectorAll("[data-match-id]").forEach(btn => {
    const active = String(btn.dataset.matchId || "") === String(matchId || "");
    btn.classList.toggle("active", active);
  });
}

function formatMatchDateParts(m) {
  let day = "";
  let time = "";
  try {
    const dt = new Date(m.match_date);
    day = dt.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
    time = dt.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  } catch {
    day = "";
    time = "";
  }
  return { day, time };
}

function updateRateHeader(matchId) {
  if (!isRatePage) return;
  const title = document.getElementById("rateMatchTitle");
  const sub = document.getElementById("rateMatchSub");
  if (!title || !sub) return;

  const m = getMatchById(matchId);
  if (!m) {
    setRateHeaderState("notfound");
    return;
  }

  title.textContent = `${m.team_home || ""} vs ${m.team_away || ""}`.trim();
  const parts = formatMatchDateParts(m);
  const bits = [
    `${parts.day} ${parts.time}`.trim(),
    m.league || "",
    m.season || ""
  ].filter(Boolean);
  sub.textContent = bits.join(" · ");

}

function setRateHeaderState(state) {
  if (!isRatePage) return;
  const title = document.getElementById("rateMatchTitle");
  const sub = document.getElementById("rateMatchSub");
  if (!title || !sub) return;
  if (state === "loading") {
    title.textContent = "Lade Spiel\u2026";
    sub.textContent = "Bitte warten...";
    return;
  }
  if (state === "notfound") {
    title.textContent = "Spiel nicht gefunden";
    sub.textContent = "";
  }
}

function isLiveMatch(match, now = new Date()) {
  if (!match || !match.match_date) return false;
  const kickoff = new Date(match.match_date);
  if (!Number.isFinite(kickoff.getTime())) return false;
  const start = new Date(kickoff.getTime() - (15 * 60 * 1000));
  const end = new Date(kickoff.getTime() + (135 * 60 * 1000));
  return now >= start && now <= end;
}

function renderLiveMatches(matches) {
  const titleEl = document.getElementById("liveTitle");
  const subEl = document.getElementById("liveSub");
  const listEl = document.getElementById("liveList");
  if (!titleEl || !subEl || !listEl) return;

  const now = new Date();
  const live = (matches || []).filter(m => isLiveMatch(m, now));
  listEl.innerHTML = "";

  if (!live.length) {
    titleEl.textContent = "Keine Live-Spiele gerade";
    subEl.textContent = "Schau später vorbei, wenn ein Spiel läuft.";
    return;
  }

  titleEl.textContent = "Live-Spiele jetzt";
  subEl.textContent = `${live.length} Spiel${live.length === 1 ? "" : "e"} aktiv`;

  live.forEach(m => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "mv-live-match";
    const apiId = String(m.match_id || "");
    const title = document.createElement("div");
    title.className = "mv-live-match-title";
    title.textContent = `${m.team_home} vs ${m.team_away}`;
    const time = document.createElement("div");
    time.className = "mv-live-match-time";
    const parts = formatMatchDateParts(m);
    time.textContent = `${parts.day} ${parts.time}`.trim();
    btn.appendChild(title);
    btn.appendChild(time);
    btn.addEventListener("click", async () => {
      if (!apiId) return;
      if (isOverviewPage) {
        goToRateMatch(m);
        return;
      }
      const sel = document.getElementById("matchesSelect");
      if (sel) sel.value = apiId;
      await onMatchChanged();
      await loadScenesByMatch(apiId);
      showTab("scene");
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
    listEl.appendChild(btn);
  });
}

async function initRatePage() {
  if (!isRatePage) return;
  if (!document.getElementById("sceneList")) return;
  const matchId = getMatchIdFromQuery();
  if (!matchId) {
    const main = document.querySelector(".mv-content");
    if (main) {
      main.innerHTML = `
        <section class="card">
          <h2>Kein Spiel ausgewählt</h2>
          <p>Bitte gehe zurück und wähle ein Spiel aus.</p>
          <a class="mv-btn mv-btn--primary mv-btn--md" href="/ratings.html">Zurück zur Übersicht</a>
        </section>
      `;
    }
    return;
  }

  setRateHeaderState("loading");

  const sel = document.getElementById("matchesSelect");
  if (sel) sel.value = matchId;
  document.getElementById("manualMatchId").value = matchId;

  await loadMatch(matchId);
  await onMatchChanged();
  await loadScenesByMatch(matchId);
  updateRateHeader(matchId);
  showTab("scene");
}

async function loadMatchesForRate() {
  const r = await apiFetch(`/matches?limit=500&offset=0`);
  const list = normalizeList(r.data);
  if (!list) return;

  allMatches.length = 0;
  Object.keys(matchCache).forEach(k => delete matchCache[k]);

  for (const m of list) {
    matchCache[m.match_id] = m;
    allMatches.push(m);
  }
}

async function loadMatch(matchId) {
  if (!matchId) return null;
  if (matchCache[matchId]) return matchCache[matchId];
  try {
    const r = await apiFetch(`/matches/${encodeURIComponent(matchId)}`);
    if (r.data && typeof r.data === "object" && r.data.match_id) {
      matchCache[r.data.match_id] = r.data;
      allMatches.push(r.data);
      return r.data;
    }
  } catch (e) {
    return null;
  }
  return null;
}

function initRatingsPage() {
  if (!document.getElementById("matchList")) return;
  const base = getApiBase();
  document.getElementById("apiBasePill").textContent = base;

  document.getElementById("matchLeagueFilter").addEventListener("change", onLeagueFilterChange);
  document.getElementById("matchWeekFilter").addEventListener("change", onWeekFilterChange);

  const loadScenesBtn = document.getElementById("loadScenesBtn");
  if (loadScenesBtn) {
    loadScenesBtn.addEventListener("click", async () => {
      const matchId = document.getElementById("matchesSelect")?.value || "";
      if (!matchId) return;
      goToRateId(matchId);
    });
  }

  const listEl = document.getElementById("matchList") || document.querySelector("[data-role='match-list']") || document;
  if (listEl && !listEl.dataset.matchClickBound) {
    listEl.dataset.matchClickBound = "true";
    listEl.addEventListener("click", (e) => {
      try {
        if (e.target.closest(".match-stat-link")) return;
        const card = e.target.closest("[data-match-id], .mv-match-card, .match-card, .mv-card-btn");
        if (!card) return;
        const id = card.dataset.matchId || "";
        if (!id) return;
        window.location.assign(`/rate.html?match_id=${encodeURIComponent(id)}`);
      } catch (err) {
        console.error("NAV ERROR", err);
      }
    });
  }

  initWeekNav();
  showTab("match");
  updateTabs();
  loadMatches();
}

function renderMatchList(list) {
  const listEl = document.getElementById("matchList");
  if (!listEl) return;
  listEl.innerHTML = "";

  if (!list || !list.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Keine Spiele verf\u00fcgbar.";
    listEl.appendChild(empty);
    return;
  }

  for (const m of list) {
    const btn = document.createElement("div");
    btn.className = "match-card";
    btn.setAttribute("role", "button");
    btn.setAttribute("tabindex", "0");
    const matchId = String(m.match_id || "");
    btn.dataset.matchId = matchId;
    if (!matchId) {
      btn.setAttribute("aria-disabled", "true");
      btn.title = "Dieses Spiel hat keine Match-ID.";
    }

    const time = document.createElement("div");
    time.className = "match-time";
    const parts = formatMatchDateParts(m);
    const day = document.createElement("div");
    day.textContent = parts.day || "";
    const clock = document.createElement("div");
    clock.textContent = parts.time || "";
    time.appendChild(day);
    time.appendChild(clock);

    const teams = document.createElement("div");
    teams.className = "match-teams";
    const home = document.createElement("div");
    home.textContent = m.team_home || "";
    const away = document.createElement("div");
    away.textContent = m.team_away || "";
    teams.appendChild(home);
    teams.appendChild(away);

    const meta = document.createElement("div");
    meta.className = "match-meta";
    const statLink = document.createElement("a");
    statLink.className = "match-league match-stat-link";
    statLink.innerHTML = `<span class="stat-count">—</span><span class="stat-star">★</span>`;
    statLink.setAttribute("aria-label", "Statistik");
    statLink.setAttribute("title", "Statistik");
    if (matchId) {
      statLink.href = `/match-stats.html?match_id=${encodeURIComponent(matchId)}`;
      loadMatchVoteCount(matchId, statLink);
    } else {
      statLink.href = "#";
      statLink.setAttribute("aria-disabled", "true");
      statLink.setAttribute("tabindex", "-1");
      statLink.classList.add("is-disabled");
    }
    meta.appendChild(statLink);

    btn.appendChild(time);
    btn.appendChild(teams);
    btn.appendChild(meta);

  listEl.appendChild(btn);
  }

  updateMatchListActive(document.getElementById("matchesSelect")?.value || "");
}

async function loadMatchVoteCount(matchId, targetEl) {
  if (!matchId || !targetEl) return;
  if (matchVoteCountCache[matchId] != null) {
    const cached = matchVoteCountCache[matchId];
    const countEl = targetEl.querySelector(".stat-count");
    if (countEl) countEl.textContent = String(cached);
    return;
  }

  let total = 0;
  try {
    const scenesUrl = `/scenes?match_id=${encodeURIComponent(matchId)}&limit=500&offset=0`;
    let r = await apiFetch(scenesUrl);
    let list = normalizeList(r.data);
    if (!list || list.length === 0) {
      const fallback = await apiFetch(`/scenes?limit=500&offset=0`);
      const allList = normalizeList(fallback.data);
      if (allList) {
        list = allList.filter(s => String(s.match_id) === String(matchId));
      }
    }
    if (list && list.length) {
      const ids = list.map(s => s.scene_id).filter(Boolean);
      const results = await Promise.all(ids.map(id => apiFetch(`/ratings?scene_id=${encodeURIComponent(id)}`)));
      for (const res of results) {
        const arr = Array.isArray(res.data) ? res.data : [];
        total += arr.length;
      }
    }
  } catch (e) {
    total = 0;
  }
  matchVoteCountCache[matchId] = total;
  const countEl = targetEl.querySelector(".stat-count");
  if (countEl) countEl.textContent = String(total);
}

async function loadScenesForMatchStats(matchId) {
  Object.keys(sceneCache).forEach(k => delete sceneCache[k]);
  if (!matchId) return;
  const scenesUrl = `/scenes?match_id=${encodeURIComponent(matchId)}&limit=500&offset=0`;
  let r = await apiFetch(scenesUrl);
  let list = normalizeList(r.data);
  if (!list || list.length === 0) {
    const fallback = await apiFetch(`/scenes?limit=500&offset=0`);
    const allList = normalizeList(fallback.data);
    if (allList) {
      list = allList.filter(s => String(s.match_id) === String(matchId));
    }
  }
  if (!list) return;
  list = list.filter(s => s.scene_type !== "GOAL");
  list.forEach(s => {
    if (s && s.scene_id) sceneCache[s.scene_id] = s;
  });
}

function setMatchStatsHeaderState(state) {
  const title = document.getElementById("statsMatchTitle");
  const sub = document.getElementById("statsMatchSub");
  if (!title || !sub) return;
  if (state === "loading") {
    title.textContent = "Lade Statistik…";
    sub.textContent = "Bitte warten...";
    return;
  }
  if (state === "notfound") {
    title.textContent = "Spiel nicht gefunden";
    sub.textContent = "";
  }
}

async function initMatchStatsPage() {
  const matchId = getMatchIdFromQuery();
  const main = document.querySelector(".mv-content");
  if (!matchId) {
    if (main) {
      main.innerHTML = `
        <section class="card">
          <h2>Kein Spiel ausgewählt</h2>
          <p>Bitte gehe zurück und wähle ein Spiel aus.</p>
          <a class="mv-btn mv-btn--primary mv-btn--md" href="/ratings.html">Zurück zur Übersicht</a>
        </section>
      `;
    }
    return;
  }

  document.getElementById("manualMatchId").value = matchId;
  setMatchStatsHeaderState("loading");

  const match = await loadMatch(matchId);
  if (match) {
    const title = document.getElementById("statsMatchTitle");
    const sub = document.getElementById("statsMatchSub");
    if (title) title.textContent = `${match.team_home || ""} vs ${match.team_away || ""}`.trim();
    if (sub) {
      const parts = formatMatchDateParts(match);
      const bits = [
        `${parts.day} ${parts.time}`.trim(),
        match.league || "",
        match.season || ""
      ].filter(Boolean);
      sub.textContent = bits.join(" · ");
    }
  } else {
    setMatchStatsHeaderState("notfound");
  }

  await loadScenesForMatchStats(matchId);
  await loadMatchRatingsSummary();
}

function updateSceneListActive(sceneId) {
  const listEl = document.getElementById("sceneList");
  if (!listEl) return;
  listEl.querySelectorAll("button[data-scene-id]").forEach(btn => {
    const active = String(btn.dataset.sceneId || "") === String(sceneId || "");
    btn.classList.toggle("active", active);
    btn.setAttribute("aria-selected", active ? "true" : "false");
  });
}

function renderSceneList(list) {
  const listEl = document.getElementById("sceneList");
  if (!listEl) return;
  listEl.innerHTML = "";

  if (!list || !list.length) {
    const empty = document.createElement("div");
    empty.className = "muted";
    empty.textContent = "Keine Szenen f\u00fcr dieses Spiel.";
    listEl.appendChild(empty);
    return;
  }

  const allBtn = document.createElement("button");
  allBtn.type = "button";
  allBtn.className = "scene-item";
  allBtn.dataset.sceneId = "__all__";
  allBtn.textContent = "Alle Szenen";
  allBtn.addEventListener("click", () => {
    const sel = document.getElementById("scenesSelect");
    if (sel) sel.value = "__all__";
    onSceneChanged("__all__");
    updateSceneListActive("__all__");
  });
  listEl.appendChild(allBtn);

  for (const s of list) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "scene-item";
    btn.dataset.sceneId = s.scene_id;
    const desc = getSceneDescription(s) || "";
    const short = desc.slice(0, 80) + (desc.length > 80 ? "..." : "");
    const label = getSceneTypeLabel(s);
    btn.textContent = `${s.minute}${s.stoppage_time ? "+" + s.stoppage_time : ""} - ${label} - ${short}`;
    btn.addEventListener("click", () => {
      const sel = document.getElementById("scenesSelect");
      if (sel) sel.value = s.scene_id;
      onSceneChanged(s.scene_id);
      updateSceneListActive(s.scene_id);
    });
    listEl.appendChild(btn);
  }
}
function formatSceneMeta(s) {
  const t = `${s.minute}${s.stoppage_time ? "+"+s.stoppage_time : ""}`;
  const rel = s.is_released ? "freigegeben" : "nicht freigegeben";
  const lock = s.is_locked ? "gesperrt" : "";
  const label = getSceneTypeLabel(s);
  return `${t} | ${label} | ${rel}${lock ? " | " + lock : ""}`;
}

function setDetailGrid(containerId, rows) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = "";
  if (!rows || !rows.length) return;

  for (const row of rows) {
    const item = document.createElement("div");
    item.className = "detail-item";

    const label = document.createElement("div");
    label.className = "detail-label";
    label.textContent = row.label;

    const value = document.createElement("div");
    value.className = "detail-value";
    value.textContent = (row.value === null || row.value === undefined || row.value === "") ? "-" : String(row.value);

    item.appendChild(label);
    item.appendChild(value);
    el.appendChild(item);
  }
}

function setSceneHeader(matchId, sceneId) {
  const title = document.getElementById("sceneTitle");
  const meta = document.getElementById("sceneMeta");
  const desc = document.getElementById("sceneDesc");
  const ratingDesc = document.getElementById("ratingSceneDesc");

  const m = matchCache[matchId];
  const s = sceneCache[sceneId];

  const matchFacts = [];
  const sceneFacts = [];

  if (m) {
    let d = "";
    try { d = new Date(m.match_date).toLocaleString("de-DE"); } catch { d = String(m.match_date || ""); }
    matchFacts.push({ label: "Liga", value: m.league });
    matchFacts.push({ label: "Saison", value: m.season });
    matchFacts.push({ label: "Heim", value: m.team_home });
    matchFacts.push({ label: "Gast", value: m.team_away });
    matchFacts.push({ label: "Datum", value: d });
  }

  if (!s) {
    title.textContent = "Keine Szene gew\u00e4hlt";
    meta.innerHTML = "";
    desc.textContent = "W\u00e4hle ein Spiel und eine Szene, um Details zu sehen.";
    if (ratingDesc) ratingDesc.textContent = "W\u00e4hle eine Szene, um die Beschreibung zu sehen.";
    setDetailGrid("matchFacts", matchFacts);
    setDetailGrid("sceneFacts", sceneFacts);
    return;
  }

  title.textContent = getSceneTypeLabel(s) || "Szene";
  meta.innerHTML = "";

  const pills = [];
  if (s.minute != null) pills.push({ txt: `${s.minute}${s.stoppage_time ? "+" + s.stoppage_time : ""}` });
  const sceneLabel = getSceneTypeLabel(s);
  if (sceneLabel) pills.push({ txt: sceneLabel });
  if (s.is_released != null) pills.push({ txt: s.is_released ? "Freigegeben" : "Nicht freigegeben" });

  for (const p of pills) {
    const el = document.createElement("span");
    el.className = "pill";
    el.textContent = p.txt;
    meta.appendChild(el);
  }

  const descTxt = getSceneDescription(s) || "-";
  desc.textContent = descTxt;
  if (ratingDesc) ratingDesc.textContent = descTxt;

  sceneFacts.push({ label: "Typ", value: sceneLabel || "-" });
  sceneFacts.push({ label: "Minute", value: `${s.minute}${s.stoppage_time ? "+" + s.stoppage_time : ""}` });
  if (descTxt && descTxt !== "-") sceneFacts.push({ label: "Beschreibung", value: descTxt });

  setDetailGrid("matchFacts", matchFacts);
  setDetailGrid("sceneFacts", sceneFacts);
}

function updateFavTeamOptions(matchId, allowFetch = true) {
  const sel = document.getElementById("rateFavTeam");
  if (!sel) return;
  sel.innerHTML = "";
  const optNone = document.createElement("option");
  optNone.value = "";
  optNone.textContent = "Kein Team";
  sel.appendChild(optNone);

  const m = matchCache[matchId];
  if (!m && matchId && allowFetch) {
    apiFetch(`/matches/${encodeURIComponent(matchId)}`)
      .then(r => {
        if (r.data && r.data.match_id) {
          matchCache[r.data.match_id] = r.data;
          updateFavTeamOptions(matchId, false);
        }
      })
      .catch(() => {});
    return;
  }
  if (!m) return;
  const teams = [m.team_home, m.team_away].filter(Boolean);
  for (const t of teams) {
    const opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    sel.appendChild(opt);
  }
}

function updateTabs() {
  const matchId = document.getElementById("matchesSelect")?.value || "";
  const sceneId = document.getElementById("scenesSelect")?.value || "";
  const btnScene = document.getElementById("tabBtnScene");
  const btnRating = document.getElementById("tabBtnRating");

  const canScene = !!matchId && scenesLoadedMatchId === matchId;
  const canRating = !!matchId && !!sceneId;

  if (btnScene) btnScene.style.display = canScene ? "inline-flex" : "none";
  if (btnRating) btnRating.style.display = canRating ? "inline-flex" : "none";

  if (currentTab === "scene" && !canScene) showTab("match");
  if (currentTab === "rating" && !canRating) showTab(canScene ? "scene" : "match");
}

function updateMatchSummaryVisibility() {
  const box = document.getElementById("matchSummaryBox");
  if (!box) return;

  const matchId = document.getElementById("matchesSelect")?.value || "";
  const manualSceneId = document.getElementById("manualSceneId")?.value || "";
  const canShow = !!matchId && !manualSceneId && Object.keys(sceneCache).length > 0;

  box.style.display = canShow ? "block" : "none";
  if (canShow) loadMatchRatingsSummary();
}

function showTab(name) {
  currentTab = name;
  const tabMatch = document.getElementById("tabMatch");
  const tabScene = document.getElementById("tabScene");
  const tabRating = document.getElementById("ratingSection");
  const btnMatch = document.getElementById("tabBtnMatch");
  const btnScene = document.getElementById("tabBtnScene");
  const btnRating = document.getElementById("tabBtnRating");

  if (tabMatch) tabMatch.style.display = (name === "match") ? "block" : "none";
  if (tabScene) tabScene.style.display = (name === "scene") ? "block" : "none";
  if (tabRating) tabRating.style.display = (name === "rating") ? "block" : "none";

  if (btnMatch) btnMatch.classList.toggle("active", name === "match");
  if (btnScene) btnScene.classList.toggle("active", name === "scene");
  if (btnRating) btnRating.classList.toggle("active", name === "rating");

  if (name === "scene") {
    window.scrollTo({ top: 0, behavior: "smooth" });
    updateMatchSummaryVisibility();
  }
}

function getFilteredMatches() {
  const league = document.getElementById("matchLeagueFilter")?.value || "";
  const week = document.getElementById("matchWeekFilter")?.value || "";
  const list = allMatches.filter(m => {
    const leagueOk = !league || m.league === league;
    const weekOk = !week || getMatchdayKey(m) === week;
    return leagueOk && weekOk;
  });
  list.sort((a, b) => new Date(a.match_date) - new Date(b.match_date));
  return list;
}

function populateMatchesSelect(matches) {
  const sel = document.getElementById("matchesSelect");
  sel.innerHTML = "";
  renderMatchList(matches);

  for (const m of matches) {
    const opt = document.createElement("option");
    opt.value = String(m.match_id || "");
    opt.textContent = formatMatchMeta(m);
    sel.appendChild(opt);
  }
}

function formatMatchMeta(match) {
  // must never throw
  const m = match || {};
  const league = (m.league || m.league_key || m.league_code || m.league_name || "").toString().trim();
  const dt = (m.kickoff_at || m.kickoff || m.match_date || m.utc_date || m.date || "").toString().trim();
  const md = (m.matchday || m.round || m.match_day || "").toString().trim();
  const parts = [];
  if (league) parts.push(league);
  if (md) parts.push(`ST ${md}`);
  if (dt) parts.push(dt);
  return parts.filter(Boolean).join(" · ");
}

async function applyMatchFilters() {
  const matches = getFilteredMatches();
  populateMatchesSelect(matches);

  if (matches.length) {
    if (isOverviewPage) {
      const sel = document.getElementById("matchesSelect");
      if (sel) sel.selectedIndex = -1;
      updateMatchListActive("");
      return;
    }
    const preset = document.getElementById("manualMatchId")?.value || "";
    const sel = document.getElementById("matchesSelect");
    if (sel && preset) {
      const opt = [...sel.options].find(o => o.value === preset);
      if (opt) sel.value = preset;
    } else if (sel) {
      sel.selectedIndex = 0;
    }
    await onMatchChanged();
  } else {
    document.getElementById("manualMatchId").value = "";
    scenesLoadedMatchId = "";
    const sceneSel = document.getElementById("scenesSelect");
    if (sceneSel) sceneSel.innerHTML = "";
    Object.keys(sceneCache).forEach(k => delete sceneCache[k]);
    renderSceneList([]);
    updateFavTeamOptions("");
    setSceneHeader("", null);
    setAggregateStars(null, null, 0);
    updateTabs();
    updateMatchSummaryVisibility();
  }
}

function onLeagueFilterChange() {
  const league = document.getElementById("matchLeagueFilter")?.value || "";
  const subset = league ? allMatches.filter(m => m.league === league) : allMatches;
  const currentWeek = document.getElementById("matchWeekFilter")?.value || "";
  buildWeekOptions(subset, currentWeek);
  applyMatchFilters();
  syncFilterButtons();
}

function onWeekFilterChange() {
  applyMatchFilters();
  syncFilterButtons();
}
// ---------- Load matches/scenes ----------
async function loadMatches() {
  const sel = document.getElementById("matchesSelect");
  sel.innerHTML = "";
  const r = await apiFetch(`/matches?limit=500&offset=0`);
  const list = normalizeList(r.data);
  if (!list) return;

  allMatches.length = 0;
  Object.keys(matchCache).forEach(k => delete matchCache[k]);

  for (const m of list) {
    matchCache[m.match_id] = m;
    allMatches.push(m);
  }

  renderLiveMatches(allMatches);
  buildLeagueOptions(allMatches);
  buildWeekOptions(allMatches);
  await applyMatchFilters();
}

async function loadScenesByMatch(matchId) {
  const sel = document.getElementById("scenesSelect");
  sel.innerHTML = "";
  Object.keys(sceneCache).forEach(k => delete sceneCache[k]);
  renderSceneList([]);

  if (!matchId || matchId === "undefined" || matchId === "null") {
    setSceneHeader("", null);
    setAggregateStars(null, null, 0);
    scenesLoadedMatchId = "";
    return;
  }

  const scenesUrl = `/scenes?match_id=${encodeURIComponent(matchId)}&limit=500&offset=0`;
  let r = await apiFetch(scenesUrl);
  let list = normalizeList(r.data);

  if (!list || list.length === 0) {
    const fallback = await apiFetch(`/scenes?limit=500&offset=0`);
    const allList = normalizeList(fallback.data);
    if (allList) {
      list = allList.filter(s => String(s.match_id) === String(matchId));
    }
  }

  if (!list) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Szenen konnten nicht geladen werden.";
    sel.appendChild(opt);
    setSceneHeader(matchId, null);
    setAggregateStars(null, null, 0);
    scenesLoadedMatchId = "";
    renderSceneList([]);
    updateTabs();
    return;
  }

  list = list.filter(s => s.scene_type !== "GOAL");

  list.sort((a, b) => {
    const aMin = (Number(a.minute) || 0) * 100 + (Number(a.stoppage_time) || 0);
    const bMin = (Number(b.minute) || 0) * 100 + (Number(b.stoppage_time) || 0);
    return bMin - aMin;
  });

  if (list.length) {
    const optAll = document.createElement("option");
    optAll.value = "__all__";
    optAll.textContent = "Alle Szenen";
    sel.appendChild(optAll);
    sel.selectedIndex = 0;
    sel.value = "__all__";
  }

  for (const s of list) {
    sceneCache[s.scene_id] = s;
    const opt = document.createElement("option");
    opt.value = s.scene_id;
    const desc = getSceneDescription(s) || "";
    const short = desc.slice(0, 60) + (desc.length > 60 ? "..." : "");
    const label = getSceneTypeLabel(s);
    opt.textContent = `${s.minute}${s.stoppage_time ? "+" + s.stoppage_time : ""} - ${label} - ${short}`;
    sel.appendChild(opt);
  }

  if (list.length) {
    document.getElementById("manualSceneId").value = "";
    setSceneHeader(matchId, null);
    setAggregateStars(null, null, 0);
    scenesLoadedMatchId = matchId;
    renderSceneList(list);
    updateSceneListActive("__all__");
    updateTabs();
    updateMatchSummaryVisibility();
  } else {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "Keine Szenen f\u00fcr dieses Spiel.";
    sel.appendChild(opt);
    document.getElementById("manualSceneId").value = "";
    setSceneHeader(matchId, null);
    setAggregateStars(null, null, 0);
    scenesLoadedMatchId = "";
    renderSceneList([]);
    updateTabs();
    updateMatchSummaryVisibility();
  }
}

async function onMatchChanged() {
  const matchId = document.getElementById("matchesSelect")?.value || document.getElementById("manualMatchId")?.value || "";
  document.getElementById("manualMatchId").value = matchId;
  document.getElementById("manualSceneId").value = "";
  renderSceneList([]);
  scenesLoadedMatchId = "";
  const sceneSel = document.getElementById("scenesSelect");
  if (sceneSel) {
    sceneSel.innerHTML = "";
    const opt = document.createElement("option");
    opt.value = "__all__";
    opt.textContent = "Alle Szenen";
    sceneSel.appendChild(opt);
    sceneSel.value = "__all__";
  }
  setSceneHeader(matchId, null);
  setAggregateStars(null, null, 0);
  updateFavTeamOptions(matchId);
  updateTabs();
  updateMatchListActive(matchId);
  updateRateHeader(matchId);

  updateMatchSummaryVisibility();
}

async function onSceneChanged(sceneIdOverride = "") {
  const matchSel = document.getElementById("matchesSelect");
  const sceneSel = document.getElementById("scenesSelect");
  const notice = document.getElementById("sceneNotice");
  const sceneId = sceneIdOverride || sceneSel?.value || "";
  let matchId = matchSel?.value || document.getElementById("manualMatchId")?.value || scenesLoadedMatchId || "";

  if (matchId && matchSel && matchSel.value !== matchId) {
    matchSel.value = matchId;
  }
  if (matchId) {
    document.getElementById("manualMatchId").value = matchId;
  }

  if (notice) {
    notice.textContent = "";
    notice.style.display = "none";
  }

  if (!matchId && sceneId && sceneCache[sceneId]?.match_id) {
    matchId = String(sceneCache[sceneId].match_id);
    if (matchSel) matchSel.value = matchId;
    document.getElementById("manualMatchId").value = matchId;
  }

  if (sceneSel && sceneId) sceneSel.value = sceneId;
  if (sceneId === "__all__") {
    document.getElementById("manualSceneId").value = "";
    setSceneHeader(matchId, null);
    updateSceneListActive("__all__");
    updateFavTeamOptions(matchId);
    if (matchId) scenesLoadedMatchId = matchId;
    showTab("scene");
    const box = document.getElementById("matchSummaryBox");
    if (box) box.style.display = matchId ? "block" : "none";
    if (matchId) {
      await loadMatchRatingsSummary();
      if (box) box.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    return;
  }
  document.getElementById("manualSceneId").value = sceneId;

  setSceneHeader(matchId, sceneId);
  updateFavTeamOptions(matchId);
  updateTabs();
  updateSceneListActive(sceneId);
  if (matchId && sceneId) {
    const r = await apiFetch(`/ratings/me/${encodeURIComponent(sceneId)}`);
    if (r.res && r.res.status === 200) {
      if (notice) {
        notice.textContent = "Du hast diese Szene bereits bewertet.";
        notice.style.display = "block";
      }
      showTab("scene");
      updateMatchSummaryVisibility();
      return;
    }

    showTab("rating");
    const rating = document.getElementById("ratingSection");
    if (rating) rating.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  updateMatchSummaryVisibility();

  resetRatingStars();
  loadAggregate();
}

async function reloadFromManual() {
  const mid = document.getElementById("manualMatchId").value.trim();
  const sid = document.getElementById("manualSceneId").value.trim();

  if (mid) {
    const matchSel = document.getElementById("matchesSelect");
    if (matchSel) matchSel.value = mid;
    await loadScenesByMatch(mid);
    updateFavTeamOptions(mid);
  }

  if (sid) {
    const sceneSel = document.getElementById("scenesSelect");
    const opt = [...sceneSel.options].find(o => o.value === sid);
    if (opt) sceneSel.value = sid;

    if (!sceneCache[sid]) {
      const r = await apiFetch(`/scenes/${encodeURIComponent(sid)}`);
      if (r.data && typeof r.data === "object" && r.data.scene_id) {
        sceneCache[r.data.scene_id] = r.data;
      }
    }

    setSceneHeader(mid, sid);
    resetRatingStars();
    loadAggregate();
  }
}

function clamp(n, min, max) { return Math.max(min, Math.min(max, n)); }

function setAriaForGroup(groupEl, value) {
  const stars = [...groupEl.querySelectorAll("span[data-value]")];
  stars.forEach(star => {
    const v = Number(star.dataset.value);
    star.setAttribute("aria-checked", (v === Number(value)) ? "true" : "false");
  });
}

function highlightStars(groupEl, value) {
  const stars = [...groupEl.querySelectorAll("span[data-value]")];
  stars.forEach(s => {
    const on = Number(s.dataset.value) <= Number(value || 0);
    s.classList.toggle("active", on);
    s.classList.remove("hover");
  });
  setAriaForGroup(groupEl, value);
}

function hoverStars(groupEl, value) {
  const stars = [...groupEl.querySelectorAll("span[data-value]")];
  stars.forEach(s => {
    const on = Number(s.dataset.value) <= Number(value || 0);
    s.classList.toggle("hover", on);
  });
}

function showError(fieldId, show) {
  const el = document.getElementById(fieldId + "_error");
  if (!el) return;
  el.style.display = show ? "block" : "none";
}

function validateRatingStars() {
  const d = Number(document.getElementById("rateDecision").value || 0);
  const c = Number(document.getElementById("rateConfidence").value || 0);

  const dOk = d >= 1 && d <= 5;
  const cOk = c >= 1 && c <= 5;

  showError("rateDecision", !dOk);
  showError("rateConfidence", !cOk);

  document.getElementById("sendRatingBtn").disabled = !(dOk && cOk);

  return dOk && cOk;
}

function resetRatingStars() {
  document.getElementById("rateDecision").value = "";
  document.getElementById("rateConfidence").value = "";

  document.querySelectorAll(".star-rating").forEach(group => {
    const field = group.dataset.field;
    const input = document.getElementById(field);
    highlightStars(group, input.value);
  });

  showError("rateDecision", false);
  showError("rateConfidence", false);
  validateRatingStars();
}

function wireStars() {
  document.querySelectorAll(".star-rating").forEach(group => {
    const field = group.dataset.field;
    const input = document.getElementById(field);
    const stars = [...group.querySelectorAll("span[data-value]")];

    highlightStars(group, input.value);

    stars.forEach(star => {
      star.addEventListener("mouseenter", () => hoverStars(group, star.dataset.value));
      star.addEventListener("mouseleave", () => hoverStars(group, 0));

      star.addEventListener("click", () => {
        input.value = star.dataset.value;
        highlightStars(group, input.value);
        validateRatingStars();
      });

      star.addEventListener("keydown", (e) => {
        const current = Number(input.value || 0);

        if (e.key === "ArrowRight" || e.key === "ArrowUp") {
          e.preventDefault();
          const next = clamp(current + 1, 1, 5);
          input.value = String(next);
          highlightStars(group, input.value);
          const target = group.querySelector(`span[data-value="${next}"]`);
          if (target) target.focus();
          validateRatingStars();
        }

        if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
          e.preventDefault();
          const next = clamp(current - 1, 1, 5);
          input.value = String(next);
          highlightStars(group, input.value);
          const target = group.querySelector(`span[data-value="${next}"]`);
          if (target) target.focus();
          validateRatingStars();
        }

        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          input.value = star.dataset.value;
          highlightStars(group, input.value);
          validateRatingStars();
        }
      });
    });
  });

  validateRatingStars();
}
function wireChoiceGroup(groupId, selectId) {
  const group = document.getElementById(groupId);
  const select = document.getElementById(selectId);
  if (!group || !select) return;

  const buttons = [...group.querySelectorAll("button[data-value]")];

  function sync(value) {
    buttons.forEach(btn => {
      const active = String(btn.dataset.value || "") === String(value || "");
      btn.classList.toggle("active", active);
    });
  }

  buttons.forEach(btn => {
    btn.addEventListener("click", () => {
      select.value = btn.dataset.value || "";
      sync(select.value);
    });
  });

  select.addEventListener("change", () => sync(select.value));
  sync(select.value);
}

function renderReadonlyStars(targetEl, value, opts = { showHalf: true }) {
  const v = Number(value);
  if (!targetEl || Number.isNaN(v)) {
    if (targetEl) targetEl.innerHTML = "";
    return null;
  }

  const rounded = opts.showHalf ? Math.round(v * 2) / 2 : Math.round(v);
  const full = Math.floor(rounded);
  const half = (rounded - full) >= 0.5 ? 1 : 0;

  const wrap = document.createElement("span");
  wrap.className = "stars-readonly";

  for (let i = 1; i <= 5; i++) {
    const star = document.createElement("span");
    star.className = "star";
    star.textContent = "\u2605";
    if (i <= full) star.classList.add("filled");
    if (i === full + 1 && half === 1) star.classList.add("half");
    wrap.appendChild(star);
  }

  targetEl.innerHTML = "";
  targetEl.appendChild(wrap);
  return { rounded };
}

function setAggregateStars(avgDecision, avgConfidence, ratingCount) {
  const dEl = document.getElementById("avgDecisionStars");
  const cEl = document.getElementById("avgConfidenceStars");
  const dMeta = document.getElementById("avgDecisionMeta");
  const cMeta = document.getElementById("avgConfidenceMeta");
  const cnt = document.getElementById("ratingCountPill");

  if (ratingCount != null) cnt.textContent = String(ratingCount);

  if (avgDecision == null || avgConfidence == null) {
    if (dEl) dEl.innerHTML = "";
    if (cEl) cEl.innerHTML = "";
    if (dMeta) dMeta.textContent = "";
    if (cMeta) cMeta.textContent = "";
    return;
  }

  const d = renderReadonlyStars(dEl, avgDecision);
  const c = renderReadonlyStars(cEl, avgConfidence);

  if (dMeta && d) dMeta.textContent = `(${Number(avgDecision).toFixed(2)} ~ ${d.rounded.toFixed(1)})`;
  if (cMeta && c) cMeta.textContent = `(${Number(avgConfidence).toFixed(2)} ~ ${c.rounded.toFixed(1)})`;
}

async function loadAggregate() {
  const sid = document.getElementById("manualSceneId").value.trim() || document.getElementById("scenesSelect").value || "";
  if (!sid) {
    setAggregateStars(null, null, 0);
    return;
  }

  try {
    const r = await apiFetch(`/scenes/${encodeURIComponent(sid)}/aggregate`);
    if (r.data && typeof r.data === "object") {
      setAggregateStars(r.data.avg_decision, r.data.avg_confidence, r.data.rating_count);
    } else {
      setAggregateStars(null, null, 0);
    }
  } catch (e) {
    setAggregateStars(null, null, 0);
  }
}

async function sendRating() {
  if (!validateRatingStars()) return;

  const scene_id = document.getElementById("manualSceneId").value.trim() || document.getElementById("scenesSelect").value || "";

  if (!scene_id) return logOut("ratingOut", "Keine Szene gew\u00e4hlt.");
  const body = {
    scene_id,
    decision_score: Number(document.getElementById("rateDecision").value),
    confidence_score: Number(document.getElementById("rateConfidence").value),
    perception_channel: document.getElementById("rateChannel").value,
    rule_knowledge: document.getElementById("rateRule").value,
    rating_time_type: document.getElementById("rateTimeType").value
  };
  const favTeam = document.getElementById("rateFavTeam")?.value || "";
  if (favTeam) body.fav_team = favTeam;

  try {
    const r = await apiFetch("/ratings", {
      method:"POST",
      headers:{ "Content-Type":"application/json" },
      body: JSON.stringify(body)
    });
    if (r.res.status === 201 || r.res.status === 200) {
      logOut("ratingOut", "Bewertung gespeichert.");
      await loadAggregate();
      showTab("scene");
    } else {
      logOut("ratingOut", "Bewertung konnte nicht gespeichert werden.");
    }
  } catch (e) {
    logOut("ratingOut", "Bewertung konnte nicht gespeichert werden.");
  }
}

function safeNum(n) {
  const x = Number(n);
  return Number.isFinite(x) ? x : 0;
}

function mergeDist(target, addDist) {
  if (!addDist || typeof addDist !== "object") return;
  for (const [k, v] of Object.entries(addDist)) {
    target[k] = (target[k] || 0) + safeNum(v);
  }
}

function renderBars(containerId, distObj, orderKeys, labelFormatter = null) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const entries = orderKeys
    ? orderKeys.map(k => [k, distObj[k] || 0])
    : Object.entries(distObj).sort((a,b) => b[1]-a[1]);

  const total = entries.reduce((s, [,v]) => s + safeNum(v), 0);

  el.innerHTML = "";
  if (!total) {
    el.innerHTML = `<div class="muted">Noch keine Daten.</div>`;
    return;
  }

  for (const [k, v] of entries) {
    const pct = (safeNum(v) / total) * 100;

    const row = document.createElement("div");
    row.className = "barRow";

    const head = document.createElement("div");
    head.className = "barHeader";

    const lab = document.createElement("div");
    lab.className = "barLabel";
    lab.textContent = labelFormatter ? labelFormatter(k) : k;

    const val = document.createElement("div");
    val.className = "barValue";
    val.textContent = `${v} (${pct.toFixed(0)}%)`;

    head.appendChild(lab);
    head.appendChild(val);

    const track = document.createElement("div");
    track.className = "barTrack";

    const fill = document.createElement("div");
    fill.className = "barFill";
    fill.style.width = pct.toFixed(1) + "%";
    track.appendChild(fill);

    row.appendChild(head);
    row.appendChild(track);

    el.appendChild(row);
  }
}

function calcAvgFromDist(distObj) {
  let sum = 0, cnt = 0;
  for (const [k, v] of Object.entries(distObj || {})) {
    const score = Number(k);
    const n = safeNum(v);
    if (score >= 1 && score <= 5) {
      sum += score * n;
      cnt += n;
    }
  }
  return cnt ? (sum / cnt) : null;
}

function pickScene(sceneId) {
  const sceneSel = document.getElementById("scenesSelect");
  const opt = [...sceneSel.options].find(o => o.value === sceneId);
  if (opt) {
    sceneSel.value = sceneId;
    onSceneChanged();
    window.scrollTo({ top: 0, behavior: "smooth" });
  } else {
    document.getElementById("manualSceneId").value = sceneId;
    reloadFromManual();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
}

async function loadMatchRatingsSummary() {
  const matchId = document.getElementById("manualMatchId").value.trim() || document.getElementById("matchesSelect")?.value || "";
  if (!matchId) return;

  const scenes = Object.values(sceneCache || {});
  if (!scenes.length) return;

  const decisionDist = { "1":0,"2":0,"3":0,"4":0,"5":0 };
  const confidenceDist = { "1":0,"2":0,"3":0,"4":0,"5":0 };
  const channelDist = {};
  const timeDist = {};

  let totalRatings = 0;
  let ratedScenes = 0;

  const sceneRows = [];

  const box = document.getElementById("matchSummaryBox");
  box.style.display = "block";
  document.getElementById("sumTotalRatings").textContent = "l\u00e4dt...";
  document.getElementById("sumRatedScenes").textContent = "";

  for (const s of scenes) {
    try {
      const r = await apiFetch(`/ratings?scene_id=${encodeURIComponent(s.scene_id)}`);
      const list = Array.isArray(r.data) ? r.data : [];
      const cnt = list.length;

      if (cnt > 0) ratedScenes++;
      totalRatings += cnt;

      const d = { "1":0,"2":0,"3":0,"4":0,"5":0 };
      const c = { "1":0,"2":0,"3":0,"4":0,"5":0 };
      const ch = {};
      const tt = {};

      for (const it of list) {
        const ds = String(it.decision_score);
        const cs = String(it.confidence_score);
        if (d[ds] != null) d[ds] += 1;
        if (c[cs] != null) c[cs] += 1;

        const pch = it.perception_channel || "UNKNOWN";
        const rtt = it.rating_time_type || "UNKNOWN";
        ch[pch] = (ch[pch] || 0) + 1;
        tt[rtt] = (tt[rtt] || 0) + 1;
      }

      mergeDist(decisionDist, d);
      mergeDist(confidenceDist, c);
      mergeDist(channelDist, ch);
      mergeDist(timeDist, tt);

      const avgD = cnt ? list.reduce((a,x)=>a+safeNum(x.decision_score),0)/cnt : null;
      const avgC = cnt ? list.reduce((a,x)=>a+safeNum(x.confidence_score),0)/cnt : null;

      const sceneDesc = getSceneDescription(s) || "";
      sceneRows.push({
        scene_id: s.scene_id,
        minute: `${s.minute}${s.stoppage_time ? "+" + s.stoppage_time : ""}`,
        scene_type: getSceneTypeLabel(s),
        description: sceneDesc.slice(0, 90) + (sceneDesc.length > 90 ? "..." : ""),
        rating_count: cnt,
        avg_decision: avgD,
        avg_confidence: avgC
      });

    } catch (e) {
      const sceneDesc = getSceneDescription(s) || "";
      sceneRows.push({
        scene_id: s.scene_id,
        minute: `${s.minute}${s.stoppage_time ? "+" + s.stoppage_time : ""}`,
        scene_type: getSceneTypeLabel(s),
        description: sceneDesc.slice(0, 90) + (sceneDesc.length > 90 ? "..." : ""),
        rating_count: 0,
        avg_decision: null,
        avg_confidence: null
      });
    }
  }

  sceneRows.sort((a,b) => (b.rating_count - a.rating_count));

  const avgDecision = calcAvgFromDist(decisionDist);
  const avgConfidence = calcAvgFromDist(confidenceDist);

  document.getElementById("sumTotalRatings").textContent = `${totalRatings} Bewertungen`;
  document.getElementById("sumRatedScenes").textContent = `${ratedScenes} Szenen bewertet`;

  const dEl = document.getElementById("sumAvgDecisionStars");
  const cEl = document.getElementById("sumAvgConfidenceStars");
  const dMeta = document.getElementById("sumAvgDecisionMeta");
  const cMeta = document.getElementById("sumAvgConfidenceMeta");

  if (avgDecision != null) {
    const d = renderReadonlyStars(dEl, avgDecision);
    dMeta.textContent = `(${avgDecision.toFixed(2)} ~ ${d.rounded.toFixed(1)})`;
  } else { dEl.innerHTML = ""; dMeta.textContent = ""; }

  if (avgConfidence != null) {
    const c = renderReadonlyStars(cEl, avgConfidence);
    cMeta.textContent = `(${avgConfidence.toFixed(2)} ~ ${c.rounded.toFixed(1)})`;
  } else { cEl.innerHTML = ""; cMeta.textContent = ""; }

  setAggregateStars(avgDecision, avgConfidence, totalRatings);

  renderBars("sumDecisionDist", decisionDist, ["1","2","3","4","5"]);
  renderBars("sumConfidenceDist", confidenceDist, ["1","2","3","4","5"]);
  renderBars("sumChannelDist", channelDist, ["TV","STADIUM","STREAM","HIGHLIGHT","UNKNOWN"], getChannelLabel);
  renderBars("sumTimeDist", timeDist, ["LIVE","AFTER_REPLAY","AFTER_VAR","LATER","UNKNOWN"], getTimeLabel);

  // Scene table removed in favor of a jump button for mobile UX.
}

function init() {
  const page = document.body?.dataset?.page || "";
  if (page === "ratings") {
    initRatingsPage();
    return;
  }
  if (page === "rate") {
    const base = getApiBase();
    const pill = document.getElementById("apiBasePill");
    if (pill) pill.textContent = base;
    if (!document.getElementById("sceneList")) return;
    document.getElementById("scenesSelect").addEventListener("change", onSceneChanged);
    wireStars();
    wireChoiceGroup("channelChoices", "rateChannel");
    wireChoiceGroup("ruleChoices", "rateRule");
    wireChoiceGroup("timeChoices", "rateTimeType");
    initRatePage();
    return;
  }
  if (page === "match-stats") {
    const base = getApiBase();
    const pill = document.getElementById("apiBasePill");
    if (pill) pill.textContent = base;
    initMatchStatsPage();
    return;
  }
}

document.addEventListener("DOMContentLoaded", init);


