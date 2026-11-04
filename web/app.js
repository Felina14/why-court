// Why Court — comic courtroom. No framework; works in any phone browser.
const $ = (s) => document.querySelector(s);
const API = window.WHYCOURT_API || "";   // set in static/config.js: the API's address when the UI is hosted apart
const NAMES = { judge: "JUDGE", prosecutor: "PROSECUTOR", defence: "DEFENCE", clerk: "COURT CLERK", student: "YOU" };
const VOICE = { judge: { pitch: 0.75, rate: 0.95 }, prosecutor: { pitch: 1.05, rate: 1.08 }, defence: { pitch: 1.2, rate: 1 }, clerk: { pitch: 1.1, rate: 1 }, student: { pitch: 1.3, rate: 1.05 } };

// Simple original comic faces, drawn inline so the app needs no image files.
const FACES = {
  judge: `<circle cx="30" cy="32" r="16" fill="#f3d2ae"/><path d="M12 30a18 18 0 0 1 36 0" fill="none"/>
    <path d="M10 26c0-9 9-16 20-16s20 7 20 16c-4-2-7-1-9 1-3-4-19-5-22 0-2-2-5-3-9-1z" fill="#ece7f5" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>
    <circle cx="24" cy="33" r="4.5" fill="#fff"/><circle cx="36" cy="33" r="4.5" fill="#fff"/>
    <circle cx="24" cy="33" r="1.8"/><circle cx="36" cy="33" r="1.8"/><path d="M28.5 33h3" stroke-width="2"/>
    <path d="M25 43q5 3 10 0" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <path d="M18 52l6-6M42 52l-6-6" stroke-width="3" stroke-linecap="round"/>`,
  prosecutor: `<circle cx="30" cy="32" r="16" fill="#f1c9a5"/>
    <path d="M13 26l8-10 6 6 7-7 6 7 7-2-4 8z" fill="#3a2a22" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M20 29l8 3M40 29l-8 3" stroke-width="2.5" stroke-linecap="round"/>
    <circle cx="24" cy="35" r="1.9"/><circle cx="36" cy="35" r="1.9"/>
    <path d="M24 44q6 1 12-2" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <path d="M22 50l8 8 8-8z" fill="#e03b2f" stroke="#15110d" stroke-width="2.5"/>`,
  defence: `<circle cx="30" cy="32" r="16" fill="#e8c49c"/>
    <path d="M14 25q16-14 32 0-6 2-16 2T14 25z" fill="#6b4a2f" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>
    <circle cx="23" cy="34" r="5.5" fill="#fff"/><circle cx="37" cy="34" r="5.5" fill="#fff"/>
    <circle cx="23" cy="34" r="2"/><circle cx="37" cy="34" r="2"/><path d="M28.5 34h3" stroke-width="2"/>
    <path d="M23 43q7 5 14 0" stroke-width="2.5" fill="none" stroke-linecap="round"/>
    <path d="M24 52l6-4 6 4-6 3z" fill="#1f6fd0" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>`,
  clerk: `<circle cx="30" cy="32" r="16" fill="#f5d6b3"/>
    <path d="M14 28q4-16 16-16t16 16q-4-6-16-6T14 28z" fill="#2f2a26" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M46 24q8 4 6 14" fill="none" stroke-width="3" stroke-linecap="round"/>
    <circle cx="24" cy="34" r="2"/><circle cx="36" cy="34" r="2"/>
    <path d="M24 42q6 5 12 0" fill="none" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M18 54h24l-3-6H21z" fill="#1f8a4c" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>`,
  student: `<circle cx="30" cy="33" r="16" fill="#eec29b"/>
    <path d="M12 24h36l-4-6H16z" fill="#f6b93b" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>
    <path d="M30 18V9" stroke-width="2.5" stroke-linecap="round"/><circle cx="30" cy="8" r="2.5" fill="#e03b2f"/>
    <circle cx="24" cy="35" r="2"/><circle cx="36" cy="35" r="2"/>
    <path d="M24 43q6 4 12 0" stroke-width="2.5" fill="none" stroke-linecap="round"/>`,
};
function face(who) {
  return `<svg class="face" viewBox="0 0 60 60" aria-hidden="true" stroke="#15110d" fill="none">${FACES[who] || FACES.clerk}</svg>`;
}

const EPISODES = [
  { title: "The Case of the Lucky Fraction", blurb: "3/5 won. You're the defendant: tell the court WHY it's bigger, and a surprise witness tests your reason.", case: { subject: "maths", grade: "5", question: "Which is bigger: 3/5 or 2/4?", options: ["3/5", "2/4"], student_answer: "3/5", correct_answer: "3/5", source: "episode" } },
  { title: "The Decimal in Disguise", blurb: "0.45 beat 0.4. Tell the court why. Did you count digits, or think about value? The witness will find out.", case: { subject: "maths", grade: "5", question: "Which is bigger: 0.45 or 0.4?", options: ["0.45", "0.4"], student_answer: "0.45", correct_answer: "0.45", source: "episode" } },
  { title: "The Log That Would Not Sink", blurb: "A heavy log floats, a small stone sinks. Tell the court why, and see if your reason survives the witness.", case: { subject: "science", grade: "6", question: "Which will float in water: a big wooden log or a small stone?", options: ["the big wooden log", "the small stone"], student_answer: "the big wooden log", correct_answer: "the big wooden log", source: "episode" } },
];

// Each screen is a step in the browser's history, so the phone's Back button goes back a screen, not out of the app.
let fromHistory = false;
window.addEventListener("popstate", (e) => { fromHistory = true; show(e.state?.screen || "home"); fromHistory = false; });
try { history.replaceState({ screen: "home" }, ""); } catch (e) { /* history off */ }
function show(id) {
  const now = document.querySelector(".screen.active")?.id;
  if (!fromHistory && now && now !== id) { try { history.pushState({ screen: id }, ""); } catch (e) { /* history off */ } }
  // Close the phone keyboard first: if a text box keeps focus, the visible area stays shifted and later taps land
  // in the wrong place (measured: 177px off after typing homework, so a witness answer button could not be tapped).
  if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  document.querySelectorAll(".screen").forEach((s) => s.classList.toggle("active", s.id === id));
  window.scrollTo(0, 0);
}
function player() { return ($("#player").value || "guest").trim().slice(0, 8); }
function esc(s) { return String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c])); }
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// A failed call shows the server's own sentence ("That file isn't a PDF…"), never raw JSON.
async function problem(r) {
  const text = await r.text();
  let detail = text;
  try { const d = JSON.parse(text).detail; detail = typeof d === "string" ? d : "Something in that didn't look right. Check it and try again."; } catch (e) { /* plain text */ }
  return new Error(detail || r.statusText || "The court hit a problem. Try again!");
}
async function post(path, body, isForm = false, headers = {}) {
  const r = await fetch(API + path, { method: "POST", body: isForm ? body : JSON.stringify(body), headers: isForm ? headers : { "Content-Type": "application/json", ...headers } });
  if (!r.ok) throw await problem(r);
  return r.json();
}
async function getJSON(path) { const r = await fetch(API + path); if (!r.ok) throw await problem(r); return r.json(); }

// ---------- voice: Amazon Polly reads the court aloud, one line after another ----------
// Polly has voices for English, Hindi, Spanish and French; for other languages (204 from the server) the browser's
// own voice speaks instead, so a child always hears the court.
const SPEECH_LANG = { English: "en-IN", Hindi: "hi-IN", Tamil: "ta-IN", Spanish: "es-ES", French: "fr-FR", Swahili: "sw-KE" };
const sayQueue = [];
let saying = false, nowPlaying = null;
// One shared player, unlocked by the child's first tap: phones (iPhones especially) refuse audio that does not start
// from a tap, and a Polly line arrives a moment after the tap that asked for it.
const voicePlayer = new Audio();
const SILENCE = "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQAAAAA=";
function unlockAudio() {
  voicePlayer.src = SILENCE; voicePlayer.play().catch(() => {});
  if ("speechSynthesis" in window) { try { speechSynthesis.speak(new SpeechSynthesisUtterance("")); } catch (e) { /* ignore */ } }
  document.removeEventListener("pointerdown", unlockAudio, true);
}
document.addEventListener("pointerdown", unlockAudio, true);
// speak(speaker, text, {onstart, onend}): onstart fires when the voice really starts, onend when it finishes (or is
// skipped), so the characters on screen move with the voice. Every line also fires a "court-say" event on document.
let sayingNow = null, sayGen = 0;
function sayEvent(phase, item) {
  document.dispatchEvent(new CustomEvent("court-say", { detail: { phase, speaker: item[0], text: item[1] } }));
  const cb = phase === "start" ? item[2]?.onstart : item[2]?.onend;
  if (cb) { if (phase === "end") item[2].onend = null; try { cb(); } catch (e) { /* never break the voice */ } }
}
function speak(speaker, text, opts = {}) {
  if (!$("#voiceToggle").checked || !text) { opts.onend?.(); return false; }
  sayQueue.push([speaker, text, opts]);
  if (!saying) nextSay();
  return true;
}
function stopSpeaking() {
  sayGen++;
  if (sayingNow) sayEvent("end", sayingNow);
  sayQueue.splice(0).forEach((it) => sayEvent("end", it));
  sayingNow = null;
  if (nowPlaying) { nowPlaying.pause(); nowPlaying = null; }
  voicePlayer.pause();
  if ("speechSynthesis" in window) speechSynthesis.cancel();
  saying = false;
}
async function nextSay() {
  if (sayingNow) { sayEvent("end", sayingNow); sayingNow = null; }
  const item = sayQueue.shift();
  if (!item) { saying = false; return; }
  saying = true; sayingNow = item;
  const [speaker, text] = item, gen = sayGen;
  try {
    const r = await fetch(API + "/api/speak", { method: "POST", headers: { "Content-Type": "application/json" },
                                               body: JSON.stringify({ text, speaker, lang: lang() }) });
    if (gen !== sayGen) return;                 // stopped while the voice was on its way
    if (r.status === 200) {
      const url = URL.createObjectURL(await r.blob());
      if (gen !== sayGen) { URL.revokeObjectURL(url); return; }
      const a = voicePlayer;      // the shared, tap-unlocked player
      a.src = url; nowPlaying = a;
      a.onended = a.onerror = () => { URL.revokeObjectURL(url); a.onended = a.onerror = null; if (nowPlaying === a) nowPlaying = null; nextSay(); };
      try { await a.play(); sayEvent("start", item); return; } catch (e) { URL.revokeObjectURL(url); a.onended = a.onerror = null; nowPlaying = null; }  // still blocked
    }
  } catch (e) { /* offline or no Polly: the browser speaks instead */ }
  if (gen !== sayGen) return;
  browserSay(speaker, text, nextSay);
}
function browserSay(speaker, text, done) {
  if (!("speechSynthesis" in window)) return done();
  const u = new SpeechSynthesisUtterance(text);
  Object.assign(u, VOICE[speaker] || {});
  u.lang = SPEECH_LANG[lang()] || "en-IN";
  u.onstart = () => sayingNow && sayEvent("start", sayingNow);
  u.onend = u.onerror = () => done();
  speechSynthesis.speak(u);
}
$("#voiceToggle").addEventListener("change", () => { if (!$("#voiceToggle").checked) stopSpeaking(); });
function attachMic(btn, textarea) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) { btn.hidden = true; return; }
  btn.onclick = () => {
    const rec = new SR(); rec.lang = SPEECH_LANG[lang()] || "en-IN"; rec.interimResults = false;  // listen in the child's language
    btn.classList.add("on");
    rec.onresult = (e) => { textarea.value = (textarea.value + " " + e.results[0][0].transcript).trim(); };
    rec.onend = () => btn.classList.remove("on");
    rec.start();
  };
}

