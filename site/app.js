/* SoundDirector library browser. No dependencies; data comes from data.js (window.SOUND_LIBRARY). */
(() => {
  "use strict";

  const LIB = window.SOUND_LIBRARY || { skills: {} };
  const SKILLS = ["sound-effects", "background-music"];
  const SHORT = { "sound-effects": "sfx", "background-music": "music" };
  const LONG = { sfx: "sound-effects", music: "background-music" };
  const PAGE = 60;
  const CATEGORY_NAMES = {
    "ui-clicks": "UI clicks", transitions: "Transitions", notifications: "Notifications", "tech-ai": "Tech & AI",
    impacts: "Impacts", "edu-diagrams": "Diagrams", ambience: "Ambience", cinematic: "Cinematic",
    education: "Education", technology: "Technology", suspense: "Suspense", vlog: "Vlog", reels: "Reels & shorts",
    corporate: "Corporate", playful: "Playful", "ambient-focus": "Ambient & focus",
  };
  const FIELD_WEIGHTS = [["title", 3], ["tags", 3], ["moods", 3], ["category", 2], ["use_cases", 2],
    ["preferred_content_types", 2], ["description", 1], ["id", 1]];

  const $ = (sel, el = document) => el.querySelector(sel);
  const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const catName = c => CATEGORY_NAMES[c] || c;
  const fmtDur = s => {
    if (!isFinite(s)) return "–";
    if (s < 10) return s.toFixed(1) + "s";
    const m = Math.floor(s / 60), r = Math.round(s % 60);
    return r === 60 ? `${m + 1}:00` : `${m}:${String(r).padStart(2, "0")}`;
  };
  const stem = w => w.length > 4 ? w.replace(/(ing|ed|es|s)$/, "") : w;
  const tokens = text => String(text || "").toLowerCase().split(/[^a-z0-9]+/).filter(Boolean).map(stem);

  // Pre-index every asset once.
  for (const skill of SKILLS) {
    for (const a of LIB.skills[skill] || []) {
      a.skill = skill;
      a._fields = FIELD_WEIGHTS.map(([k, w]) => {
        const v = a[k];
        return [tokens(Array.isArray(v) ? v.join(" ") : v), w];
      });
    }
  }

  // ---------- state ----------
  const state = { skill: "sound-effects", q: "", cat: "", level: "any", mood: "", length: "any", sort: "relevance", shown: PAGE };

  function readHash() {
    const p = new URLSearchParams(location.hash.slice(1));
    state.skill = LONG[p.get("s")] || "sound-effects";
    state.q = p.get("q") || "";
    state.cat = p.get("c") || "";
    state.level = p.get("l") || "any";
    state.mood = p.get("m") || "";
    state.length = p.get("d") || "any";
    state.sort = p.get("o") || "relevance";
  }
  function writeHash() {
    const p = new URLSearchParams();
    p.set("s", SHORT[state.skill]);
    if (state.q) p.set("q", state.q);
    if (state.cat) p.set("c", state.cat);
    if (state.level !== "any") p.set("l", state.level);
    if (state.mood) p.set("m", state.mood);
    if (state.length !== "any") p.set("d", state.length);
    if (state.sort !== "relevance") p.set("o", state.sort);
    history.replaceState(null, "", "#" + p.toString());
  }

  // ---------- search ----------
  function score(a, terms) {
    let total = 0, matched = 0;
    for (const t of terms) {
      let s = 0;
      for (const [toks, w] of a._fields) if (toks.some(x => x === t || x.startsWith(t))) s += w;
      if (s) { matched++; total += s; }
    }
    if (terms.length && matched === terms.length) total += 2;
    return { total, all: matched === terms.length };
  }
  const LEVELS = { subtle: [1, 2], medium: [3, 3], strong: [4, 5], low: [1, 2], mid: [3, 3], high: [4, 5] };
  const LENGTHS = { short: [0, 40], medium: [40, 100], long: [100, Infinity] };

  function passesFilters(a) {
    if (state.cat && a.category !== state.cat) return false;
    const lv = LEVELS[state.level];
    const n = a.skill === "sound-effects" ? a.intensity : a.energy;
    if (lv && !(n >= lv[0] && n <= lv[1])) return false;
    if (a.skill === "background-music") {
      if (state.mood && !(a.moods || []).includes(state.mood)) return false;
      const ln = LENGTHS[state.length];
      if (ln && !(a.duration_seconds >= ln[0] && a.duration_seconds < ln[1])) return false;
    }
    return true;
  }

  function results() {
    const pool = (LIB.skills[state.skill] || []).filter(passesFilters);
    const terms = tokens(state.q);
    let rows = pool.map(a => ({ a, ...(terms.length ? score(a, terms) : { total: 0, all: true }) }));
    let partial = false;
    if (terms.length) {
      const exact = rows.filter(r => r.all);
      if (exact.length) rows = exact;
      else { rows = rows.filter(r => r.total > 0); partial = rows.length > 0; }
    }
    const byId = (x, y) => x.a.id.localeCompare(y.a.id);
    const sorts = {
      relevance: (x, y) => (y.total - x.total) || byId(x, y),
      short: (x, y) => (x.a.duration_seconds - y.a.duration_seconds) || byId(x, y),
      long: (x, y) => (y.a.duration_seconds - x.a.duration_seconds) || byId(x, y),
      az: (x, y) => x.a.title.localeCompare(y.a.title) || byId(x, y),
    };
    const order = state.sort === "relevance" && !terms.length
      ? (x, y) => x.a.category.localeCompare(y.a.category) || byId(x, y)
      : sorts[state.sort] || sorts.relevance;
    rows.sort(order);
    return { list: rows.map(r => r.a), partial, poolSize: pool.length };
  }

  // ---------- rendering ----------
  const els = {
    results: $("#results"), summary: $("#summary"), chips: $("#chips"), filters: $("#filters"),
    q: $("#q"), sort: $("#sort"), empty: $("#empty"), more: $("#more"), stats: $("#stats"),
  };
  let current = [];

  function renderStats() {
    const sfx = LIB.skills["sound-effects"] || [], music = LIB.skills["background-music"] || [];
    const minutes = Math.round(music.reduce((t, a) => t + a.duration_seconds, 0) / 60);
    els.stats.innerHTML = [
      `<li><b>${sfx.length}</b> sound effects</li>`,
      `<li><b>${music.length}</b> instrumental tracks · <b>${minutes}</b> min</li>`,
      `<li>Plain-language descriptions and tags</li>`,
      `<li>Works offline · no API keys</li>`,
    ].join("");
    for (const s of SKILLS) $(`[data-count="${s}"]`).textContent = (LIB.skills[s] || []).length;
  }

  function renderTabs() {
    document.querySelectorAll(".tabs button").forEach(b => b.setAttribute("aria-selected", String(b.dataset.skill === state.skill)));
  }

  function renderChips() {
    const all = LIB.skills[state.skill] || [];
    const counts = {};
    for (const a of all) counts[a.category] = (counts[a.category] || 0) + 1;
    const cats = Object.keys(counts).sort((x, y) => catName(x).localeCompare(catName(y)));
    els.chips.innerHTML = [`<button class="chip" data-cat="" aria-pressed="${!state.cat}">All <span class="count">${all.length}</span></button>`]
      .concat(cats.map(c => `<button class="chip" data-cat="${esc(c)}" aria-pressed="${state.cat === c}">${esc(catName(c))} <span class="count">${counts[c]}</span></button>`))
      .join("");
  }

  function seg(name, label, options, value) {
    return `<span class="filter">${label}<span class="seg" data-filter="${name}">${options.map(([v, t]) =>
      `<button type="button" data-v="${v}" aria-pressed="${value === v}">${t}</button>`).join("")}</span></span>`;
  }

  function renderFilters() {
    if (state.skill === "sound-effects") {
      els.filters.innerHTML = seg("level", "Intensity", [["any", "Any"], ["subtle", "Subtle"], ["medium", "Medium"], ["strong", "Strong"]], state.level);
      return;
    }
    const moods = [...new Set((LIB.skills["background-music"] || []).flatMap(a => a.moods || []))].sort();
    els.filters.innerHTML =
      seg("level", "Energy", [["any", "Any"], ["low", "Low"], ["mid", "Medium"], ["high", "High"]], state.level) +
      seg("length", "Length", [["any", "Any"], ["short", "< 40s"], ["medium", "40–100s"], ["long", "> 100s"]], state.length) +
      `<label class="filter">Mood <select id="mood"><option value="">Any</option>${moods.map(m =>
        `<option ${state.mood === m ? "selected" : ""}>${esc(m)}</option>`).join("")}</select></label>`;
  }

  const ICONS = {
    play: '<svg viewBox="0 0 24 24" aria-hidden="true"><path class="i-play" d="M8 5.5v13l11-6.5z"/><path class="i-pause" d="M7 5h3.5v14H7zM13.5 5H17v14h-3.5z"/></svg>',
    copy: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M7 2.5h8A2.5 2.5 0 0 1 17.5 5v8H16V5a1 1 0 0 0-1-1H7zM4.5 6h8A1.5 1.5 0 0 1 14 7.5v9a1.5 1.5 0 0 1-1.5 1.5h-8A1.5 1.5 0 0 1 3 16.5v-9A1.5 1.5 0 0 1 4.5 6Zm0 1.5v9h8v-9z"/></svg>',
    down: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M9.25 3h1.5v8.19l2.97-2.97 1.06 1.06L10 14.06 5.22 9.28l1.06-1.06 2.97 2.97zM4 15.5h12V17H4z"/></svg>',
    info: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2a8 8 0 1 1 0 16 8 8 0 0 1 0-16Zm0 1.5a6.5 6.5 0 1 0 0 13 6.5 6.5 0 0 0 0-13ZM9.25 9h1.5v5h-1.5zm0-3h1.5v1.5h-1.5z"/></svg>',
  };

  const level = n => `<span class="level" aria-label="${n} of 5">${[1, 2, 3, 4, 5].map(i => `<i class="${i <= n ? "on" : ""}"></i>`).join("")}</span>`;

  function rowHtml(a) {
    const music = a.skill === "background-music";
    const badges = music
      ? [a.instrumental && `<span class="badge good">Instrumental</span>`,
         a.voiceover_friendly && `<span class="badge good">Voiceover-friendly</span>`,
         a.loopable && `<span class="badge good">Loop-tested</span>`].filter(Boolean).join("")
      : "";
    const tags = (a.tags || []).slice(0, 6).map(t => `<button class="tag" type="button" data-tag="${esc(t)}">${esc(t)}</button>`).join("");
    return `<li class="row" data-id="${esc(a.id)}">
      <div class="row-main">
        <button class="play" type="button" data-act="play" aria-pressed="false" aria-label="Play ${esc(a.title)}">${ICONS.play}</button>
        <div class="info">
          <div class="title-line"><h3 class="title">${esc(a.title)}</h3><span class="cat">${esc(catName(a.category))}</span></div>
          <p class="desc">${esc(a.description)}</p>
          <div class="tags">${badges}${tags}</div>
        </div>
        <div class="wave" data-act="seek" title="Click to play from here">${a.waveform ? "<canvas></canvas>" : '<div class="nowave">preview</div>'}</div>
        <div class="side">
          <span class="dur">${fmtDur(a.duration_seconds)}</span>
          <span title="${music ? "Energy" : "Intensity"}">${level(music ? a.energy : a.intensity)}</span>
          <div class="acts">
            <button class="btn ghost" type="button" data-act="copy" title="Copy repository path" aria-label="Copy path">${ICONS.copy}</button>
            <a class="btn ghost" href="${esc(a.file)}" download title="Download" aria-label="Download">${ICONS.down}</a>
            <button class="btn ghost" type="button" data-act="details" aria-expanded="false" title="Details" aria-label="Details">${ICONS.info}</button>
          </div>
        </div>
      </div>
      <div class="details" hidden></div>
    </li>`;
  }

  function detailsHtml(a) {
    const music = a.skill === "background-music";
    const t = a.timing || {};
    const kv = [
      ["ID", `<code>${esc(a.id)}</code>`],
      ["Format", `${esc((a.format || "").toUpperCase())} · ${a.sample_rate ? (a.sample_rate / 1000) + " kHz" : "?"} · ${a.channels === 1 ? "mono" : a.channels === 2 ? "stereo" : "?"}`],
      ["Duration", `${a.duration_seconds.toFixed(2)} s`],
      t.peak_seconds != null && [music ? "Loudest moment" : "Sync point (peak)", `${t.peak_seconds.toFixed(2)} s`],
      t.onset_seconds != null && ["Audible from / to", `${t.onset_seconds.toFixed(2)} – ${(t.end_seconds ?? a.duration_seconds).toFixed(2)} s`],
      music ? ["Moods", esc((a.moods || []).join(", "))] : ["Attack / tail", esc(`${a.attack} / ${a.tail}`)],
      music ? ["Good for", esc((a.preferred_content_types || []).join(", "))] : ["Use cases", esc((a.use_cases || []).join(", "))],
      a.bpm && ["BPM", esc(a.bpm)],
      ["Made with", esc(a.source)],
    ].filter(Boolean);
    return `<div class="pathline"><code>${esc(a.repo_path)}</code><button class="btn ghost" type="button" data-act="copy" aria-label="Copy path">${ICONS.copy}</button></div>
      <dl class="kv">${kv.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join("")}</dl>
      ${a.generation_prompt ? `<p class="prompt"><b>Generation prompt</b>${esc(a.generation_prompt)}</p>` : ""}
      ${!music && t.peak_seconds != null ? `<p class="muted small">To land the hit on a visual event at time T, start this clip at T − ${t.peak_seconds.toFixed(2)} s.</p>` : ""}`;
  }

  function render() {
    renderTabs(); renderChips(); renderFilters();
    els.q.value = state.q;
    els.sort.value = state.sort;
    const { list, partial, poolSize } = results();
    current = list;
    const visible = list.slice(0, state.shown);
    els.results.innerHTML = visible.map(rowHtml).join("");
    els.empty.hidden = list.length > 0;
    els.more.hidden = list.length <= state.shown;
    els.more.textContent = `Show more (${list.length - state.shown} left)`;
    const noun = state.skill === "sound-effects" ? "sound effects" : "tracks";
    els.summary.textContent = list.length
      ? `${partial ? "No exact match. Showing partial matches: " : ""}${Math.min(list.length, state.shown)} of ${list.length} ${noun}${state.q || state.cat || poolSize !== (LIB.skills[state.skill] || []).length ? " matching" : ""}`
      : "";
    observeWaves();
    syncPlayingRow();
    writeHash();
  }

  // ---------- waveforms ----------
  const byId = id => current.find(a => a.id === id) || SKILLS.flatMap(s => LIB.skills[s] || []).find(a => a.id === id);
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  function drawWave(row, progress = null) {
    const canvas = $("canvas", row);
    const a = byId(row.dataset.id);
    if (!canvas || !a || !a.waveform) return;
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    const cw = Math.round(w * dpr), ch = Math.round(h * dpr);
    if (canvas.width !== cw || canvas.height !== ch) { canvas.width = cw; canvas.height = ch; }
    const ctx = canvas.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    const peaks = a.waveform, n = peaks.length;
    const gap = w / n > 3 ? 1 : 0.5, bw = Math.max(1, w / n - gap);
    const base = css("--wave"), played = css("--wave-played") || css("--accent");
    for (let i = 0; i < n; i++) {
      const x = i * (w / n);
      const bh = Math.max(2, Math.sqrt(peaks[i]) * (h - 4));
      ctx.fillStyle = progress != null && (i + 0.5) / n <= progress ? played : base;
      const y = (h - bh) / 2;
      if (ctx.roundRect) { ctx.beginPath(); ctx.roundRect(x, y, bw, bh, Math.min(bw / 2, 1.5)); ctx.fill(); }
      else ctx.fillRect(x, y, bw, bh);
    }
    const peak = a.timing && a.timing.peak_seconds;
    if (a.skill === "sound-effects" && peak != null && a.duration_seconds) {
      const px = Math.round((peak / a.duration_seconds) * w) + 0.5;
      ctx.fillStyle = css("--peak");
      ctx.fillRect(px - 0.5, 0, 1.5, h);
      ctx.beginPath(); ctx.moveTo(px - 3.5, 0); ctx.lineTo(px + 3.5, 0); ctx.lineTo(px, 4); ctx.fill();
    }
  }

  const io = "IntersectionObserver" in window ? new IntersectionObserver(entries => {
    for (const e of entries) if (e.isIntersecting) { drawWave(e.target, progressFor(e.target.dataset.id)); io.unobserve(e.target); }
  }, { rootMargin: "200px" }) : null;
  function observeWaves() { document.querySelectorAll(".row").forEach(r => io ? io.observe(r) : drawWave(r)); }
  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => document.querySelectorAll(".row").forEach(r => drawWave(r, progressFor(r.dataset.id))), 120);
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener?.("change", () =>
    document.querySelectorAll(".row").forEach(r => drawWave(r, progressFor(r.dataset.id))));

  // ---------- audio ----------
  const audio = new Audio();
  audio.preload = "none";
  let playingId = null, raf = 0;
  const player = { el: $("#player"), toggle: $("#pToggle"), title: $("#pTitle"), sub: $("#pSub"), bar: $("#pBar"), fill: $("#pFill"), time: $("#pTime") };
  const progressFor = id => id === playingId && audio.duration ? audio.currentTime / audio.duration : null;
  const rowFor = id => els.results.querySelector(`.row[data-id="${CSS.escape(id)}"]`);

  function play(a, at = null) {
    if (playingId !== a.id) {
      const prev = playingId && rowFor(playingId);
      playingId = a.id;
      audio.src = a.file;
      if (prev) drawWave(prev);
      player.title.textContent = a.title;
      player.sub.textContent = `${catName(a.category)} · ${a.repo_path}`;
      player.el.hidden = false;
    }
    if (at != null) {
      const seekTo = () => { audio.currentTime = at * (audio.duration || a.duration_seconds); };
      if (audio.readyState >= 1) seekTo(); else audio.addEventListener("loadedmetadata", seekTo, { once: true });
    }
    audio.play().catch(() => toast("Could not play this file"));
  }
  function toggle(a) {
    if (playingId === a.id && !audio.paused) audio.pause();
    else play(a, playingId === a.id && audio.ended ? 0 : null);
  }
  function syncPlayingRow() {
    document.querySelectorAll(".row").forEach(r => {
      const on = r.dataset.id === playingId;
      r.classList.toggle("playing", on);
      $(".play", r).setAttribute("aria-pressed", String(on && !audio.paused));
    });
    player.toggle.setAttribute("aria-pressed", String(!audio.paused));
    player.toggle.setAttribute("aria-label", audio.paused ? "Play" : "Pause");
  }
  function tick() {
    const p = audio.duration ? audio.currentTime / audio.duration : 0;
    player.fill.style.width = (p * 100).toFixed(2) + "%";
    player.bar.setAttribute("aria-valuenow", String(Math.round(p * 100)));
    player.time.textContent = `${fmtDur(audio.currentTime)} / ${fmtDur(audio.duration || (byId(playingId) || {}).duration_seconds)}`;
    const row = playingId && rowFor(playingId);
    if (row) drawWave(row, p);
    if (!audio.paused) raf = requestAnimationFrame(tick);
  }
  audio.addEventListener("play", () => { syncPlayingRow(); cancelAnimationFrame(raf); raf = requestAnimationFrame(tick); });
  audio.addEventListener("pause", () => { syncPlayingRow(); tick(); });
  audio.addEventListener("ended", () => { syncPlayingRow(); tick(); });
  audio.addEventListener("error", () => { if (playingId) toast("Audio file not found"); });

  player.toggle.addEventListener("click", () => { const a = byId(playingId); if (a) toggle(a); });
  $("#pClose").addEventListener("click", () => {
    audio.pause(); const row = playingId && rowFor(playingId); playingId = null;
    if (row) drawWave(row); player.el.hidden = true; syncPlayingRow();
  });
  const seekBar = e => { const r = player.bar.getBoundingClientRect(); const a = byId(playingId); if (a) play(a, Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))); };
  player.bar.addEventListener("click", seekBar);
  player.bar.addEventListener("keydown", e => {
    if (!audio.duration) return;
    if (e.key === "ArrowRight") { audio.currentTime = Math.min(audio.duration, audio.currentTime + Math.max(0.5, audio.duration / 20)); e.preventDefault(); }
    if (e.key === "ArrowLeft") { audio.currentTime = Math.max(0, audio.currentTime - Math.max(0.5, audio.duration / 20)); e.preventDefault(); }
    tick();
  });

  // ---------- interactions ----------
  function toast(msg) {
    const t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toast.t); toast.t = setTimeout(() => t.classList.remove("show"), 1600);
  }
  async function copy(text) {
    try { await navigator.clipboard.writeText(text); }
    catch {
      const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } finally { ta.remove(); }
    }
    toast("Copied " + text.split("/").pop());
  }

  els.results.addEventListener("click", e => {
    const row = e.target.closest(".row"); if (!row) return;
    const a = byId(row.dataset.id);
    const tag = e.target.closest("[data-tag]");
    if (tag) { state.q = tag.dataset.tag; state.shown = PAGE; render(); window.scrollTo({ top: 0, behavior: "smooth" }); return; }
    const act = e.target.closest("[data-act]"); if (!act) return;
    const kind = act.dataset.act;
    if (kind === "play") toggle(a);
    else if (kind === "seek") { const r = act.getBoundingClientRect(); play(a, Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))); }
    else if (kind === "copy") copy(a.repo_path);
    else if (kind === "details") {
      const d = $(".details", row), open = d.hidden;
      if (open && !d.innerHTML) d.innerHTML = detailsHtml(a);
      d.hidden = !open; act.setAttribute("aria-expanded", String(open));
    }
  });

  document.querySelector(".tabs").addEventListener("click", e => {
    const b = e.target.closest("button[data-skill]"); if (!b || b.dataset.skill === state.skill) return;
    Object.assign(state, { skill: b.dataset.skill, cat: "", level: "any", mood: "", length: "any", shown: PAGE });
    render();
  });
  els.chips.addEventListener("click", e => {
    const c = e.target.closest(".chip"); if (!c) return;
    state.cat = c.dataset.cat; state.shown = PAGE; render();
  });
  els.filters.addEventListener("click", e => {
    const b = e.target.closest(".seg button"); if (!b) return;
    state[b.parentElement.dataset.filter] = b.dataset.v; state.shown = PAGE; render();
  });
  els.filters.addEventListener("change", e => { if (e.target.id === "mood") { state.mood = e.target.value; state.shown = PAGE; render(); } });
  let qTimer;
  els.q.addEventListener("input", () => {
    clearTimeout(qTimer);
    qTimer = setTimeout(() => {
      state.q = els.q.value.trim(); state.shown = PAGE;
      const pos = els.q.selectionStart; render(); els.q.focus(); els.q.setSelectionRange(pos, pos);
    }, 120);
  });
  els.sort.addEventListener("change", () => { state.sort = els.sort.value; render(); });
  els.more.addEventListener("click", () => { state.shown += PAGE; render(); });
  $("#reset").addEventListener("click", () => { Object.assign(state, { q: "", cat: "", level: "any", mood: "", length: "any", sort: "relevance", shown: PAGE }); render(); });

  document.addEventListener("keydown", e => {
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing) { e.preventDefault(); els.q.focus(); els.q.select(); return; }
    if (e.key === "Escape" && document.activeElement === els.q) { els.q.blur(); return; }
    if (typing || e.metaKey || e.ctrlKey || e.altKey || $("#useDialog").open) return;
    if (e.key === " " && !e.target.closest("button, a, [role=slider]")) {
      e.preventDefault();
      const a = byId(playingId) || current[0]; if (a) toggle(a);
    } else if (e.key === "j" || e.key === "k") {
      if (!current.length) return;
      const i = current.findIndex(a => a.id === playingId);
      const next = current[Math.min(current.length - 1, Math.max(0, i < 0 ? 0 : i + (e.key === "j" ? 1 : -1)))];
      const idx = current.indexOf(next);
      if (idx >= state.shown) { state.shown = idx + 1; render(); }
      play(next, 0);
      rowFor(next.id)?.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  });

  // ---------- repository link + dialog ----------
  function repoUrl() {
    if (LIB.repo_url) return LIB.repo_url;
    const host = location.hostname;
    if (host.endsWith(".github.io")) {
      const user = host.slice(0, -".github.io".length);
      const repo = location.pathname.split("/").filter(Boolean)[0];
      return `https://github.com/${user}/${repo || host}`;
    }
    return null;
  }
  const repo = repoUrl();
  if (repo) {
    const link = $("#repoLink"); link.href = repo; link.hidden = false;
    $("#cloneCmd").textContent = `git clone ${repo}.git SoundDirector`;
  }
  const dlg = $("#useDialog");
  $("#openUse").addEventListener("click", () => dlg.showModal ? dlg.showModal() : dlg.setAttribute("open", ""));
  dlg.addEventListener("click", e => { if (e.target === dlg) dlg.close(); });

  window.addEventListener("hashchange", () => { readHash(); render(); });
  readHash();
  renderStats();
  render();
})();
