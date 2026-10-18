/* War Room shared helpers: escaping, the hub API, model families, the sidebar shell, modal, toasts and the
   Ctrl+K command palette. Each page defines TOKEN before calling anything here. */
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;"})[c]);
const setHTML = (el, html) => { if (el && el._h !== html) { el.innerHTML = html; el._h = html; } };
const REDUCED = matchMedia("(prefers-reduced-motion: reduce)").matches;
const tier = m => /^ally:/.test(m) ? "info" : /haiku/.test(m) ? "haiku" : /sonnet/.test(m) ? "sonnet" : /fable/.test(m) ? "fable" : "opus";
const FAMILIES = {claude: "Claude", codex: "Codex", gemini: "Gemini", kimi: "Kimi", deepseek: "DeepSeek", omniroute: "OmniRoute"};
/* the model family: claude for every Claude tier, else the ally engine (an unknown engine shows as a gateway) */
const family = m => /^ally:/.test(m || "") ? (FAMILIES[m.slice(5)] ? m.slice(5) : "omniroute") : "claude";
const isAlly = m => /^ally:/.test(m || "");
const cap = s => s.charAt(0).toUpperCase() + s.slice(1);
/* "Sonnet 4.6" for a Claude model, "Codex" for an ally */
const modelName = m => { if (isAlly(m)) return FAMILIES[family(m)] === "OmniRoute" && m.slice(5) !== "omniroute" ? m.slice(5) : FAMILIES[family(m)];
  const v = (/(\d+)-(\d+)/.exec(m || "") || [])[0]; return `${cap(tier(m))}${v ? " " + v.replace("-", ".") : ""}`; };
const initials = n => (String(n).match(/[a-z0-9]/gi) || ["?"]).slice(0, 2).join("").toUpperCase();
const avatar = (name, model, cls = "") => `<span class="av f-${family(model)} ${cls}" aria-hidden="true">${esc(initials(name))}</span>`;
const famBadge = m => isAlly(m) ? `<span class="fam f-${family(m)}">${esc(modelName(m))}</span>` : "";
const dur = s => s == null || s < 0 ? "--" : s < 60 ? `${Math.floor(s)}s` : s < 3600 ? `${Math.floor(s / 60)}m ${Math.floor(s % 60)}s` : `${Math.floor(s / 3600)}h ${Math.floor(s % 3600 / 60)}m`;
const hhmm = t => new Date(t * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23"});
const hm = t => new Date(t * 1000).toLocaleTimeString([], {hour: "2-digit", minute: "2-digit", hourCycle: "h23"});
const ago = t => { const s = Date.now() / 1000 - t; return s < 60 ? "just now" : s < 3600 ? `${Math.floor(s / 60)} min ago` : s < 86400 ? `${Math.floor(s / 3600)} h ago` : `${Math.floor(s / 86400)} d ago`; };
const money = v => v == null ? "--" : v < 1 ? `$${v.toFixed(3)}` : `$${v.toFixed(2)}`;
const plural = (n, w) => `${n} ${w}${n === 1 ? "" : "s"}`;

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"X-War-Room-Token": TOKEN, "Content-Type": "application/json"}, body: JSON.stringify(body)});
  const out = await r.json().catch(() => ({}));
  if (!r.ok) { const e = new Error(out.error || r.status); e.out = out; throw e; }
  return out;
}

/* ---------- shell: the icon sidebar every page shares ---------- */
const ICONS = {
  home: '<path d="M4 11 12 4l8 7"/><path d="M6 10v9h12v-9"/>',
  new: '<rect x="4" y="4" width="16" height="16" rx="3"/><path d="M12 8v8M8 12h8"/>',
  run: '<rect x="3.5" y="5" width="17" height="14" rx="2"/><path d="M7 15l3-3 2.5 2L17 9"/>',
  history: '<path d="M4 12a8 8 0 1 0 2.4-5.7"/><path d="M4 5v4h4"/><path d="M12 8v4l3 2"/>',
  settings: '<path d="M5 7h9M18 7h1M5 17h3M12 17h7"/><rect x="14" y="5" width="4" height="4" rx="1"/><rect x="8" y="15" width="4" height="4" rx="1"/>',
  theme: '<circle cx="12" cy="12" r="7.5"/><path d="M12 4.5v15a7.5 7.5 0 0 0 0-15z" fill="currentColor"/>',
  search: '<circle cx="11" cy="11" r="6"/><path d="m20 20-4.5-4.5"/>'};