// ---------- life: motion, typewriter, confetti ----------
const calm = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
let skipping = false, finishLine = null;    // the child tapped to skip the rest of this hearing
function typewrite(el, text) {
  if (calm() || skipping) { el.textContent = text; return; }
  el.textContent = ""; el.classList.add("typing");
  const total = Math.min(1600, Math.max(400, text.length * 22)), step = Math.max(1, Math.ceil(text.length / (total / 30)));
  let i = 0;
  const tick = setInterval(() => {
    i = Math.min(text.length, i + step); el.textContent = text.slice(0, i);
    if (i >= text.length || skipping) { el.textContent = text; el.classList.remove("typing"); clearInterval(tick); }
  }, 30);
}
// Show one court line: the speaker pops and talks, everyone else dims. Resolves when the voice ends (or a reading
// timer when the voice is off), so the scene moves at the pace of the words.
function performLine(li, m) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (done) return; done = true; finishLine = null; li.classList.remove("speaking"); castTalk(null); resolve(); };
    finishLine = finish;
    li.hidden = false; li.classList.add("speaking", "new");
    li.parentElement.querySelectorAll(".line").forEach((x) => x.classList.toggle("dim", x !== li && !x.hidden));
    castTalk(m.speaker); castSpoke(m.speaker);
    typewrite(li.querySelector(".txt"), m.text);
    if (skipping) return finish();
    // Wait for both the voice to end and a short minimum, so a line never flashes past (no voice on the device).
    const reading = Math.min(4500, Math.max(1300, m.text.length * 48));
    let voiceOver = false, minOver = false;
    const tryEnd = () => { if (skipping || (voiceOver && minOver)) finish(); };
    const voiced = speak(m.speaker, m.text, { onend: () => { voiceOver = true; tryEnd(); } });
    if (!voiced) voiceOver = true;
    setTimeout(() => { minOver = true; tryEnd(); }, voiced ? Math.min(reading, 1400) : reading);
    if (voiced) setTimeout(finish, reading + 12000);   // safety net if the voice never reports back
  });
}
function castTalk(role) { document.querySelectorAll(".castrow").forEach((r) => r.classList.toggle("talking", r.dataset.role === role)); }
function confetti() {
  if (calm()) return;
  const c = document.createElement("canvas"), dpr = Math.min(2, devicePixelRatio || 1);
  c.className = "confetti"; c.width = innerWidth * dpr; c.height = innerHeight * dpr; c.setAttribute("aria-hidden", "true");
  document.body.appendChild(c);
  const g = c.getContext("2d"); g.scale(dpr, dpr);
  const COLS = ["#f6b93b", "#e03b2f", "#1f6fd0", "#1f8a4c", "#6b3fa0", "#ffffff"];
  const P = Array.from({ length: 140 }, () => ({ x: innerWidth / 2 + (Math.random() - .5) * 120, y: innerHeight * .35,
    vx: (Math.random() - .5) * 13, vy: -Math.random() * 13 - 4, r: Math.random() * 6.28, vr: (Math.random() - .5) * .4,
    w: 6 + Math.random() * 7, h: 4 + Math.random() * 5, c: COLS[Math.floor(Math.random() * COLS.length)] }));
  const t0 = performance.now();
  (function frame(t) {
    const k = (t - t0) / 1900;
    g.clearRect(0, 0, innerWidth, innerHeight);
    P.forEach((p) => { p.vy += .38; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.r += p.vr;
      g.save(); g.globalAlpha = Math.max(0, 1 - k * k); g.translate(p.x, p.y); g.rotate(p.r); g.fillStyle = p.c;
      g.fillRect(-p.w / 2, -p.h / 2, p.w, p.h); g.strokeStyle = "#15110d"; g.lineWidth = 1; g.strokeRect(-p.w / 2, -p.h / 2, p.w, p.h); g.restore(); });
    if (k < 1) requestAnimationFrame(frame); else c.remove();
  })(t0);
}

// ---------- questions you can see: fraction bars and decimal grids ----------
function valueOf(o) {
  const s = String(o).trim(), f = s.match(/^(\d+)\s*\/\s*(\d+)$/), d = s.match(/^0?\.(\d{1,2})$/);
  if (f && +f[2] > 0 && +f[2] <= 24 && +f[1] <= +f[2]) return { kind: "frac", a: +f[1], b: +f[2], v: f[1] / f[2] };
  if (d) return { kind: "dec", digits: d[1].length, hundredths: +d[1] * (d[1].length === 1 ? 10 : 1), v: +("0." + d[1]) };
  return null;
}
function barSVG(a, b, cls = "") {
  const w = 120 / b;
  return `<svg class="vis bar ${cls}" viewBox="-1.5 -1.5 123 21" preserveAspectRatio="none" aria-hidden="true">` +
    Array.from({ length: b }, (_, i) => `<rect x="${i * w}" y="0" width="${w}" height="18" fill="${i < a ? "#f6b93b" : "#fff"}" stroke="#15110d" stroke-width="1.5"/>`).join("") + "</svg>";
}
function gridSVG(n, cls = "") {
  let cells = "";
  for (let i = 0; i < 100; i++) cells += `<rect x="${(i % 10) * 10}" y="${Math.floor(i / 10) * 10}" width="10" height="10" fill="${i < n ? "#f6b93b" : "#fff"}" stroke="#15110d" stroke-width=".8"/>`;
  return `<svg class="vis grid ${cls}" viewBox="-1 -1 102 102" aria-hidden="true">${cells}</svg>`;
}
// One picture per option, drawn the same way for every option so they can be compared (null if any option is not a
// simple fraction or decimal). Decimals: tenths bars, or hundred grids as soon as any option has hundredths.
function visualsFor(options) {
  const vals = (options || []).map(valueOf);
  if (vals.length < 2 || vals.some((v) => !v) || new Set(vals.map((v) => v.kind)).size > 1) return null;
  if (vals[0].kind === "frac") return vals.map((v) => barSVG(v.a, v.b));
  const hundred = vals.some((v) => v.digits === 2);
  return vals.map((v) => (hundred ? gridSVG(v.hundredths) : barSVG(v.hundredths / 10, 10)));
}
function optionButtons(container, options, onPick) {
  const vis = visualsFor(options);
  return options.map((o, i) => {
    const b = document.createElement("button");
    b.className = "optbtn" + (vis ? " withvis" : "");
    b.innerHTML = `<span class="optlabel">${esc(o)}</span>${vis ? vis[i] : ""}`;
    b.onclick = () => onPick(o, b);
    container.appendChild(b);
    return b;
  });
}
// The visual proof after a practice answer: the options' pictures side by side, the bigger one highlighted.
function proofFor(options) {
  const vals = (options || []).map(valueOf), vis = visualsFor(options);
  if (!vis) return "";
  const max = Math.max(...vals.map((v) => v.v));
  return `<div class="proof">${options.map((o, i) => `<div class="proofrow${vals[i].v === max ? " big" : ""}">
    <span class="prooflabel" data-notr>${esc(o)}</span>${vis[i]}${vals[i].v === max ? `<span class="biggest">bigger</span>` : ""}</div>`).join("")}</div>`;
}

// ---------- a case card: answer + "why" ----------
function caseCard(c, label = "Put it on trial ⚖") {
  const el = document.createElement("div");
  el.className = "card";
  const asking = !c.student_answer && c.source === "homework";
  el.innerHTML = `${asking ? `<div class="askhead">Good question for the court!</div>` : ""}<div class="q">${esc(c.question)}</div>
    ${c.options?.length ? `<div class="opts-line">${c.options.map(esc).join("  ·  ")}</div>` : ""}
    ${asking ? `<p class="askline">What do you think? Then tell the court why.</p>` : ""}
    ${c.student_answer ? `<div class="a">Your answer: <b>${esc(c.student_answer)}</b></div>` : `<input class="ans" placeholder="Your answer" aria-label="Your answer">`}
    ${c.source === "book" ? `<div class="whylabel">Explain or show your reasoning</div>` : ""}
    <div class="whyrow"><textarea class="why" rows="2" placeholder="Tell the court why you knew…" aria-label="Your reason">${esc(c.student_why || "")}</textarea><button class="mic" aria-label="Speak your reason">🎤</button></div>
    <button class="primary go">${label}</button>`;
  attachMic(el.querySelector(".mic"), el.querySelector(".why"));
  el.querySelector(".go").onclick = () => {
    const ans = el.querySelector(".ans");
    const kase = { ...c, student_answer: ans ? ans.value.trim() : c.student_answer, student_why: el.querySelector(".why").value.trim() };
    if (!kase.student_answer) return alert(uiText("Give your answer first!"));
    if (!kase.student_why) return needWhy(el.querySelector(".why"));
    startTrial(kase);
  };
  return el;
}

// ---------- courtroom ----------
// The trial reads as a scene with a few big moments: a compact hearing (one line per speaker), the surprise
// witness as a large card, then a large verdict card. Earlier hearings (before an objection) fold away.
let seen = 0;          // transcript lines already shown (only newer ones animate and are read aloud)

const CAST = ["clerk", "prosecutor", "defence", "judge"];
function buildCast() {
  $("#cast").innerHTML = `<h4>Who's in court</h4>` + CAST.map((r) =>
    `<div class="castrow" data-role="${r}">${face(r)}<span class="role">${NAMES[r]}</span><span class="tick"></span></div>`).join("");
}
function castSpoke(role) {
  const row = $(`.castrow[data-role="${role}"]`);
  if (row) { row.classList.add("spoken"); row.querySelector(".tick").textContent = "✓"; }
}

function slate(kase) {
  $("#slate").innerHTML = `<div class="label">YOUR ANSWER</div>
    <div class="q">${esc(kase.question)}</div>
    <div class="mine"><span>Your answer:</span> <b>${esc(kase.student_answer)}</b>${kase.student_why ? `<span data-notr> · “${esc(kase.student_why)}”</span>` : ""}</div>`;
}

