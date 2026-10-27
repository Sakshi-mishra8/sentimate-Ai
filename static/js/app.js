/* app.js - dashboard logic: talks to the Flask API and draws everything */
(() => {
  const $ = (id) => document.getElementById(id);
  window.addEventListener("error", (e) => toast("Page error: " + e.message));
  const COL = { pos: "#12936c", neu: "#d9a21b", neg: "#d6405a", ind: "#4338ca" };
  const scoreColor = (s) => (s >= 55 ? COL.pos : s <= 45 ? COL.neg : COL.neu);
  const charts = {};
  const TITLES = { overview: "Overview", analyze: "Analyze a review", inbox: "Inbox", csv: "CSV dashboard", bulk: "Bulk upload",
                   ask: "Ask AI", history: "History" };

  /* ---------- helpers ---------- */
  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;   // textContent keeps user text safe (no XSS)
    return e;
  }
  function toast(msg) {
    const t = $("toast"); t.textContent = msg; t.hidden = false;
    clearTimeout(toast.t); toast.t = setTimeout(() => (t.hidden = true), 2200);
  }
  function setStatus(node, msg, err = false) { node.textContent = msg; node.classList.toggle("error", err); }
  async function api(url, opt) {
    let res;
    try { res = await fetch(url, opt); }
    catch (_) { throw new Error("Cannot reach the server. Make sure the black window (python app.py) is still running, then try again."); }
    if (res.status === 401) { location.href = "/login"; throw new Error("Please log in again."); }
    let data = {};
    try { data = await res.json(); } catch (_) { /* ignore */ }
    if (!res.ok) throw new Error(data.error || "Something went wrong. Try again.");
    return data;
  }
  const post = (url, body) => api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const channel = () => $("channelFilter").value;
  const qs = () => (channel() === "All" ? "" : "?channel=" + encodeURIComponent(channel()));
  let csvList = [], csvId = null;                    // the CSV dashboard looks at ONE uploaded file at a time
  function refreshView() { show(location.hash.slice(1) || "overview"); }
  function chart(key, id, cfg) {
    if (typeof Chart === "undefined") return;
    if (charts[key]) charts[key].destroy();
    charts[key] = new Chart($(id), cfg);
  }
  const plainOpts = { maintainAspectRatio: false, plugins: { legend: { display: false } } };
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const prio = (p) => (p.startsWith("P1") ? "p1" : p.startsWith("P2") ? "p2" : "p3");

  /* ---------- navigation ---------- */
  const loaders = { overview: loadOverview, csv: loadCsv, history: loadHistory, inbox: () => loadInbox(false) };
  function show(view) {
    if (!TITLES[view]) view = "overview";
    document.querySelectorAll(".view").forEach((v) => (v.hidden = v.id !== "v-" + view));
    document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.view === view));
    $("viewTitle").textContent = TITLES[view];
    history.replaceState(null, "", "#" + view);
    $("channelFilter").parentElement.style.visibility = ["overview", "history"].includes(view) ? "visible" : "hidden";
    if (loaders[view]) loaders[view]().catch((e) => toast(e.message));
  }
  document.querySelectorAll("#nav button").forEach((b) => b.addEventListener("click", () => show(b.dataset.view)));
  $("channelFilter").addEventListener("change", refreshView);

  /* ---------- OVERVIEW ---------- */
  function renderDash(p, s, sum, ins) {
    $(p + "sumText").textContent = sum.text; $(p + "sumSource").textContent = sum.source;
    const acts = $(p + "sumActions"); acts.replaceChildren();
    sum.actions.forEach((a) => acts.appendChild(el("li", "", a)));
    $(p + "kpiTotal").textContent = s.total; $(p + "kpiAvg").textContent = s.average + " / 100";
    $(p + "kpiIndex").textContent = (s.index > 0 ? "+" : "") + s.index; $(p + "kpiUrgent").textContent = s.urgent;
    $(p + "kpiEmotion").textContent = s.top_emotion;
    const al = $(p + "alertList"); al.replaceChildren();
    (ins.alerts || []).forEach((a) => al.appendChild(el("li", a.level, a.text)));

    const byDay = s.daily.length >= 3;                    // a CSV has one date, so show each review in order instead
    $(p + "trendCap").textContent = byDay ? "Average score per day" : "Score of each review (last 30, in order)";
    const tLabels = byDay ? s.daily.map((d) => d.day.slice(5)) : s.recent.map((_, i) => i + 1);
    const tData = byDay ? s.daily.map((d) => d.score) : s.recent;
    chart(p + "trend", p + "chTrend", { type: "line", data: { labels: tLabels,
      datasets: [{ data: tData, borderColor: COL.ind, backgroundColor: "rgba(67,56,202,.12)", fill: true, tension: .3, pointRadius: 3 }] },
      options: { ...plainOpts, scales: { y: { min: 0, max: 100 } } } });
    chart(p + "split", p + "chSplit", { type: "doughnut", data: { labels: ["Positive", "Neutral", "Negative"],
      datasets: [{ data: [s.positive, s.neutral, s.negative], backgroundColor: [COL.pos, COL.neu, COL.neg], borderWidth: 2 }] },
      options: { maintainAspectRatio: false, cutout: "62%", plugins: { legend: { position: "bottom" } } } });
    chart(p + "aspects", p + "chAspects", { type: "bar", data: { labels: s.aspects.map((a) => `${a.name} (${a.mentions})`),
      datasets: [{ data: s.aspects.map((a) => a.score), backgroundColor: s.aspects.map((a) => scoreColor(a.score)) }] },
      options: { ...plainOpts, indexAxis: "y", scales: { x: { min: 0, max: 100 } } } });
    const em = Object.entries(s.emotions);
    chart(p + "emotion", p + "chEmotion", { type: "radar", data: { labels: em.map(([k]) => cap(k)),
      datasets: [{ data: em.map(([, v]) => v), borderColor: COL.ind, backgroundColor: "rgba(67,56,202,.2)", pointRadius: 2 }] },
      options: { ...plainOpts, scales: { r: { beginAtZero: true, ticks: { display: false } } } } });
    chart(p + "channel", p + "chChannel", { type: "bar", data: { labels: s.channels.map((c) => c.name),
      datasets: [{ data: s.channels.map((c) => c.score), backgroundColor: s.channels.map((c) => scoreColor(c.score)) }] },
      options: { ...plainOpts, scales: { y: { min: 0, max: 100 } } } });
    const it = Object.entries(s.intents).sort((a, b) => b[1] - a[1]);
    chart(p + "intent", p + "chIntent", { type: "bar", data: { labels: it.map(([k]) => k), datasets: [{ data: it.map(([, v]) => v), backgroundColor: COL.ind }] },
      options: { ...plainOpts, indexAxis: "y" } });
  }

  async function loadOverview() {
    const [s, sum, ins] = await Promise.all([api("/api/stats" + qs()), api("/api/summary" + qs()), api("/api/insights" + qs())]);
    $("ovEmpty").hidden = s.total > 0; $("ovBody").hidden = !s.total;
    if (s.total) renderDash("", s, sum, ins);
  }

  /* ---------- ANALYZE ---------- */
  let lastText = "", activeTone = "Professional", liveTimer = null, seq = 0;

  function renderResult(r) {
    $("anEmpty").hidden = true; $("anResult").hidden = false;
    $("verdict").className = "verdict " + r.label;
    $("vLabel").textContent = r.label;
    $("vMeta").textContent = `Score ${r.score} / 100 - ${r.confidence}% sure`;
    $("needle").style.transform = `rotate(${(r.score / 100) * 180 - 90}deg)`;
    $("warn").hidden = !r.warning; $("warn").textContent = r.warning || "";

    const mc = $("metaChips"); mc.replaceChildren();
    const p = el("span", "tag " + prio(r.priority), r.priority); mc.appendChild(p);
    [r.intent, r.language].forEach((t) => mc.appendChild(el("span", "tag", t)));
    if (r.mixed) mc.appendChild(el("span", "tag mixed", "Mixed review"));
    if (r.sarcasm) mc.appendChild(el("span", "tag mixed", "Sarcasm"));
    $("explain").hidden = !r.explain; $("explain").textContent = r.explain || "";

    $("agree").textContent = r.agreement;
    const ml = $("modelList"); ml.replaceChildren();
    r.models.forEach((m) => {
      const li = document.createElement("li");
      li.append(el("span", "", m.name), el("span", "badge " + m.label, m.label), el("span", "muted small", (m.compound > 0 ? "+" : "") + m.compound));
      ml.appendChild(li);
    });

    $("emoName").textContent = r.emotion.dominant;
    const bars = $("emoBars"); bars.replaceChildren();
    Object.entries(r.emotion.scores).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]).forEach(([n, v]) => {
      const row = el("div", "bar-row"), tr = el("div", "bar-track"), f = el("div", "bar-fill");
      f.style.width = v + "%"; tr.appendChild(f); row.append(el("span", "", n), tr, el("span", "", v + "%")); bars.appendChild(row);
    });
    const rk = $("riskName"); rk.textContent = r.risk.level + " risk"; rk.className = "big risk-" + r.risk.level;
    $("riskDetail").textContent = `Risk points ${r.risk.points}/100. ` + (r.risk.triggers.length ? "Warning words: " + r.risk.triggers.join(", ") + "." : "No warning words.");

    const al = $("aspectList"); al.replaceChildren();
    if (!r.aspects.length) al.appendChild(el("li", "none", "No specific topic found (delivery, price, support, quality, app, packaging)."));
    r.aspects.forEach((a) => { const li = el("li", a.label); li.append(el("span", "", a.name), el("strong", "", a.label)); al.appendChild(li); });
    const wl = $("wordList"); wl.replaceChildren();
    if (!r.words.length) wl.appendChild(el("span", "small muted", "No strong sentiment words found."));
    r.words.forEach((w) => wl.appendChild(el("span", "word " + (w.value > 0 ? "p" : "n"), w.word)));

    $("replyText").textContent = r.reply; $("replySrc").textContent = "template";
    document.querySelectorAll("#toneRow .chip").forEach((c) => c.classList.toggle("on", c.dataset.tone === "Professional"));
    activeTone = "Professional";
  }

  async function analyze(save) {
    const text = $("reviewText").value.trim();
    if (!text) { setStatus($("anStatus"), "Enter some customer feedback first.", true); return null; }
    const my = ++seq;
    const r = await post("/api/analyze", { text, engine: $("engineSel").value, channel: $("channelSel").value, save });
    if (my === seq) { lastText = text; renderResult(r); }
    return r;
  }
  function scheduleLive() {
    clearTimeout(liveTimer);
    if (!$("reviewText").value.trim()) { $("anResult").hidden = true; $("anEmpty").hidden = false; setStatus($("anStatus"), ""); return; }
    liveTimer = setTimeout(async () => {
      try { await analyze(false); setStatus($("anStatus"), 'Live preview. Click "Analyze and save" to add it to the dashboard.'); }
      catch (e) { setStatus($("anStatus"), e.message, true); }
    }, 550);
  }
  $("reviewText").addEventListener("input", scheduleLive);
  $("engineSel").addEventListener("change", scheduleLive);
  document.querySelectorAll("#sampleChips .chip").forEach((c) => c.addEventListener("click", () => { $("reviewText").value = c.dataset.t; scheduleLive(); }));
  $("analyzeBtn").addEventListener("click", async () => {
    const b = $("analyzeBtn"); b.disabled = true; setStatus($("anStatus"), "Analyzing...");
    try { if (await analyze(true)) { setStatus($("anStatus"), "Saved to your dashboard."); toast("Saved"); } }
    catch (e) { setStatus($("anStatus"), e.message, true); } finally { b.disabled = false; }
  });
  document.querySelectorAll("#toneRow .chip").forEach((c) => c.addEventListener("click", async () => {
    if (!lastText) return;
    document.querySelectorAll("#toneRow .chip").forEach((x) => x.classList.toggle("on", x === c));
    activeTone = c.dataset.tone; $("replyText").textContent = "Writing reply...";
    try { const r = await post("/api/reply", { text: lastText, tone: activeTone }); $("replyText").textContent = r.reply; $("replySrc").textContent = r.source; }
    catch (e) { $("replyText").textContent = e.message; }
  }));
  $("copyReply").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText($("replyText").textContent); toast("Reply copied"); } catch (_) { toast("Copy failed. Select the text and copy it."); }
  });

  /* ---------- INBOX (real customer feedback) ---------- */
  let inboxFilter = "open", lastInboxIds = "", feedbackUrl = "";
  function showInboxError(e) {
    $("inboxError").textContent = "Inbox problem: " + (e && e.message ? e.message : e) + " Press Refresh, or log in again.";
    $("inboxError").hidden = false;
  }
  const tones = ["Professional", "Empathetic", "Friendly", "Short"];


  async function changeStatus(id, status) {
    try { await post(`/api/review/${id}/status`, { status }); toast("Marked " + status.toLowerCase()); await loadInbox(false); }
    catch (e) { toast(e.message); }
  }

  function inboxItem(r) {
    const li = el("li", "inb " + r.label + (r.status === "Resolved" ? " done" : ""));
    const head = el("div", "inb-head");
    head.append(el("span", "badge " + r.label, `${r.label} ${r.score}`), el("span", "tag " + prio(r.priority), r.priority),
      el("span", "tag", r.intent), el("span", "tag", r.channel), el("span", "muted small", r.created_at));
    if (r.status !== "New") head.appendChild(el("span", "tag st-" + r.status, r.status));
    li.appendChild(head);
    const who = [r.customer_name, r.customer_contact].filter(Boolean).join(" - ");
    if (who) li.appendChild(el("p", "small muted", "From: " + who));
    li.appendChild(el("p", "inb-text", r.text));

    // reply panel (hidden until "Write reply" is clicked)
    const panel = el("div", "reply-box"); panel.hidden = true;
    const tone = document.createElement("select");
    tone.setAttribute("aria-label", "Reply tone");
    tones.forEach((t) => tone.add(new Option(t, t)));
    const ta = document.createElement("textarea"); ta.rows = 4;
    const gen = async () => {
      ta.value = "Writing reply...";
      try { ta.value = (await post("/api/reply", { text: r.text, tone: tone.value })).reply; } catch (e) { ta.value = e.message; }
    };
    tone.addEventListener("change", gen);
    const row = el("div", "inb-actions");
    const copy = el("button", "btn ghost small", "Copy reply"); copy.type = "button";
    copy.addEventListener("click", async () => { try { await navigator.clipboard.writeText(ta.value); toast("Reply copied"); } catch (_) { toast("Copy failed. Select the text and copy it."); } });
    row.appendChild(copy);
    if ((r.customer_contact || "").includes("@")) {
      const mail = el("button", "btn ghost small", "Send by email"); mail.type = "button";
      mail.addEventListener("click", () => {
        location.href = `mailto:${encodeURIComponent(r.customer_contact)}?subject=${encodeURIComponent("Re: your feedback")}&body=${encodeURIComponent(ta.value)}`;
      });
      row.appendChild(mail);
    }
    panel.append(tone, ta, row);

    const actions = el("div", "inb-actions");
    const write = el("button", "btn ghost small", "Write reply"); write.type = "button";
    write.addEventListener("click", () => { panel.hidden = !panel.hidden; if (!panel.hidden && !ta.value) gen(); });
    actions.appendChild(write);
    const mk = (label, status, cls) => { const b = el("button", "btn " + cls + " small", label); b.type = "button"; b.addEventListener("click", () => changeStatus(r.id, status)); actions.appendChild(b); };
    if (r.status === "New") mk("Mark replied", "Replied", "ghost");
    if (r.status !== "Resolved") mk("Mark resolved", "Resolved", "primary"); else mk("Reopen", "New", "ghost");
    li.append(actions, panel);
    return li;
  }

  const EMPTY_TEXT = {
    open: ["Nothing needs action", "Great: no complaint, question or urgent customer is waiting here. Open 'All reviews' to see every message."],
    done: ["Nothing done yet", "Messages you mark Replied or Resolved move here."],
    all: ["Inbox is empty", "Upload a CSV in Bulk upload and its messages appear here. Your older reviews are still in History and the CSV dashboard."],
  };
  async function loadInbox(auto) {
    try { return await loadInboxInner(auto); } catch (e) { showInboxError(e); throw e; }
  }
  async function loadInboxInner(auto) {
    $("inboxError").hidden = true;
    const d = await api("/api/inbox?filter=" + inboxFilter);
    $("inboxSourceLabel").textContent = d.source ? `${d.source.name} (${d.source.count} messages)` : "nothing uploaded yet";
    $("inboxClear").hidden = !d.source;
    $("inboxCount").textContent = `${d.counts.New} new, ${d.counts.Replied} replied, ${d.counts.Resolved} resolved`;
    $("inboxUpdated").textContent = "Updated " + new Date().toLocaleTimeString();
    document.querySelectorAll("#inboxFilter .chip").forEach((c) => {
      const label = { open: "Needs action", all: "All reviews", done: "Done" }[c.dataset.f];
      c.textContent = `${label} (${d.summary[c.dataset.f]})`;
    });
    const ids = d.rows.map((r) => r.id + r.status).join();
    if (auto) {
      if (ids === lastInboxIds) return;
      if ($("inboxList").querySelector("textarea")) {            // do not erase a reply the user is writing
        const open = [...$("inboxList").querySelectorAll(".reply-box")].some((p) => !p.hidden);
        if (open) { $("inboxNote").hidden = false; return; }
      }
    }
    lastInboxIds = ids; $("inboxNote").hidden = true;
    const list = $("inboxList"); list.replaceChildren();
    $("inboxEmpty").hidden = d.rows.length > 0;
    if (!d.rows.length) {
      const [t, x] = d.source ? EMPTY_TEXT[inboxFilter] : EMPTY_TEXT.all;
      $("inboxEmptyTitle").textContent = t; $("inboxEmptyText").textContent = x;
    }
    d.rows.forEach((r) => list.appendChild(inboxItem(r)));
    return d;
  }
  document.querySelectorAll("#inboxFilter .chip").forEach((c) => c.addEventListener("click", () => {
    inboxFilter = c.dataset.f;
    document.querySelectorAll("#inboxFilter .chip").forEach((x) => x.classList.toggle("on", x === c));
    loadInbox(false).catch(() => {});
  }));
  $("inboxClear").addEventListener("click", async () => {
    try { await post("/api/inbox/clear", {}); lastInboxIds = ""; await loadInbox(false); toast("Inbox cleared. Your reviews are still in History and the CSV dashboard."); } catch (e) { toast(e.message); }
  });
  $("inboxRefresh").addEventListener("click", async () => {
    const b = $("inboxRefresh"); b.disabled = true; b.textContent = "Refreshing...";
    try { const d = await loadInbox(false); toast(d ? `Inbox refreshed: ${d.summary.open} need action, ${d.summary.all} total` : "Inbox refreshed"); }
    catch (e) { toast(e.message); }
    finally { b.disabled = false; b.textContent = "Refresh"; }
  });
  $("copyLink").addEventListener("click", async () => {
    try { await navigator.clipboard.writeText(feedbackUrl); toast("Link copied"); } catch (_) { $("feedbackLink").select(); toast("Press Ctrl+C to copy"); }
  });
  setInterval(() => { if (location.hash === "#inbox") loadInbox(true).catch(() => {}); }, 15000);

  document.querySelectorAll("[data-goto]").forEach((b) => b.addEventListener("click", () => show(b.dataset.goto)));

  /* ---------- BULK ---------- */
  const MAX_BYTES = 2 * 1024 * 1024;
  let file = null;
  function resetPick(msg, isErr) {
    file = null; $("fileName").textContent = "Click here or drop a CSV file"; $("uploadBtn").disabled = true;
    setStatus($("bulkStatus"), msg || "", !!isErr);
  }
  function pick(f) {
    if (!f) return;
    const n = f.name.toLowerCase();
    if (/\.xlsx?$/.test(n)) return resetPick("Excel files cannot be read directly. In Excel use File > Save As > CSV UTF-8, then choose that file.", true);
    if (!n.endsWith(".csv")) return resetPick("Please choose a .csv file.", true);
    if (f.size === 0) return resetPick("That file is empty.", true);
    if (f.size > MAX_BYTES) return resetPick(`That file is ${(f.size / 1048576).toFixed(1)} MB. The limit is 2 MB, so split it into smaller files.`, true);
    file = f; $("fileName").textContent = `${f.name} (${Math.max(1, Math.round(f.size / 1024))} KB)`;
    $("uploadBtn").disabled = false; $("openDash").hidden = true; setStatus($("bulkStatus"), 'File ready. Click "Analyze CSV".');
  }
  const dz = $("dropZone"), fileInput = $("csvFile");
  const openPicker = () => fileInput.click();
  $("pickFile").addEventListener("click", openPicker);
  dz.addEventListener("click", (e) => { if (!e.target.closest("button, a, input")) openPicker(); });   // the WHOLE box is clickable
  dz.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target === dz) { e.preventDefault(); openPicker(); } });
  fileInput.addEventListener("change", (e) => { pick(e.target.files[0]); e.target.value = ""; });
  ["dragenter", "dragover"].forEach((n) => dz.addEventListener(n, () => dz.classList.add("over")));
  ["dragleave", "drop"].forEach((n) => dz.addEventListener(n, () => dz.classList.remove("over")));
  // Always stop the browser from opening a dropped file (it would leave the dashboard). On the Bulk page, a drop anywhere picks the file.
  window.addEventListener("dragover", (e) => e.preventDefault());
  window.addEventListener("drop", (e) => {
    e.preventDefault();
    if (!$("v-bulk").hidden && e.dataTransfer && e.dataTransfer.files.length) pick(e.dataTransfer.files[0]);
  });
  $("uploadBtn").addEventListener("click", async () => {
    if (!file) return;
    const b = $("uploadBtn"), sent = file; b.disabled = true; $("openDash").hidden = true;
    setStatus($("bulkStatus"), "Analyzing all reviews... big files can take up to a minute.");
    const fd = new FormData(); fd.append("file", sent); fd.append("channel", $("bulkChannel").value); fd.append("engine", "ensemble");
    try {
      const d = await api("/api/batch", { method: "POST", body: fd });
      let msg = `Done. ${d.count} reviews analyzed from column "${d.column}".`;
      if (d.truncated) msg += ` Your file has ${d.rows_in_file} reviews, but only the first ${d.limit} are analyzed. Split the file to analyze the rest.`;
      if (d.headerless) msg += " Your file had no header row, so every line was used as a review.";
      setStatus($("bulkStatus"), msg);
      file = null; $("fileName").textContent = `Uploaded: ${d.dataset_name}. Click to choose another file`;   // stops an accidental double upload
      const sum = $("bulkSummary"); sum.replaceChildren();
      [["Average score", d.average], ["Positive", d.counts.Positive], ["Neutral", d.counts.Neutral], ["Negative", d.counts.Negative]].forEach(([n, v]) => {
        const box = el("div"); box.append(el("b", "", String(v)), document.createTextNode(n)); sum.appendChild(box); });
      sum.hidden = false;
      const body = $("bulkRows"); body.replaceChildren();
      d.rows.forEach((r) => {
        const tr = document.createElement("tr"), res = document.createElement("td");
        res.appendChild(el("span", "badge " + r.label, r.label));
        tr.append(el("td", "text", r.text), res, el("td", "", String(r.score)), el("td", "", r.emotion), el("td", "", r.intent), el("td", "", r.risk));
        body.appendChild(tr); });
      $("bulkWrap").hidden = false;
      await loadCsvList(d.dataset_id); $("openDash").hidden = false; toast("Done. The Inbox now shows this file.");
    } catch (e) { setStatus($("bulkStatus"), e.message, true); b.disabled = false; }
  });

  /* ---------- INSIGHTS ---------- */
  function renderIns(p, ins) {
    const f = ins.forecast;
    if (f) {
      $(p + "fcTag").textContent = f.trend;
      $(p + "fcText").textContent = `Linear regression on the last ${f.history.length} reviews. Slope ${f.slope} points per review. Dashed line = next 7 predicted scores.`;
      const n = f.history.length;
      const labels = Array.from({ length: n + 7 }, (_, i) => i + 1);
      const actual = [...f.history, ...Array(7).fill(null)];
      const pred = [...Array(n - 1).fill(null), f.history[n - 1], ...f.next];
      chart(p + "forecast", p + "chForecast", { type: "line", data: { labels, datasets: [
        { label: "Actual", data: actual, borderColor: COL.ind, tension: .3, pointRadius: 2 },
        { label: "Forecast", data: pred, borderColor: COL.neu, borderDash: [6, 5], tension: .3, pointRadius: 3 }] },
        options: { maintainAspectRatio: false, scales: { y: { min: 0, max: 100 } }, plugins: { legend: { position: "bottom" } } } });
    } else {
      $(p + "fcTag").textContent = "needs 8+ reviews"; $(p + "fcText").textContent = "Analyze more reviews to unlock the forecast.";
      if (charts[p + "forecast"]) { charts[p + "forecast"].destroy(); delete charts[p + "forecast"]; }
    }

    const rl = $(p + "riskList"); rl.replaceChildren();
    if (!ins.at_risk.length) rl.appendChild(el("li", "", "No urgent customers. Good."));
    ins.at_risk.forEach((r) => { const li = el("li", "", r.text); li.appendChild(el("div", "m", `${r.channel} - ${r.intent} - risk ${r.points}/100`)); rl.appendChild(li); });

    const tl = $(p + "themeList"); tl.replaceChildren();
    if (!ins.themes.length) tl.appendChild(el("p", "muted", "Need at least 6 negative reviews to find themes."));
    ins.themes.forEach((t) => {
      const d = el("div", "theme"); d.append(el("h4", "", t.name), el("p", "n", `${t.count} reviews`), el("p", "small muted", "Keywords: " + t.keywords.join(", ")));
      t.examples.forEach((x) => d.appendChild(el("blockquote", "", x))); tl.appendChild(d);
    });
    const cloud = (id, words) => {
      const box = $(id); box.replaceChildren(); const max = Math.max(1, ...words.map((w) => w.count));
      words.forEach((w) => { const s = el("span", "", w.word); s.style.fontSize = 14 + 24 * (w.count / max) + "px"; s.title = w.count + " mentions"; box.appendChild(s); });
      if (!words.length) box.appendChild(el("span", "muted small", "Not enough data yet."));
    };
    cloud(p + "posCloud", ins.positive_words); cloud(p + "negCloud", ins.negative_words);

  }

  function renderModelCard(st) {
    const m = st.model || {}, mc = $("modelCard"); mc.replaceChildren();
    [[(m.test_accuracy ?? "-") + "%", "Test accuracy"], [m.samples ?? "-", "Training samples"], [m.algorithm || "-", "Algorithm"],
     [st.transformer ? "On" : "Off", "DistilBERT"]].forEach(([b, s]) => { const d = el("div"); d.append(el("b", "", String(b)), el("span", "", s)); mc.appendChild(d); });
    $("modelCard").after($("modelNote") || Object.assign(el("p", "note", "The starter model learns from a generated dataset, so its accuracy number is optimistic. Train it on real reviews with: python train_model.py your_reviews.csv (columns: text,label)."), { id: "modelNote" }));
  }

  /* ---------- CSV DASHBOARD (only the selected uploaded file) ---------- */
  async function loadCsvList(selectId) {
    csvList = await api("/api/datasets?kind=csv");
    const ids = csvList.map((d) => d.id), stored = Number(localStorage.getItem("csv")) || null;
    csvId = ids.includes(selectId) ? selectId : ids.includes(stored) ? stored : ids[0] || null;
    if (csvId) localStorage.setItem("csv", csvId); else localStorage.removeItem("csv");
    const sel = $("csvSelect"); sel.replaceChildren();
    csvList.forEach((d) => sel.add(new Option(`${d.name} (${d.count} reviews, ${d.created_at.slice(0, 10)})`, d.id)));
    if (csvId) sel.value = csvId;
  }
  async function loadCsv() {
    await loadCsvList(csvId);
    $("csvEmpty").hidden = csvList.length > 0; $("csvBody").hidden = !csvList.length;
    if (!csvId) return;
    const q = "?ds=" + csvId;
    const [s, sum, ins, st] = await Promise.all([api("/api/stats" + q), api("/api/summary" + q), api("/api/insights" + q), api("/api/status")]);
    $("c_reportLink").href = "/report?ds=" + csvId;
    $("csvBody").hidden = !s.total; if (!s.total) return;
    renderDash("c_", s, sum, ins);
    renderIns("c_", ins);
    renderModelCard(st);
  }
  $("csvSelect").addEventListener("change", () => { csvId = Number($("csvSelect").value) || null; if (csvId) localStorage.setItem("csv", csvId); loadCsv().catch((e) => toast(e.message)); });
  $("csvDelete").addEventListener("click", async () => {
    const d = csvList.find((x) => x.id === csvId); if (!d) return;
    if (!confirm(`Delete "${d.name}" and its ${d.count} reviews? They will also disappear from Overview and Inbox.`)) return;
    try { await post(`/api/dataset/${csvId}/delete`, {}); csvId = null; toast("File data deleted"); await loadCsv(); } catch (e) { toast(e.message); }
  });

  /* ---------- ASK AI ---------- */
  function addMsg(who, text, src) {
    const m = el("div", "msg " + who); m.appendChild(el("p", "", text));
    if (src) m.appendChild(el("small", "", "answered by " + src));
    $("chatLog").appendChild(m); $("chatLog").scrollTop = $("chatLog").scrollHeight; return m;
  }
  let lastQuestion = "";
  async function ask(q) {
    const prevQ = lastQuestion; lastQuestion = q;
    addMsg("me", q); const wait = addMsg("bot", "Thinking...");
    try { const r = await post("/api/chat", { question: q, ds: csvId || undefined, prev: prevQ }); wait.remove(); addMsg("bot", r.answer, r.source); }
    catch (e) { wait.remove(); addMsg("bot", e.message); }
  }
  $("chatForm").addEventListener("submit", (e) => { e.preventDefault(); const q = $("chatInput").value.trim(); if (!q) return; $("chatInput").value = ""; ask(q); });
  document.querySelectorAll("#chatChips .chip").forEach((c) => c.addEventListener("click", () => ask(c.textContent)));

  /* ---------- HISTORY ---------- */
  async function loadHistory() {
    const rows = await api("/api/history" + qs());
    const body = $("histRows"); body.replaceChildren(); $("histEmpty").hidden = rows.length > 0;
    $("histNote").textContent = rows.length ? `Showing the latest ${rows.length} saved reviews from every source.` : "";
    rows.forEach((r) => {
      const tr = document.createElement("tr"), res = document.createElement("td");
      res.appendChild(el("span", "badge " + r.label, r.label));
      tr.append(el("td", "", r.created_at), el("td", "", r.source || r.channel), el("td", "text", r.text.length > 130 ? r.text.slice(0, 130) + "..." : r.text),
        res, el("td", "", String(r.score)), el("td", "", r.emotion), el("td", "", r.intent), el("td", prio(r.priority), r.priority));
      body.appendChild(tr);
    });
  }
  $("clearBtn").addEventListener("click", async () => {
    if (!confirm("Delete all your saved reviews? This cannot be undone.")) return;
    try { await post("/api/clear", {}); await loadCsvList(); refreshView(); toast("All data deleted"); } catch (e) { toast(e.message); }
  });

  /* ---------- start ---------- */
  api("/api/status").then((st) => {
    feedbackUrl = location.origin + st.feedback_path;
    $("feedbackLink").value = feedbackUrl; $("openLink").href = st.feedback_path;
    const row = $("statusChips");
    [["DistilBERT " + (st.transformer ? "on" : "off")]].forEach(([t]) => row.appendChild(el("span", "tag", t)));
  }).catch(() => {});
  $("openDash").addEventListener("click", () => show("csv"));
  loadCsvList().then(refreshView).catch((e) => { toast(e.message); refreshView(); });
})();
