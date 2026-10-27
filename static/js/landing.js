/* landing page: real try-it box. It sends your text to the server, the AI analyzes it, nothing is saved. */
(() => {
  const $ = (id) => document.getElementById(id);
  function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

  $("tryBtn").addEventListener("click", async () => {
    const text = $("tryText").value.trim();
    const st = $("tryStatus"), btn = $("tryBtn");
    st.className = "status";
    if (!text) { st.textContent = "Paste a customer review first."; st.classList.add("error"); return; }
    btn.disabled = true; st.textContent = "Analyzing...";
    try {
      const res = await fetch("/api/try", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const r = await res.json();
      if (!res.ok) throw new Error(r.error || "Something went wrong.");
      st.textContent = "";
      $("tryLabel").className = "badge " + r.label; $("tryLabel").textContent = r.label;
      $("tryScore").textContent = r.score + " / 100";
      const chips = $("tryChips"); chips.replaceChildren();
      [r.emotion.dominant, r.intent, r.priority, r.language].forEach((t) => chips.appendChild(el("span", "tag", t)));
      if (r.mixed) chips.appendChild(el("span", "tag mixed", "Mixed review"));
      $("tryExplain").hidden = !r.explain; $("tryExplain").textContent = r.explain || "";
      const list = $("tryAspects"); list.replaceChildren();
      r.aspects.forEach((a) => { const li = el("li", a.label); li.append(el("span", "", a.name), el("strong", "", a.label)); list.appendChild(li); });
      $("tryReply").textContent = r.reply;
      $("tryOut").hidden = false;
    } catch (e) { st.textContent = e.message; st.classList.add("error"); }
    finally { btn.disabled = false; }
  });
})();