function lineFor(m) {
  const li = document.createElement("li");
  li.className = `line ${m.speaker}`;
  const tag = m.objection ? "YOU OBJECT" : (NAMES[m.speaker] || m.speaker);
  li.innerHTML = `${face(m.speaker)}<div class="said"><span class="tag">${esc(tag)}</span><span class="txt">${esc(m.text)}</span>
    ${m.evidence ? `<span class="evidence">“${esc(m.evidence)}”</span>` : ""}</div>`;
  return li;
}

// Split one hearing's transcript into the parts the screen shows.
function sceneOf(msgs, status) {
  const hearing = [], witnesses = [], verdict = [];
  let lesson = null, lastAnswer = -1;
  msgs.forEach((m, i) => { if (m.witness_answer) lastAnswer = i; });
  const final = !["awaiting_witness", "open"].includes(status);
  msgs.forEach((m, i) => {
    if (m.witness_question) witnesses.push({ q: m.witness_question, a: null });
    else if (m.witness_answer) { if (witnesses.length) witnesses[witnesses.length - 1].a = m.text; }
    else if (m.title) lesson = m;
    else if (final && lastAnswer >= 0 && i > lastAnswer) verdict.push(m);
    else hearing.push(m);
  });
  let hint = null;
  if (status === "help") {
    const i = hearing.map((m) => m.speaker).lastIndexOf("clerk");
    if (i >= 0) hint = hearing.splice(i, 1)[0];
  }
  return { hearing, witnesses, verdict, lesson, hint };
}

async function renderTrial(t) {
  const tr = t.transcript;
  if (t.case) slate(t.case);
  let cut = 0;
  tr.forEach((m, i) => { if (m.objection) cut = i; });
  // Lines before the latest objection belong to an earlier hearing: fold them away.
  const before = cut ? tr.slice(0, cut) : [];
  $("#earlier").hidden = !before.length;
  $("#earlierLines").innerHTML = "";
  before.filter((m) => !m.witness_question && !m.title).forEach((m) => $("#earlierLines").appendChild(lineFor(m)));

  const sc = sceneOf(cut ? tr.slice(cut) : tr, t.status);
  const lines = $("#lines"); lines.innerHTML = "";
  const fresh = [];
  sc.hearing.forEach((m) => {
    const li = lineFor(m);
    if (tr.indexOf(m) >= seen) { li.hidden = true; fresh.push([li, m]); } else castSpoke(m.speaker);
    lines.appendChild(li);
  });
  $("#hearing").hidden = !sc.hearing.length;

  const log = $("#witlog");
  const answered = sc.witnesses.filter((w) => w.a !== null);
  log.hidden = !answered.length;
  log.innerHTML = answered.map((w, i) => `<li><span class="wn">Witness ${i + 1}</span><span class="wq2">${esc(w.q)}</span><span class="wa">You said <b>${esc(w.a)}</b></span></li>`).join("");

  seen = tr.length;
  // The hearing plays out line by line, at the pace of the voice; a tap on the hearing skips to the end. If the child
  // already watched the court decide live, the lines appear at once and the witness comes straight in.
  skipping = watchedLive;
  watchedLive = false;
  if (fresh.length) {
    $("#courtActions").innerHTML = `<button class="skipbtn" id="skipBtn">Skip ⏩</button>`;
    $("#skipBtn").onclick = () => { skipping = true; stopSpeaking(); finishLine?.(); };
    for (const [li, m] of fresh) {
      await performLine(li, m);
      li.scrollIntoView({ behavior: calm() ? "auto" : "smooth", block: "nearest" });
    }
    lines.querySelectorAll(".dim").forEach((x) => x.classList.remove("dim"));
  }
  skipping = false;
  renderActions(t, sc);
  // One instant scroll (two smooth ones cancelled each other and left the page at the top). A witness card is shown
  // whole, answer buttons included; any other card from its top.
  const first = $("#courtActions").firstElementChild;
  if (first && first.classList.contains("witness")) {
    // The witness card "slams" in scaled down; scrolling during the slam measured it too small, so the answer
    // buttons ended below the fold. Scroll once it has landed (or at once, with reduced motion).
    let done = false;
    const land = () => { if (!done) { done = true; first.scrollIntoView({ behavior: "auto", block: "end" }); } };
    first.addEventListener("animationend", land, { once: true });
    setTimeout(land, calm() ? 0 : 800);
  } else if (first) first.scrollIntoView({ behavior: "auto", block: "start" });
}

const VERDICTS = {
  cleared: ["CLEARED!", "win", "The witnesses agreed with you."],
  misconception_found: ["SNEAKY IDEA CAUGHT!", "learn", "That's a win — now you know it."],
  help: ["NOT QUITE YET", "amber", "Let's fix the answer first."],
  explain_again: ["TELL THE COURT WHY!", "help", "Tell us how you knew."],
};
// A closed case only says the reason held up when the court really tested it and it did.
const CLOSED = {
  held_up: ["YOUR REASON HOLDS UP!", "win", "Your reasoning holds up."],
  no_verdict: ["NO VERDICT YET", "help", "The court couldn't decide this time. Try a check-up to test your thinking."],
  out_of_scope: ["REASON CHECKED!", "help", ""],
};
function verdictFor(t, sc) {
  if (t.status !== "case_closed") return VERDICTS[t.status];
  if (CLOSED[t.verdict_kind]) return CLOSED[t.verdict_kind];
  return sc?.witnesses?.length ? CLOSED.no_verdict : ["CASE CLOSED", "help", ""];   // older server: claim nothing
}

function renderActions(t, sc) {
  const a = $("#courtActions");
  a.innerHTML = "";
  if (t.status === "awaiting_witness") {
    const w = t.witness;
    const n = (t.witness_answers?.length || 0) + 1;
    const card = document.createElement("div");
    card.className = "witness slam";
    card.innerHTML = `<span class="burst" aria-hidden="true">BANG!</span>
      <div class="wtop"><span class="bang">SURPRISE WITNESS!</span><span class="wcount">Witness ${n}</span></div>
      <div class="wq">${esc(w.question)}</div><div class="hint">Tap your answer. Think it through your own way.</div><div class="opts"></div>`;
    optionButtons(card.querySelector(".opts"), w.options, async (o) => {
      thinking("The court considers your answer");
      try { await renderTrial(await post(`/api/trial/${t.trial_id}/witness`, { answer: o })); } catch (e) { fail(e); }
    });
    a.appendChild(card);
    card.querySelector(".opts button")?.focus({ preventScroll: true });   // keyboard users land on the answers
    if (n === 1) speak("judge", uiText("The court calls a surprise witness!") + " " + w.question);
    return;
  }
  const v = verdictFor(t, sc);
  if (v) {
    const card = document.createElement("div");
    card.className = `verdict ${v[1]}`;
    // A wrong answer: the Clerk's hint is the heart of the card.
    const ls = sc?.lesson, idea = t.idea_child || t.misconception;
    const caught = t.status === "misconception_found";
    // The idea is shown once, in the "You were thinking" box: drop a court line that only repeats it.
    const repeats = (m) => caught && idea && String(m.text).toLowerCase().includes(String(idea).toLowerCase());
    const said = (sc?.verdict || []).filter((m) => !repeats(m)).concat(sc?.hint ? [sc.hint] : [])
      .map((m) => `<p class="vline">${esc(m.text)}</p>`).join("");
    card.innerHTML = `<div class="stamp ${v[1]}">${v[0]}</div>
      ${caught && idea ? `<div class="thinkingwas"><span>You were thinking:</span> <b class="ideatext">“${esc(idea)}”</b></div>` : ""}
      ${caught && t.insight?.remember ? `<p class="iremember"><b>Remember:</b> <span class="irtext">${esc(t.insight.remember)}</span></p>` : ""}
      ${said}
      ${ls ? `<div class="lesson"><div class="lessontitle">${esc(ls.title || "Lesson")}</div><p class="lessontext clamp">${esc(ls.text)}</p>
        <button class="readall" hidden>Read the whole lesson</button>
        ${ls.try_this ? `<div class="tryline"><b>${esc(uiText("Try this:"))}</b> ${esc(ls.try_this)}
          ${ls.try_this_answer ? `<details><summary>${esc(uiText("Show answer"))}</summary>${esc(ls.try_this_answer)}</details>` : ""}</div>` : ""}</div>` : ""}
      ${v[2] ? `<p class="vhint">${v[2]}</p>` : ""}`;
    a.appendChild(card);
    const lt = card.querySelector(".lessontext"), more = card.querySelector(".readall");
    if (lt && lt.scrollHeight > lt.clientHeight + 4) {
      more.hidden = false;
      more.onclick = () => { lt.classList.remove("clamp"); more.hidden = true; };
    } else if (lt) lt.classList.remove("clamp");
    (sc?.verdict || []).forEach((m) => speak(m.speaker, m.text));
    if (ls) speak("clerk", ls.text);
    if (caught || t.verdict_kind === "held_up" || t.status === "cleared") confetti();
    if (t.status === "help") card.appendChild(helpActions(t));
    let after = card;
    if (t.feedback) { const fb = feedbackCard(t.feedback); after.after(fb); after = fb; }
    if (t.insight) {
      const ins = insightCard(t.insight, { practice: caught ? (btn, el) => practiceRound(t, el, btn) : null, hideRemember: caught,
        tryAgain: () => { const ta = card.querySelector(".tryagain"); if (ta) { ta.click(); ta.scrollIntoView({ behavior: "smooth", block: "center" }); }
                          else { const ob = $("#courtActions .objection"); if (ob) { ob.open = true; ob.scrollIntoView({ behavior: "smooth", block: "center" }); } } } });
      after.after(ins); after = ins;
    }
    if (t.status === "misconception_found" && t.insight?.next !== "practice") {
      const go = document.createElement("button");
      go.className = "primary practicego"; go.textContent = "Practice round →";
      go.onclick = () => practiceRound(t, after, go);
      card.appendChild(go);
    }
  }
  const row = document.createElement("div");
  row.className = "endrow";
  if (["explain_again", "misconception_found", "case_closed"].includes(t.status) && t.verdict_kind !== "out_of_scope") {
    row.appendChild(objectCard(t, t.status === "explain_again" ? "Explain again" : "I object! ✋", t.status === "explain_again"));
  }
  const again = document.createElement("button");
  again.className = ["misconception_found", "help"].includes(t.status) || t.insight ? "secondary" : "primary"; again.textContent = "Next case →";
  again.onclick = () => { show("home"); loadRehearings(); };
  row.appendChild(again);
  a.appendChild(row);
}

// ---------- practice round: three quick questions aimed at the idea the court just caught ----------
// Questions, the tip and the "why" lines arrive already translated; the options are content and stay as they are.
// Counters are shown as "2 / 3": "{n} of {n}" filled in order reads backwards in Hindi and Tamil.
const CHEERS = [[1, "Perfect! That sneaky idea doesn't stand a chance."], [0.5, "Great work! One more look and you've got it."],
                [0, "Good try! Every question makes your thinking stronger."]];