const svgIcon = k => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[k]}</svg>`;
const NAV = [["home", "/", "Home"], ["new", "/#new", "New run"], ["run", "", "Run"], ["history", "/history", "History"], ["settings", "/#settings", "Settings"]];
function shell(active) {
  const nav = $("side");
  nav.setAttribute("aria-label", "War Room");
  nav.innerHTML = `<a class="logo" href="/" title="War Room" aria-label="War Room home"><i></i></a>${NAV.map(([k, href, label]) =>
    `<a id="nav-${k}" href="${href || "#"}" class="${k === "run" && !href ? "off" : ""}" title="${label}">${svgIcon(k)}<span>${label}</span><i class="dot"></i></a>`).join("")}
    <div class="grow"></div>
    <button type="button" id="nav-k" title="Command palette (Ctrl+K)">${svgIcon("search")}<span>Ctrl K</span></button>
    <button type="button" id="nav-theme" title="Theme: dark, light or system">${svgIcon("theme")}<span id="nav-theme-l">Theme</span></button>`;
  setNav(active);
  $("nav-k").onclick = () => palette.open();
  $("nav-theme").onclick = cycleTheme;
  themeLabel();
}
function setNav(active) { for (const [k] of NAV) { const a = $(`nav-${k}`); a.classList.toggle("on", k === active); if (k === active) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); } }
/* the Run entry points at the live run (or the newest one) */
function setRunNav(run, live) {
  const a = $("nav-run"); if (!a) return;
  a.classList.toggle("off", !run); a.classList.toggle("live", !!live);
  a.href = run ? `/run/${encodeURIComponent(run)}` : "#";
  a.title = run ? `${live ? "Live run" : "Latest run"}: ${run}` : "No runs yet";
  document.querySelector(".logo")?.classList.toggle("live", !!live);
}
const THEMES = ["dark", "light", "system"];
function themeLabel() { const l = $("nav-theme-l"); if (l) l.textContent = cap(document.documentElement.dataset.theme || "dark"); }
async function setTheme(theme) {
  document.documentElement.dataset.theme = theme; themeLabel();
  document.dispatchEvent(new Event("themechange"));
  try { await api("/api/ui", {theme}); } catch (e) { toast("Theme not saved", e.message, "danger"); }
}
const cycleTheme = () => setTheme(THEMES[(THEMES.indexOf(document.documentElement.dataset.theme) + 1) % 3]);
matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => document.dispatchEvent(new Event("themechange")));

/* ---------- modal ---------- */
/* the page behind stays inert while any overlay (modal, palette, drawer) is open, so Tab stays inside it */
function syncInert() {
  const open = $("scrim")?.classList.contains("show") || $("pal")?.classList.contains("show") || ($("drawer") && !$("drawer").hidden);
  for (const el of document.querySelectorAll(".app")) el.inert = !!open;
}
let lastFocus = null;
function modal(html, danger = false) {
  lastFocus = document.activeElement;
  $("modal").className = "modal" + (danger ? " danger" : ""); $("modal").innerHTML = html.replace("<h3>", '<h3 id="mt">');
  $("scrim").classList.add("show");
  syncInert();
  ($("modal").querySelector("input, select, textarea, button.primary, button") || $("modal")).focus();
}
function closeModal() {
  if (!$("scrim").classList.contains("show")) return;
  $("scrim").classList.remove("show"); syncInert();
  if (lastFocus && lastFocus.focus) lastFocus.focus();
}
const fail = e => toast("War Room", e.message, "danger");

/* ---------- toasts, sound, desktop notifications ---------- */
let actx = null;
function beep() {
  try { actx = actx || new AudioContext();
    [0, .16].forEach(d => { const o = actx.createOscillator(), g = actx.createGain(); o.type = "square"; o.frequency.value = 880; g.gain.value = .04;
      o.connect(g).connect(actx.destination); o.start(actx.currentTime + d); o.stop(actx.currentTime + d + .08); });
  } catch (e) { /* audio is optional */ }
}
function toast(title, body, kind = "") {
  const t = document.createElement("div"); t.className = `toast ${kind}`; t.setAttribute("role", "status");
  t.innerHTML = `<b>${esc(title)}</b>${esc(body)}`;
  $("toasts").appendChild(t); setTimeout(() => t.remove(), 9000);
}
function alertUser(title, body, kind, ui, tag) {
  toast(title, body, kind);
  if (ui?.notify && ui?.sound) beep();
  if (ui?.notify && "Notification" in window && Notification.permission === "granted") new Notification(`War Room · ${title}`, {body, tag: tag || `${title}:${body}`});
}

/* ---------- Ctrl+K command palette: pages add their own commands ---------- */
const palette = {
  sources: [() => [
    {label: "Go to Home", group: "Navigate", run: () => location.href = "/"},
    {label: "New run", hint: "prompt, template, plan", group: "Navigate", run: () => location.href = "/#new"},
    {label: "History", hint: "finished runs and reports", group: "Navigate", run: () => location.href = "/history"},
    {label: "Settings", hint: "guard, gates, presets, profiles", group: "Navigate", run: () => location.href = "/#settings"},
    ...THEMES.map(t => ({label: `Theme: ${t}`, group: "View", run: () => setTheme(t)}))]],
  items: [], sel: 0,
  add(fn) { this.sources.push(fn); },
  open() {
    if (!$("pal")) document.body.insertAdjacentHTML("beforeend", `<div class="pal" id="pal"><div class="box" role="dialog" aria-modal="true" aria-label="Command palette">
      <input id="pal-q" type="text" placeholder="Type a command or search…" autocomplete="off" spellcheck="false" aria-controls="pal-l" role="combobox" aria-expanded="true">
      <ul id="pal-l" role="listbox"></ul><div class="hint"><span><span class="kbd">↑↓</span> move</span><span><span class="kbd">Enter</span> run</span><span><span class="kbd">Esc</span> close</span></div></div></div>`);
    this.back = document.activeElement;
    this.all = this.sources.flatMap(f => { try { return f() || []; } catch (e) { return []; } });
    $("pal").classList.add("show"); syncInert(); $("pal-q").value = ""; this.filter(); $("pal-q").focus();
    $("pal-q").oninput = () => this.filter();
    $("pal").onclick = e => { if (e.target === $("pal")) this.close(); const li = e.target.closest("li[data-i]"); if (li) this.run(+li.dataset.i); };
  },
  close() { if (!$("pal")?.classList.contains("show")) return; $("pal").classList.remove("show"); syncInert(); this.back?.focus?.(); },
  filter() {
    const q = $("pal-q").value.toLowerCase().trim().split(/\s+/).filter(Boolean);
    this.items = this.all.filter(c => { const s = `${c.label} ${c.hint || ""} ${c.group || ""}`.toLowerCase(); return q.every(w => s.includes(w)); });
    this.sel = 0; this.draw();
  },
  draw() {
    $("pal-l").innerHTML = this.items.map((c, i) => `<li data-i="${i}" role="option" id="pal-${i}" aria-selected="${i === this.sel}" class="${i === this.sel ? "on" : ""}">
      <b>${esc(c.label)}</b>${c.hint ? `<span>${esc(c.hint)}</span>` : ""}<span class="g">${esc(c.group || "")}</span></li>`).join("") || `<li class="none">No matching command</li>`;
    $("pal-q").setAttribute("aria-activedescendant", this.items.length ? `pal-${this.sel}` : "");
    $(`pal-${this.sel}`)?.scrollIntoView({block: "nearest"});
  },
  run(i) { const c = this.items[i]; if (!c) return; this.close(); c.run(); }
};
addEventListener("keydown", e => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") { e.preventDefault(); $("pal")?.classList.contains("show") ? palette.close() : palette.open(); return; }
  if ($("pal")?.classList.contains("show")) {
    if (e.key === "Escape") { e.preventDefault(); palette.close(); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") { e.preventDefault(); const n = palette.items.length; if (n) { palette.sel = (palette.sel + (e.key === "ArrowDown" ? 1 : n - 1)) % n; palette.draw(); } }
    else if (e.key === "Enter") { e.preventDefault(); palette.run(palette.sel); }
    return;
  }
  if (e.key === "Escape") closeModal();
});
document.addEventListener("click", e => { if (e.target === $("scrim")) closeModal(); });