async function morePractice(id) {
  try {
    const r = await fetch(API + `/api/trial/${encodeURIComponent(id)}/practice/more`, { method: "POST" });
    if (!r.ok) return [];
    const d = await r.json();
    return (d.questions || []).map((q, j) => ({ ...q, idx: (d.start || 0) + j }));
  } catch (e) { return []; }
}
async function practiceRound(t, anchor, goBtn) {
  const id = t.trial_id;
  goBtn.disabled = true; goBtn.textContent = uiText("Getting your practice questions");
  let qs, tip = "";
  try {
    const r = await fetch(API + `/api/trial/${encodeURIComponent(id)}/practice`);
    if (!r.ok) throw new Error();
    const set = await r.json();
    qs = (set.questions || []).map((q, j) => ({ ...q, idx: j })); tip = set.tip || "";
    if (!qs.length) throw new Error();
    if ((set.answered || 0) >= qs.length) { qs = await morePractice(id); tip = ""; }   // already done once: fresh ones
    if (!qs.length) throw new Error();
  } catch (e) { goBtn.textContent = uiText("Practice isn't ready right now."); return; }
  goBtn.remove();
  const card = document.createElement("div");
  card.className = "practice";
  anchor.after(card);
  let i = 0, right = 0, lastQ = null, lastWhy = "";
  const ask = () => {
    const q = qs[i];
    card.className = "practice";
    card.innerHTML = `<div class="wtop"><span class="bang">PRACTICE ROUND!</span><span class="wcount" data-notr>${i + 1} / ${qs.length}</span></div>
      ${i === 0 && tip ? `<p class="ptip">${esc(tip)}</p>` : ""}
      <div class="wq">${esc(q.question)}</div><div class="opts"></div><div class="pfeed" aria-live="polite"></div>`;
    optionButtons(card.querySelector(".opts"), q.options, (o, b) => check(o, b));
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  const check = async (answer, btn) => {
    const q = qs[i];
    const btns = [...card.querySelectorAll(".optbtn")];
    btns.forEach((b) => (b.disabled = true));
    const feed = card.querySelector(".pfeed");
    feed.innerHTML = `<div class="hint">Checking…</div>`;
    let r;
    try { r = await post(`/api/trial/${encodeURIComponent(id)}/practice/${q.idx}`, { answer }); }
    catch (e) { feed.innerHTML = `<div class="hint">The court couldn't check that right now.</div>`; btns.forEach((b) => (b.disabled = false)); return; }
    if (r.correct) right++;
    if (!r.correct && !lastQ) { lastQ = q; lastWhy = r.why || ""; }   // look again at the FIRST one missed, not the one just read
    btn.classList.add(r.correct ? "isright" : "iswrong");
    if (!r.correct) btns.find((b) => b.querySelector(".optlabel")?.textContent === r.right_answer)?.classList.add("isright");
    const last = i === qs.length - 1;
    feed.innerHTML = (r.correct
      ? `<div class="pgood"><span class="ptick" aria-hidden="true">✓</span><b>Right!</b></div>`
      : `<div class="pbad"><b>Not quite. The answer is</b> <span class="pans">${esc(r.right_answer)}</span></div>`)
      + `<div class="whyproof">${proofFor(q.options)}${r.why ? `<p class="pwhy">${esc(r.why)}</p>` : ""}</div>`
      + `<button class="primary pnext">${last ? "See my score" : "Next →"}</button>`;
    speak("clerk", r.why || "");
    feed.querySelector(".pnext").onclick = () => { if (last) done(); else { i++; ask(); } };
  };
  const done = () => {
    const of = qs.length, cheer = CHEERS.find(([min]) => right / of >= min)[1];
    card.className = `practice done ${right === of ? "win" : "learn"}`;
    card.innerHTML = `<div class="stamp ${right === of ? "win" : "learn"}" data-notr>${right} / ${of}</div><p class="vline">${esc(uiText(cheer))}</p>`;
    speak("clerk", uiText(cheer));
    if (right === of) confetti();
    else if (lastQ) {
      // Not all right: look at one together (the pictures and the exact why), then two more tries.
      const ex = document.createElement("div");
      ex.className = "worked";
      ex.innerHTML = `<div class="workedtitle">Let's look at one together</div><div class="wq">${esc(lastQ.question)}</div>
        <div class="whyproof">${proofFor(lastQ.options)}${lastWhy ? `<p class="pwhy">${esc(lastWhy)}</p>` : ""}</div>
        <button class="primary moretries">2 more tries →</button>`;
      card.appendChild(ex);
      if (lastWhy) speak("clerk", lastWhy);
      const mb = ex.querySelector(".moretries");
      mb.onclick = async () => {
        mb.disabled = true; mb.textContent = uiText("Getting your practice questions");
        const more = await morePractice(id);
        if (!more.length) { mb.textContent = uiText("Practice isn't ready right now."); return; }
        qs = more; i = 0; right = 0; tip = ""; lastQ = null; lastWhy = ""; ask();
      };
    }
    card.scrollIntoView({ behavior: "smooth", block: "start" });
  };
  ask();
}

function objectCard(t, label, open = false) {
  const wrap = document.createElement("details");
  wrap.className = "card objection";
  wrap.open = open;
  wrap.innerHTML = `<summary>${open ? "Tell the court how you knew" : "Not happy with the verdict?"}</summary>
    <p class="hint">Say it again in your own words and the court re-hears the case.</p>
    <div class="whyrow"><textarea rows="2" placeholder="What I really meant was…" aria-label="Your reason"></textarea><button class="mic" aria-label="Speak your reason">🎤</button></div>
    <button class="secondary">${label}</button>`;
  attachMic(wrap.querySelector(".mic"), wrap.querySelector("textarea"));
  wrap.querySelector(".secondary").onclick = async () => {
    const why = wrap.querySelector("textarea").value.trim();
    if (!why) return needWhy(wrap.querySelector("textarea"));
    thinking("The court re-hears the case");
    try { await renderTrial(await hearCase(`/api/trial/${t.trial_id}/object`, { new_why: why })); } catch (e) { fail(e); }
  };
  return wrap;
}

// While the agents work (a minute or more on a phone), the cast takes turns "thinking" so the child sees the court busy.
const WAIT_TRIAL = [["clerk", "The Clerk checks your answer"], ["prosecutor", "The Prosecutor reads your reason"],
                    ["defence", "The Defence prepares"], ["judge", "The Judge decides"]];
const WAIT_CHECKUP = [["clerk", "The Clerk picks questions for you"], ["judge", "The Judge gets the court ready"],
                      ["prosecutor", "The Prosecutor sharpens a pencil"], ["defence", "The Defence cheers you on"]];
function waitCourt(el, label, lines = WAIT_TRIAL) {
  el.innerHTML = `<div class="waitcourt" role="status" aria-live="polite">
      <div class="wcast">${["clerk", "prosecutor", "defence", "judge"].map((r) => `<div class="wp" data-role="${r}">${face(r)}</div>`).join("")}</div>
      <div class="wbub"><span class="wbtext"></span><span class="dots"><span>.</span><span>.</span><span>.</span></span></div>
      <div class="wcap">${esc(uiText(label))}</div>
      <ol class="lines wlog"></ol></div>`;
  const box = el.querySelector(".waitcourt");
  const busy = (role, text) => {
    box.querySelectorAll(".wp").forEach((p) => p.classList.toggle("on", p.dataset.role === role));
    box.style.setProperty("--who", ["clerk", "prosecutor", "defence", "judge"].indexOf(role));
    box.querySelector(".wbtext").textContent = uiText(text);
  };
  let k = 0, real = false;
  const tick = () => {
    if (!box.isConnected) return clearInterval(timer);
    if (!real) busy(...lines[k++ % lines.length]);
  };
  // The real thing, as soon as the server reports it: who is working now, and what each court member decided.
  box.showLive = (items) => {
    if (!items || !items.length) return;
    real = true;
    const now = [...items].reverse().find((x) => x.kind === "working");
    if (now) busy(now.speaker, now.text);
    const said = items.filter((x) => x.kind === "said"), log = box.querySelector(".wlog");
    for (let i = log.children.length; i < said.length; i++) {
      const x = said[i], li = document.createElement("li");
      li.className = `line new ${x.speaker}`;
      li.innerHTML = `${face(x.speaker)}<div class="said"><span class="tag">${esc(uiText(NAMES[x.speaker] || x.speaker))}</span><span class="txt">${esc(uiText(x.text))}</span></div>`;
      log.appendChild(li);
    }
  };
  const timer = setInterval(tick, 2800);
  tick();
}
// A random key for this hearing; the browser asks the server what the court is doing every 1.5 s until it is done.
function liveKey() {
  const a = new Uint8Array(12);
  crypto.getRandomValues(a);
  return Array.from(a, (b) => b.toString(16).padStart(2, "0")).join("");
}
function watchLive(key) {
  let on = true;
  (async () => {
    while (on) {
      await sleep(1500);
      const box = document.querySelector("#courtActions .waitcourt");
      if (!on || !box) break;
      try {
        const r = await fetch(API + `/api/live/${key}`);
        if (r.ok && on) box.showLive((await r.json()).lines);
      } catch (e) { /* the hearing itself carries on */ }
    }
  })();
  return () => { on = false; };
}
let watchedLive = false;   // the child saw the court's decisions arrive while waiting: no need to replay them slowly
async function hearCase(path, body) {
  const key = liveKey(), stop = watchLive(key);
  let t;
  try { t = await post(path, { ...body, live: key }); } finally {
    stop();
    watchedLive = !!document.querySelector("#courtActions .wlog li");
  }
  return t;
}
function thinking(label = "The court is in session") { waitCourt($("#courtActions"), label); }
function fail(e) { $("#courtActions").innerHTML = `<div class="thinking">The court hit a problem: ${esc(e.message)}</div>`; }

async function startTrial(kase) {
  lastKase = kase;
  show("court");
  $("#lines").innerHTML = ""; $("#witlog").innerHTML = ""; $("#witlog").hidden = true;
  $("#earlier").hidden = true; $("#hearing").hidden = true; seen = 0;
  buildCast();
  slate(kase);
  thinking("The court is in session");
  $("#courtActions").focus({ preventScroll: true });
  try { await renderTrial(await hearCase("/api/trial", { case: kase, player: player(), lang: lang(), class_code: classCode() || undefined })); } catch (e) { fail(e); }
}

// ---------- language (remembered on this device only) ----------
function lang() { return $("#lang")?.value || "English"; }
try { const saved = localStorage.getItem("wc-lang"); if (saved) $("#lang").value = saved; } catch (e) { /* storage off */ }
$("#lang").onchange = () => { try { localStorage.setItem("wc-lang", lang()); } catch (e) { /* storage off */ } };
// ---------- the secret court name: links a child's trials and re-hearings without ever asking their name ----------
const ANIMALS = ["OWL", "FOX", "BEAR", "LION", "HAWK", "WOLF", "PANDA", "TIGER", "OTTER", "ZEBRA", "KOALA", "EAGLE", "SEAL", "LYNX", "YAK"];
const newCourtName = () => `${ANIMALS[Math.floor(Math.random() * ANIMALS.length)]}-${String(Math.floor(Math.random() * 90) + 10)}`;
const cleanName = (v) => String(v || "").toUpperCase().replace(/[^A-Z0-9-]/g, "").slice(0, 8);
function setCourtName(v) {
  const code = cleanName(v) || newCourtName();
  $("#player").value = code; $("#playerShow").textContent = code;
  try { localStorage.setItem("wc-player", code); } catch (e) { /* storage off: the name lasts for this visit */ }
}
let savedName = ""; try { savedName = localStorage.getItem("wc-player") || ""; } catch (e) { /* storage off */ }
setCourtName(savedName);
function editCourtName(open) {
  $("#player").hidden = !open; $("#playerShow").hidden = open;
  $("#playerEdit").textContent = open ? "save" : "change";
  if (open) { $("#player").focus(); $("#player").select(); }
}
$("#playerEdit").onclick = () => {
  if ($("#player").hidden) return editCourtName(true);
  setCourtName($("#player").value); editCourtName(false); loadRehearings();
};
$("#player").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); $("#playerEdit").click(); } });

// ---------- re-hearing day: a caught idea comes back a week later ----------
const REHEAR = {
  fixed: ["IDEA GONE!", "win"],
  still_there: ["STILL SNEAKING AROUND", "learn"],
  mixed: ["THE CASE CONTINUES", "help"],
};
async function loadRehearings() {
  const box = $("#rehearing");
  box.innerHTML = "";
  const code = ($("#player").value || "").trim();
  if (!code) return;
  let due = [];
  try {
    const r = await fetch(API + `/api/rehearings?player=${encodeURIComponent(code)}`);
    if (!r.ok) return;              // not available yet: stay quiet
    due = (await r.json()).due || [];
  } catch (e) { return; }
  if (!due.length) return;
  const item = due[0];
  const answers = [];
  const card = document.createElement("div");
  card.className = "rehear";
  box.appendChild(card);
  const ask = () => {
    const i = answers.length;
    const q = item.questions[i];
    card.innerHTML = `<div class="wtop"><span class="bang">REMEMBER THIS ONE?</span><span class="wcount" data-notr>${i + 1} / ${item.questions.length}</span></div>
      <p class="hint">Let's see if the sneaky idea is gone</p>
      <div class="wq">${esc(q.question)}</div><div class="opts"></div>`;
    optionButtons(card.querySelector(".opts"), q.options, (o) => { answers.push(o); answers.length < item.questions.length ? ask() : finish(); });
  };
  const finish = async () => {
    card.innerHTML = `<div class="thinking">⚖ The court checks your answers<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>`;
    try {
      const r = await post(`/api/rehearings/${encodeURIComponent(item.id)}`, { answers });
      const v = REHEAR[r.result] || REHEAR.mixed;
      card.className = `rehear done ${v[1]}`;
      card.innerHTML = `<div class="stamp ${v[1]}">${v[0]}</div><p class="vline">${esc(r.message || "")}</p>
        ${item.idea ? `<p class="hint">The old idea: “${esc(item.idea)}”</p>` : ""}`;
      if (r.result === "fixed") { card.classList.add("party"); confetti(); }
      if (r.practice && r.trial_id) {
        const go = document.createElement("button");
        go.className = "primary practicego"; go.textContent = "Let's practise it →";
        go.onclick = () => practiceRound({ trial_id: r.trial_id }, card, go);
        card.appendChild(go);
      }
    } catch (e) { card.innerHTML = `<div class="hint">The court couldn't check that right now.</div>`; }
  };
  ask();
}
let pTimer;
$("#player").addEventListener("input", () => {   // typing a teacher's code (or a script filling it in) takes effect
  const code = cleanName($("#player").value);
  if (!code) return;
  $("#playerShow").textContent = code;
  try { localStorage.setItem("wc-player", code); } catch (e) { /* storage off */ }
  clearTimeout(pTimer); pTimer = setTimeout(loadRehearings, 500);
});

// ---------- the bench on the home screen ----------
// One small comic courtroom, drawn inline: wall and pillars, the judge behind the bench with a gavel, the
// prosecution and defence tables, and the child in the witness stand. Same ink lines and palette as the rest.
function person(who, cx, cy, scale, robe) {
  const s = 60 * scale;
  return `<ellipse cx="${cx}" cy="${cy + s * .62}" rx="${s * .62}" ry="${s * .4}" fill="${robe}" stroke="#15110d" stroke-width="3"/>
    <circle cx="${cx}" cy="${cy}" r="${s * .36}" fill="#fff" stroke="#15110d" stroke-width="3"/>
    <g transform="translate(${cx - 30 * scale} ${cy - 32 * scale}) scale(${scale})" stroke="#15110d" fill="none">${FACES[who]}</g>`;
}
function plate(x, y, w, label, fill) {
  return `<rect x="${x - w / 2}" y="${y}" width="${w}" height="24" fill="${fill}" stroke="#15110d" stroke-width="2.5"/>
    <text x="${x}" y="${y + 18}" text-anchor="middle" class="sceneplate">${esc(uiText(label))}</text>`;
}
function drawBench() {
  const el = $("#scene");
  if (!el) return;
  const planks = [292, 334, 376].map((y) => `<path d="M0 ${y}H520" stroke="#15110d" stroke-opacity=".22" stroke-width="2"/>`).join("");
  const panels = [24, 132, 300, 408].map((x) => `<rect x="${x}" y="200" width="88" height="40" fill="none" stroke="#15110d" stroke-opacity=".35" stroke-width="2"/>`).join("");
  el.innerHTML = `<svg viewBox="0 0 520 400" role="img" aria-label="A comic courtroom" class="scene">
    <rect width="520" height="252" fill="#f3e2bf"/>
    <rect x="0" y="190" width="520" height="62" fill="#d9a86c" stroke="#15110d" stroke-width="3"/>${panels}
    <rect x="34" y="-4" width="34" height="194" fill="#ecd3a2" stroke="#15110d" stroke-width="3"/>
    <rect x="452" y="-4" width="34" height="194" fill="#ecd3a2" stroke="#15110d" stroke-width="3"/>
    <rect x="26" y="0" width="50" height="14" fill="#ecd3a2" stroke="#15110d" stroke-width="3"/>
    <rect x="444" y="0" width="50" height="14" fill="#ecd3a2" stroke="#15110d" stroke-width="3"/>
    <circle cx="260" cy="36" r="26" fill="#f6b93b" stroke="#15110d" stroke-width="3"/>
    <path d="M260 20v32M242 27h36M248 52h24" stroke="#15110d" stroke-width="3" stroke-linecap="round"/>
    <path d="M242 27l-7 12h14zM278 27l-7 12h14z" fill="#fff" stroke="#15110d" stroke-width="2.5" stroke-linejoin="round"/>
    <rect y="252" width="520" height="148" fill="#b9773d"/><path d="M0 252H520" stroke="#15110d" stroke-width="3"/>${planks}
    ${person("judge", 260, 108, 1.25, "#3b2d5c")}
    <rect x="140" y="146" width="240" height="16" fill="#a8622e" stroke="#15110d" stroke-width="3"/>
    <rect x="150" y="162" width="220" height="100" fill="#8a4f24" stroke="#15110d" stroke-width="3"/>
    <rect x="168" y="176" width="184" height="70" fill="#7a4420" stroke="#15110d" stroke-width="2.5"/>
    ${plate(260, 199, 112, "JUDGE", "#6b3fa0")}
    <rect x="318" y="134" width="34" height="12" rx="2" fill="#5a3214" stroke="#15110d" stroke-width="2.5"/>
    <g transform="rotate(-28 340 118)"><rect x="337" y="118" width="7" height="34" fill="#6b3a17" stroke="#15110d" stroke-width="2.5"/>
      <rect x="320" y="104" width="42" height="18" rx="4" fill="#6b3a17" stroke="#15110d" stroke-width="2.5"/></g>
    <text x="392" y="112" class="scenesfx" transform="rotate(-8 392 112)">BANG!</text>
    ${person("prosecutor", 92, 222, 1.05, "#e03b2f")}
    <rect x="24" y="270" width="136" height="16" fill="#a8622e" stroke="#15110d" stroke-width="3"/>
    <rect x="34" y="286" width="116" height="52" fill="#8a4f24" stroke="#15110d" stroke-width="3"/>
    ${plate(92, 298, 104, "PROSECUTOR", "#e03b2f")}
    ${person("defence", 428, 222, 1.05, "#1f6fd0")}
    <rect x="360" y="270" width="136" height="16" fill="#a8622e" stroke="#15110d" stroke-width="3"/>
    <rect x="370" y="286" width="116" height="52" fill="#8a4f24" stroke="#15110d" stroke-width="3"/>
    ${plate(428, 298, 104, "DEFENCE", "#1f6fd0")}
    ${person("student", 260, 290, 1.05, "#f6b93b")}
    <rect x="196" y="328" width="128" height="14" fill="#8a4f24" stroke="#15110d" stroke-width="3"/>
    <rect x="204" y="342" width="112" height="64" fill="#a8622e" stroke="#15110d" stroke-width="3"/>
    ${plate(260, 354, 64, "YOU", "#15110d")}
  </svg>`;
}
loadRehearings();   // the scene is drawn once the screen language is known (end of file)

// ---------- screens ----------
document.querySelectorAll("[data-go]").forEach((b) => (b.onclick = () => show(b.dataset.go)));
$("#homeBtn").onclick = () => { show("home"); loadRehearings(); };

$("#photo").onchange = (e) => {
  const f = e.target.files[0];
  if (!f) return;
  const img = $("#preview"); img.src = URL.createObjectURL(f); img.hidden = false;
};

let readTurn = 0;
$("#readHw").onclick = async () => {
  const turn = ++readTurn;
  const f = $("#photo").files[0];
  const text = $("#hwText").value.trim();
  if (!f && !text) return alert(uiText("Add a photo or type your homework"));
  const fd = new FormData();
  if (f) fd.append("photo", await shrink(f));
  fd.append("text", text);
  $("#readHw").textContent = "Reading…"; $("#readHw").disabled = true;
  try {
    const r = await post("/api/homework", fd, true);
    if (turn !== readTurn || document.querySelector(".screen.active")?.id !== "upload") return;   // the child moved on
    const list = $("#caseList"); list.innerHTML = "";
    $("#unreadable").hidden = !r.unreadable; $("#unreadable").textContent = r.unreadable ? uiText("Couldn't read:") + " " + r.unreadable : "";
    if (!r.cases.length) list.innerHTML = `<div class="hint">Type your question or snap a photo — the court will ask what YOU think.</div>`;
    r.cases.forEach((c) => list.appendChild(caseCard(c)));
    // This homework is read: clear the photo and text, so the next homework never brings the old one back.
    $("#photo").value = ""; $("#preview").hidden = true; $("#preview").removeAttribute("src"); $("#hwText").value = "";
    show("cases");
    list.querySelector("textarea, button")?.focus({ preventScroll: true });
  } catch (e) { alert(e.message); }
  $("#readHw").textContent = "Read my homework"; $("#readHw").disabled = false;
};

// Phones take huge photos; shrink to ~1600px before upload.
function shrink(file) {
  return new Promise((res) => {
    const img = new Image();
    img.onload = () => {
      const s = Math.min(1, 1600 / Math.max(img.width, img.height));
      const c = document.createElement("canvas"); c.width = img.width * s; c.height = img.height * s;
      c.getContext("2d").drawImage(img, 0, 0, c.width, c.height);
      c.toBlob((b) => res(new File([b], "homework.jpg", { type: "image/jpeg" })), "image/jpeg", 0.85);
    };
    img.src = URL.createObjectURL(file);
  });
}

function addOptionPicker(card, options) {
  const input = card.querySelector(".ans");
  if (!input) return;
  const row = document.createElement("div"); row.className = "actions";
  options.forEach((o) => {
    const b = document.createElement("button");
    b.className = "secondary"; b.textContent = o;
    b.onclick = () => { input.value = o; row.querySelectorAll("button").forEach((x) => (x.style.background = x === b ? "var(--gold)" : "var(--panel)")); };
    row.appendChild(b);
  });
  input.hidden = true; input.before(row);
  card.querySelector(".opts-line")?.remove();
}

EPISODES.forEach((ep) => {
  const wrap = document.createElement("div");
  wrap.innerHTML = `<h3>${esc(ep.title)}</h3><p class="hint">${esc(ep.blurb)}</p>`;
  wrap.appendChild(caseCard(ep.case, "Start the trial ⚖"));
  $("#episodeList").appendChild(wrap);
});

// ---------- Law Library ----------
let openBook = null;

async function loadLibrary() {
  const list = $("#bookList");
  list.innerHTML = `<div class="thinking">Opening the library<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>`;
  try {
    const books = await getJSON(`/api/books${classCode() ? `?class_=${encodeURIComponent(classCode())}` : ""}`);
    list.innerHTML = "";
    books.forEach((b) => {
      const el = document.createElement("button");
      el.className = "bookcard";
      el.innerHTML = `<b>${esc(b.title)}</b><small>${esc(b.subject)} · grade ${esc(b.grade || "—")}<br>${b.chapters} chapters · ${b.origin === "uploaded" ? "your class's book" : "built in"}</small>`;
      el.onclick = () => openBookView(b.book_id);
      list.appendChild(el);
    });
  } catch (e) { list.innerHTML = `<div class="hint">${esc(e.message)}</div>`; }
}

async function openBookView(id) {
  show("bookview");
  $("#chapterList").innerHTML = `<div class="thinking">…</div>`;
  openBook = await getJSON(`/api/books/${id}`);
  $("#bookTitle").textContent = openBook.title;
  $("#chapterList").innerHTML = "";
  openBook.chapters.forEach((c) => {
    const el = document.createElement("button");
    el.className = "chap";
    el.innerHTML = `<small>Chapter ${esc(c.number)}</small><b>${esc(c.title)}</b>`;
    el.onclick = () => openChapter(c.chapter_id);
    $("#chapterList").appendChild(el);
  });
}

async function openChapter(cid) {
  show("chapterview");
  $("#chapterTitle").textContent = "";
  $("#keyRules").innerHTML = `<div class="thinking">Reading the chapter and its exercises<span class="dots"><span>.</span><span>.</span><span>.</span></span></div>`;
  $("#exerciseList").innerHTML = "";
  const ch = await getJSON(`/api/books/${openBook.book_id}/chapters/${cid}`);
  $("#chapterTitle").textContent = `Chapter ${ch.number}: ${ch.title}`;
  $("#keyRules").innerHTML = `<div class="exid">THE LAW · key rules of this chapter</div>${esc(ch.key_rules)}`;
  if (ch.attribution) $("#keyRules").insertAdjacentHTML("beforeend", `<div class="attrib">${esc(ch.attribution)}</div>`);
  const ref = `${ch.book_title}, Chapter ${ch.number} '${ch.title}'. Key rules: ${ch.key_rules}`;
  if (!ch.exercises?.length) $("#exerciseList").innerHTML = `<div class="hint">No exercises found in this chapter.</div>`;
  ch.exercises.forEach((ex) => {
    const kase = { subject: ch.subject === "mixed" ? guessSubject(ch.title) : ch.subject, grade: ch.grade, question: ex.text, options: ex.options || [],
      student_answer: "", correct_answer: ex.answer || null, source: "book", book_ref: ref,
      book_id: openBook.book_id, chapter_id: cid };   // lets the court borrow this chapter's other exercises
    const card = caseCard(kase, "Answer & go to court ⚖");
    card.insertAdjacentHTML("afterbegin", `<div class="exid">EXERCISE ${esc(ex.id)}</div>`);
    if (kase.options.length) addOptionPicker(card, kase.options);
    $("#exerciseList").appendChild(card);
  });
}
function guessSubject(t) { t = t.toLowerCase(); return t.includes("science") ? "science" : t.includes("english") ? "english" : "maths"; }

$("#backToBook").onclick = () => openBook && openBookView(openBook.book_id);

// On the shared site the API runs on AWS Lambda, which takes at most 6 MB per request: say so before uploading.
const MAX_BOOK_MB = window.WHYCOURT_API ? 5 : 40;
$("#addBook").onclick = async () => {
  const f = $("#bPdf").files[0], err = $("#bErr"), code = cleanClass($("#bClass").value), pin = $("#bPin").value.trim();
  err.textContent = "";
  if (!code || !pin) { err.textContent = uiText("Type your class code and teacher PIN first."); return; }
  if (!$("#bTitle").value.trim()) { err.textContent = uiText("Give the book a title."); return; }
  if (!f) { err.textContent = uiText("Choose the PDF of your textbook."); return; }
  if (f.size > MAX_BOOK_MB * 2 ** 20) {
    err.textContent = uiText(`This PDF is too big. The court can read PDFs up to ${MAX_BOOK_MB} MB: try a smaller file, or just the chapters you need.`);
    return;
  }
  const fd = new FormData();
  fd.append("pdf", f); fd.append("title", $("#bTitle").value.trim());
  fd.append("subject", $("#bSubject").value); fd.append("grade", $("#bGrade").value.trim());
  const b = $("#addBook"); b.textContent = uiText("Reading the table of contents…"); b.disabled = true;
  try {
    await post("/api/books", fd, true, { "X-Class-Code": code, "X-Class-Pin": pin });
    if (!classCode()) { $("#classCode").value = code; checkClass(); }   // so this device sees the class's book
    loadLibrary();
  } catch (e) { err.textContent = e.message === "Failed to fetch" ? uiText("The court couldn't take that file. Try a smaller PDF.") : e.message; }
  b.textContent = uiText("Add to library"); b.disabled = false;
};

document.querySelectorAll('[data-go="library"]').forEach((b) => b.addEventListener("click", loadLibrary));

// ---------- class code: links a child's trials to their teacher's class (optional) ----------
const cleanClass = (v) => String(v || "").toUpperCase().replace(/[^A-Z0-9-]/g, "").slice(0, 12);
function classCode() { return cleanClass($("#classCode")?.value); }
let classTimer, classAsked = "";
async function checkClass() {
  const code = classCode(), st = $("#classStatus");
  try { code ? localStorage.setItem("wc-class", code) : localStorage.removeItem("wc-class"); } catch (e) { /* storage off */ }
  if (code === classAsked) return;
  classAsked = code; st.textContent = ""; st.className = "cc-status";
  if (!code) return;
  try {
    const r = await fetch(API + `/api/classes/${encodeURIComponent(code)}`);
    if (code !== classAsked) return;            // typed on since
    if (r.ok) { const c = await r.json(); st.innerHTML = `✓ <span data-notr>${esc(c.name)}</span>`; st.classList.add("ok"); }
    else if (r.status === 404) { st.textContent = "We can't find that class"; st.classList.add("bad"); }
  } catch (e) { /* not available yet: stay quiet */ }
}
try { $("#classCode").value = localStorage.getItem("wc-class") || ""; } catch (e) { /* storage off */ }
$("#classCode").addEventListener("input", () => {
  const v = cleanClass($("#classCode").value); if ($("#classCode").value !== v) $("#classCode").value = v;
  clearTimeout(classTimer); classTimer = setTimeout(checkClass, 600);
});
$("#classCode").addEventListener("change", checkClass);
checkClass();

// ---------- say your homework: the child reads it out and the words appear as they speak ----------
(() => {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition, btn = $("#sayHw"), box = $("#hwText");
  if (!SR) { $("#sayRow").hidden = true; return; }
  let rec = null;
  btn.onclick = () => {
    if (rec) { rec.stop(); return; }
    rec = new SR(); rec.lang = SPEECH_LANG[lang()] || "en-IN"; rec.continuous = true; rec.interimResults = true;
    const base = box.value.trim(); let heard = "";
    const show = (interim = "") => { box.value = [base, heard.trim(), interim.trim()].filter(Boolean).join(" "); };
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        if (e.results[i].isFinal) heard += e.results[i][0].transcript + " "; else interim += e.results[i][0].transcript;
      }
      show(interim);
    };
    rec.onend = rec.onerror = () => { show(); rec = null; btn.classList.remove("on"); $("#sayLabel").textContent = uiText("Say it instead"); };
    btn.classList.add("on"); $("#sayLabel").textContent = uiText("Stop listening");
    try { rec.start(); } catch (e) { rec = null; btn.classList.remove("on"); }
  };
})();

// ---------- chapter check-up: a few adaptive questions on one chapter, looking for a sneaky idea ----------
try { const g = localStorage.getItem("wc-grade"); if (g) $("#grade").value = g; } catch (e) { /* storage off */ }
$("#grade").onchange = () => { try { localStorage.setItem("wc-grade", $("#grade").value); } catch (e) { /* storage off */ } };
const CU_DONE = { found: ["SNEAKY IDEA FOUND!", "learn"], clear: ["YOUR THINKING HOLDS UP!", "win"], not_proven: ["NO VERDICT YET", "help"] };
let cuReady = false;
function cuTab(which) {
  $("#cuBook").hidden = which !== "book"; $("#cuTopic").hidden = which !== "topic";
  $("#cuTabBook").classList.toggle("on", which === "book"); $("#cuTabTopic").classList.toggle("on", which === "topic");
  $("#cuTabBook").setAttribute("aria-selected", which === "book"); $("#cuTabTopic").setAttribute("aria-selected", which === "topic");
  if (which === "topic") cuLoadTopics();
}
function cuMsg(text) { $("#cuMsg").hidden = !text; $("#cuMsg").textContent = text || ""; }
$("#cuTabBook").onclick = () => cuTab("book");
$("#cuTabTopic").onclick = () => cuTab("topic");
async function cuOpen() {
  $("#cuSetup").hidden = false; $("#cuStage").innerHTML = ""; cuMsg("");
  if (cuReady) return;
  cuReady = true;
  try {
    const books = await getJSON(`/api/books${classCode() ? `?class_=${encodeURIComponent(classCode())}` : ""}`);
    $("#cuBookSel").innerHTML = books.map((b) => `<option value="${esc(b.book_id)}">${esc(b.title)}</option>`).join("");
    if (books.length) cuChapters(books[0].book_id); else cuTab("topic");
  } catch (e) { cuTab("topic"); }
}
$("#cuBookSel").onchange = () => cuChapters($("#cuBookSel").value);
async function cuChapters(id) {
  const list = $("#cuChapters");
  list.innerHTML = `<div class="hint">Opening the library…</div>`;
  try {
    const b = await getJSON(`/api/books/${encodeURIComponent(id)}`);
    list.innerHTML = "";
    b.chapters.forEach((c) => {
      const el = document.createElement("button");
      el.className = "chap";
      el.innerHTML = `<small>Chapter ${esc(c.number)}</small><b data-notr>${esc(c.title)}</b>`;
      el.onclick = () => cuStart({ book_id: id, chapter_id: c.chapter_id }, c.title);
      list.appendChild(el);
    });
  } catch (e) { list.innerHTML = `<div class="hint">The library isn't available right now.</div>`; }
}
let cuTopicsLoaded = false;
async function cuLoadTopics() {
  if (cuTopicsLoaded) return;
  const list = $("#cuTopics");
  list.innerHTML = `<div class="hint">Finding topics…</div>`;
  try {
    const r = await fetch(API + "/api/topics");
    if (!r.ok) throw new Error();
    const topics = await r.json();
    cuTopicsLoaded = true;
    list.innerHTML = "";
    topics.forEach((t) => {
      const el = document.createElement("button");
      el.className = "chap";
      el.innerHTML = `<small>${esc(uiText(t.subject || ""))}</small><b data-notr>${esc(uiText(t.name))}</b>`;
      el.onclick = () => cuStart({ topic: t.id }, uiText(t.name));
      list.appendChild(el);
    });
    if (!topics.length) list.innerHTML = `<div class="hint">No topics yet.</div>`;
  } catch (e) { list.innerHTML = `<div class="hint">Topics aren't ready yet.</div>`; }
}
async function cuStart(pick, label) {
  cuMsg("");
  const stage = $("#cuStage");
  $("#cuSetup").hidden = true;
  waitCourt(stage, "The court prepares your check-up", WAIT_CHECKUP);
  let r;
  try {
    r = await fetch(API + "/api/checkup", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...pick, grade: $("#grade").value, player: player(), class_code: classCode() || undefined, lang: lang() }) });
  } catch (e) { r = null; }
  if (!r || !r.ok) {
    let detail = "";
    if (r && r.status === 422) { try { detail = (await r.json()).detail; } catch (e) { /* no body */ } }
    stage.innerHTML = ""; $("#cuSetup").hidden = false;
    if (r && r.status === 422) { cuMsg(typeof detail === "string" && detail ? detail : uiText("This chapter has no check-up yet. Pick a topic instead.")); cuTab("topic"); }
    else cuMsg(uiText("The check-up isn't ready yet."));
    return;
  }
  const d = await r.json();
  cuAsk(d.trial_id, d.topic_name || label, d.question, d.n || 1);
}
function cuAsk(id, topic, q, n) {
  const stage = $("#cuStage");
  let chosen = null;
  stage.innerHTML = `<div class="witness checkq"><div class="wtop"><span class="bang">CHECK-UP!</span><span class="wcount">Question ${n}</span></div>
      <div class="cu-topic" data-notr>${esc(topic || "")}</div>
      <div class="wq">${esc(q.question)}</div><div class="opts"></div>
      <details class="cu-why"><summary>Why? (optional)</summary>
        <div class="whyrow"><textarea rows="2" placeholder="How did you know?" aria-label="Why? (optional)"></textarea><button class="mic" aria-label="Speak your reason">🎤</button></div></details>
      <button class="primary cu-lock" disabled>That's my answer →</button></div>`;
  const card = stage.firstElementChild, lock = card.querySelector(".cu-lock");
  attachMic(card.querySelector(".mic"), card.querySelector("textarea"));
  optionButtons(card.querySelector(".opts"), q.options, (o, b) => {
    chosen = o; card.querySelectorAll(".optbtn").forEach((x) => x.classList.toggle("picked", x === b)); lock.disabled = false;
  });
  if (n === 1) speak("judge", q.question);
  card.scrollIntoView({ behavior: "smooth", block: "start" });
  lock.onclick = async () => {
    if (!chosen) return;
    lock.disabled = true; lock.textContent = uiText("The court considers your answer");
    let d;
    try { d = await post(`/api/checkup/${encodeURIComponent(id)}`, { answer: chosen, why: card.querySelector("textarea").value.trim() }); }
    catch (e) { lock.disabled = false; lock.textContent = uiText("That's my answer →"); return; }
    if (d.done) cuDone(id, d); else cuAsk(id, topic, d.question, d.n || n + 1);
  };
}
function cuDone(id, d) {
  const v = CU_DONE[d.result] || CU_DONE.not_proven, stage = $("#cuStage");
  stage.innerHTML = "";
  const card = document.createElement("div");
  card.className = `verdict ${v[1]}`;
  card.innerHTML = `<div class="stamp ${v[1]}">${v[0]}</div>${d.message ? `<p class="vline">${esc(d.message)}</p>` : ""}
    ${d.idea && !String(d.message || "").includes(d.idea) ? `<p class="cu-idea"><span>The sneaky idea:</span> <b data-notr>“${esc(d.idea)}”</b></p>` : ""}`;
  stage.appendChild(card);
  if (d.message) speak("judge", d.message);
  if (d.result === "found" || d.result === "clear") confetti();
  let after = card;
  if (d.insight) { after = insightCard(d.insight, { practice: d.practice ? (btn, el) => practiceRound({ trial_id: id }, el, btn) : null, inCheckup: true }); card.after(after); }
  if (d.result === "found" && d.practice && d.insight?.next !== "practice") {
    const go = document.createElement("button");
    go.className = "primary practicego"; go.textContent = "Practice round →";
    go.onclick = () => practiceRound({ trial_id: id }, after, go);
    card.appendChild(go);
  }
  const row = document.createElement("div");
  row.className = "endrow";
  const again = document.createElement("button");
  again.className = "secondary"; again.textContent = "Another check-up";
  again.onclick = () => { cuOpen(); window.scrollTo(0, 0); };
  const home = document.createElement("button");
  home.className = d.result === "found" && d.practice ? "secondary" : "primary"; home.textContent = "Home";
  home.onclick = () => { show("home"); loadRehearings(); };
  row.append(again, home);
  stage.appendChild(row);
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------- the insight card: what the court learned about the child's thinking ----------
// headline, points and remember arrive already translated; "next" chooses the one button.
function insightCard(ins, ctx = {}) {
  const el = document.createElement("div");
  el.className = "insight";
  el.innerHTML = `<div class="insighttitle">What the court learned about your thinking</div>
    ${ins.headline ? `<p class="ihead">${esc(uiText(ins.headline))}</p>` : ""}
    ${ins.points?.length ? `<ul class="ipoints">${ins.points.map((p) => `<li>${esc(p)}</li>`).join("")}</ul>` : ""}
    ${ins.remember && !ctx.hideRemember ? `<p class="iremember"><b>Remember:</b> <span class="irtext">${esc(ins.remember)}</span></p>` : ""}`;
  let next = ins.next || "home";
  if ((next === "practice" && !ctx.practice) || (next === "try_again" && !ctx.tryAgain)) next = "home";
  if (ctx.inCheckup && next !== "practice") return el;      // the check-up screen has its own "Another check-up" and "Home"
  const btn = document.createElement("button");
  btn.className = "primary inext";
  btn.textContent = { practice: "Practice round →", checkup: "Try a chapter check-up →", try_again: "Try again" }[next] || "Home";
  btn.onclick = () => {
    if (next === "practice") ctx.practice(btn, el);
    else if (next === "try_again") ctx.tryAgain();
    else if (next === "checkup") { show("checkup"); cuOpen(); }
    else { show("home"); loadRehearings(); }
  };
  el.appendChild(btn);
  return el;
}

// ---------- reason check: kind, specific feedback when the court could not test the reason with a witness ----------
function feedbackCard(fb) {
  const el = document.createElement("div");
  el.className = "insight feedback";
  const part = (label, text, cls) => (text ? `<div class="fbpart ${cls}"><div class="fblabel">${label}</div><p class="fbtext">${esc(text)}</p></div>` : "");
  el.innerHTML = `<div class="insighttitle">Reason check</div>
    ${part("What you did well", fb.good, "good")}${part("Think about", fb.think, "think")}${part("Try this", fb.try_this, "try")}`;
  return el;
}

// ---------- a wrong answer: try again, or be taught ----------
let lastKase = null;
// Caught before sending: a reason is what the court tries, so ask for it here, not after a trip to the court.
function needWhy(ta) {
  let note = ta.closest(".whyrow").previousElementSibling;
  if (!note?.classList.contains("needwhy")) {
    note = document.createElement("div"); note.className = "needwhy";
    note.textContent = uiText("Tell the court why first! Type it or tap 🎤 to say it.");
    ta.closest(".whyrow").before(note);
  }
  ta.classList.add("wantwhy"); ta.focus();
  speak("clerk", note.textContent);
}

function helpActions(t) {
  const box = document.createElement("div");
  box.className = "helpacts";
  box.innerHTML = `<div class="helpbtns"><button class="primary tryagain">Try again</button><button class="secondary teachme">Teach me</button></div>
    <div class="retry" hidden><input class="ans" placeholder="Your new answer" aria-label="Your new answer">
      <div class="whyrow"><textarea class="why" rows="2" placeholder="Tell the court why you knew…" aria-label="Your reason"></textarea><button class="mic" aria-label="Speak your reason">🎤</button></div>
      <button class="primary go">Put it on trial ⚖</button></div>`;
  const kase = t.case || lastKase;
  attachMic(box.querySelector(".mic"), box.querySelector(".why"));
  if (kase?.options?.length) addOptionPicker(box.querySelector(".retry"), kase.options);   // same buttons as the question
  box.querySelector(".tryagain").onclick = () => {
    box.querySelector(".retry").hidden = false;
    (box.querySelector(".retry .actions button") || box.querySelector(".ans")).focus();
  };
  box.querySelector(".go").onclick = () => {
    const ans = box.querySelector(".ans").value.trim();
    if (!ans || !kase) return alert(uiText("Give your answer first!"));
    if (!box.querySelector(".why").value.trim()) return needWhy(box.querySelector(".why"));
    startTrial({ ...kase, student_answer: ans, student_why: box.querySelector(".why").value.trim() });
  };
  const teach = box.querySelector(".teachme");
  teach.onclick = async () => {
    teach.disabled = true; teach.textContent = uiText("The clerk is getting a lesson ready");
    try {
      const r = await fetch(API + `/api/trial/${encodeURIComponent(t.trial_id)}/teach`, { method: "POST" });
      if (!r.ok) throw new Error();
      const ls = await r.json();
      const lesson = document.createElement("div");
      lesson.className = "lesson taught";
      lesson.innerHTML = `<div class="lessontitle">${esc(ls.title || "Lesson")}</div><p class="lessontext">${esc(ls.explanation || "")}</p>
        ${ls.try_this ? `<div class="tryline"><b>${esc(uiText("Try this:"))}</b> ${esc(ls.try_this)}
          ${ls.try_this_answer ? `<details><summary>${esc(uiText("Show answer"))}</summary>${esc(ls.try_this_answer)}</details>` : ""}</div>` : ""}`;
      box.after(lesson); teach.remove();
      speak("clerk", ls.explanation || "");
    } catch (e) { teach.textContent = uiText("Lessons aren't ready right now."); teach.disabled = false; }   // a tap tries again
  };
  return box;
}
$("#checkupBtn").addEventListener("click", cuOpen);

// ---------- the screen in the child's language ----------
// The court's own lines arrive already translated by the Interpreter agent. This puts the app's buttons, labels and
// hints into the child's language from fixed, checked files (web/i18n/<Language>.json, made by
// scripts/translate_ui.py), so switching language is instant and no model runs at this point.
// Content is never touched: homework, questions, answer options and court lines.
const NOTR = ".q, .opts-line, .a b, .why, .txt, .evidence, .wq, .wq2, .wa b, .optbtn, .vline, .lessontitle, .lessontext, .ptip, .pwhy, .pans, #classCode, #hwText, #cuMsg, .ihead, .ipoints, .irtext, .optlabel, .ideatext, .fbtext, .wq, "
  + ".tryline, .mine b, #keyRules, #exerciseList, #chapterTitle, #bookTitle, .bookcard, #lang, script, style, svg, textarea, [data-notr]";
// Strings the app writes while it runs (they are not in the page until then), so the translation files cover them.
const UI_EXTRA = ["Put it on trial ⚖", "Tell the court why you knew…", "Speak your reason", "Give your answer first!",
  "Who's in court", "EXHIBIT A", "Your answer:", "YOU OBJECT", "CASE CLOSED!", "Your reasoning holds up.", "CLEARED!",
  "The witnesses agreed with you.", "SNEAKY IDEA CAUGHT!", "That's a win — now you know it.", "MISTRIAL",
  "Let's fix the answer first.", "THE COURT NEEDS MORE", "Tell us how you knew.", "SURPRISE WITNESS!", "Witness {n}",
  "Tap your answer. Think it through your own way.", "The court considers your answer", "The court calls a surprise witness!",
  "NOT PROVEN", "You go free. Case closed.", "Lesson", "Read the whole lesson", "Try this:", "Show answer", "Explain again",
  "I object! ✋", "Next case →", "Tell the court how you knew", "Not happy with the verdict?", "What I really meant was…",
  "Your reason", "The court re-hears the case", "The court is in session", "You said", "RE-HEARING DAY!", "{n} of {n}",
  "The court is back to check on an old case. Answer your own way.", "The court checks your answers", "IDEA GONE!",
  "STILL SNEAKING AROUND", "THE CASE CONTINUES", "The old idea:", "The court couldn't check that right now.",
  "No answered questions found. Try a clearer photo.", "Opening the library", "Reading the chapter and its exercises",
  "No exercises found in this chapter.", "The court hit a problem:", "Your first try (before you objected)", "Your answer", "Add a photo or type your homework",
  "Reading…", "Say it again in your own words and the court re-hears the case.", "JUDGE", "PROSECUTOR", "DEFENCE",
  "COURT CLERK", "YOU", "save", "Practice round →", "Getting your practice questions", "Practice isn't ready right now.",
  "PRACTICE ROUND!", "Checking…", "Right!", "Not quite. The answer is", "See my score", "Next →",
  "Perfect! That sneaky idea doesn't stand a chance.", "Great work! One more look and you've got it.",
  "Good try! Every question makes your thinking stronger.", "Your court name lets the court check back with you. Your teacher may give you one. We never ask your real name.",
  "or start from", "PROSECUTOR", "DEFENCE", "JUDGE", "We can't find that class", "Say it instead", "Stop listening",
  "Opening the library…", "The library isn't available right now.", "Finding topics…", "Topics aren't ready yet.", "No topics yet.",
  "The court prepares your check-up", "This chapter has no check-up yet. Pick a topic instead.", "The check-up isn't ready yet.",
  "CHECK-UP!", "Question {n}", "Why? (optional)", "How did you know?", "Lock it in →", "SNEAKY IDEA FOUND!",
  "YOUR THINKING HOLDS UP!", "NO SNEAKY IDEA FOUND", "The sneaky idea:", "Another check-up", "Home", "Chapter {n}",
  "Skip ⏩", "bigger", "Good question for the court!", "What do you think? Then tell the court why.",
  "Type your question or snap a photo — the court will ask what YOU think.", "Try again", "Teach me", "Your new answer", "Tell the court why first! Type it or tap 🎤 to say it.",
  "The clerk is getting a lesson ready", "Lessons aren't ready right now.", "What the court learned about your thinking",
  "Remember:", "Try a chapter check-up →", "BANG!", "NOT QUITE YET", "TELL THE COURT WHY!", "YOUR REASON HOLDS UP!",
  "NO VERDICT YET", "The court couldn't decide this time. Try a check-up to test your thinking.", "THE COURT CAN'T TEST THIS ONE YET",
  "REASON CHECKED!", "The Judge picks a surprise witness", "The court looks closely at your reason", "Right answer! Now the court checks your reason.", "Hmm, let's look at that answer again.", "I think a sneaky idea might be hiding in this reason!", "I can't find anything wrong with this reason.", "I'm on your side: this reason makes sense to me!", "I'm on your side. Let's test it fairly!", "Let's test it! The court calls a surprise witness.", "The court has heard enough!",
  "CASE CLOSED", "You were thinking:", "Reason check", "What you did well", "Think about", "Try this", "Let's look at one together",
  "2 more tries →", "Let's practise it →", "REMEMBER THIS ONE?", "Let's see if the sneaky idea is gone", "YOUR ANSWER",
  "That's my answer →", "Explain or show your reasoning", "The Clerk checks your answer", "The Prosecutor reads your reason",
  "The Defence prepares", "The Judge decides", "The Clerk picks questions for you", "The Judge gets the court ready",
  "The Prosecutor sharpens a pencil", "The Defence cheers you on", "About Why Court"];
const ORIG = new WeakMap();          // text node -> its English text
const WHOLE = new WeakMap();         // [data-i18n] element -> its English markup (translated as one sentence)
// The one-sentence key of a [data-i18n] element: its text, with a line break counted as a space.
const wholeKey = (html) => new DOMParser().parseFromString(html.replace(/<br\s*\/?>/gi, " "), "text/html").body.textContent.replace(/\s+/g, " ").trim();
let UI = {}, uiLang = "English";
const UI_FILES = {};
async function uiFile(l) {
  if (l === "English") return {};
  if (!UI_FILES[l]) UI_FILES[l] = fetch(`/static/i18n/${encodeURIComponent(l)}.json`).then((r) => (r.ok ? r.json() : {})).catch(() => ({}));
  return UI_FILES[l];
}
// "Witness 2" is translated through the template "Witness {n}"; the numbers are put back in order.
function uiText(en) {
  const key = String(en).trim();
  if (uiLang === "English" || !key) return en;
  if (UI[key]) return String(en).replace(key, UI[key]);
  const nums = key.match(/\d+/g);
  const tpl = nums && UI[key.replace(/\d+/g, "{n}")];
  if (tpl) { let i = 0; return String(en).replace(key, tpl.replace(/\{n\}/g, () => nums[i++] ?? "")); }
  return en;
}
function uiTargets() {
  const out = [];
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
    acceptNode: (n) => (/[A-Za-z]/.test(ORIG.get(n) ?? n.nodeValue) && !n.parentElement.closest(NOTR + ", [data-i18n]"))
      ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT });
  while (walk.nextNode()) out.push(walk.currentNode);
  return out;
}
async function applyUI() {
  const l = lang();
  if (l !== uiLang) { UI = await uiFile(l); uiLang = l; }
  document.documentElement.lang = { English: "en", Hindi: "hi", Tamil: "ta", Spanish: "es", French: "fr", Swahili: "sw" }[l] || "en";
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    if (!WHOLE.has(el)) WHOLE.set(el, el.innerHTML);
    const en = WHOLE.get(el), key = wholeKey(en);
    if (l === "English" || !UI[key]) { if (el.innerHTML !== en) el.innerHTML = en; } else if (el.textContent !== UI[key]) el.textContent = UI[key];
  });
  uiTargets().forEach((n) => { if (!ORIG.has(n)) ORIG.set(n, n.nodeValue); const v = uiText(ORIG.get(n)); if (n.nodeValue !== v) n.nodeValue = v; });
  document.querySelectorAll("[placeholder], [aria-label], [title]").forEach((el) => {
    if (el.closest("[data-notr]")) return;
    ["placeholder", "aria-label", "title"].forEach((a) => {
      if (!el.hasAttribute(a)) return;
      const k = "data-en-" + a;
      if (!el.hasAttribute(k)) el.setAttribute(k, el.getAttribute(a));
      const v = uiText(el.getAttribute(k)); if (el.getAttribute(a) !== v) el.setAttribute(a, v);
    });
  });
}
// For scripts/translate_ui.py: every English string this page can show.
window.__uiStrings = () => {
  const s = new Set(UI_EXTRA);
  document.querySelectorAll("[data-i18n]").forEach((el) => s.add(wholeKey(WHOLE.get(el) ?? el.innerHTML)));
  uiTargets().forEach((n) => s.add((ORIG.get(n) ?? n.nodeValue).trim()));
  document.querySelectorAll("[placeholder], [aria-label], [title]").forEach((el) => ["placeholder", "aria-label", "title"].forEach((a) => {
    const v = el.getAttribute("data-en-" + a) ?? el.getAttribute(a); if (v && /[A-Za-z]/.test(v)) s.add(v.trim()); }));
  return [...s].filter((x) => /[A-Za-z]/.test(x));
};
let uiTimer = null;
new MutationObserver(() => { clearTimeout(uiTimer); uiTimer = setTimeout(applyUI, 80); })
  .observe(document.body, { childList: true, subtree: true });
$("#lang").addEventListener("change", async () => { stopSpeaking(); await applyUI(); drawBench(); });
applyUI().then(drawBench);
