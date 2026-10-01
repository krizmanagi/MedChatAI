(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const messagesEl = $("messages");
  const form = $("composer");
  const input = $("input");
  const sendBtn = $("send");
  const counter = $("counter");
  const termList = $("term-list");
  const termCount = $("term-count");
  const MAX_CHARS = 2000;

  /** Conversation history sent to the backend for context. */
  let history = [];
  let busy = false;

  // ------------------------------------------------------------ utilities
  const escapeHtml = (s) =>
    s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /** Minimal, safe markdown: escapes HTML first, then **bold**, *italic*, bullet lists, paragraphs. */
  function renderMarkdown(text) {
    const inline = (s) =>
      escapeHtml(s)
        .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[^*])\*(?!\s)(.+?)\*(?!\*)/g, "$1<em>$2</em>");
    const blocks = text.trim().split(/\n{2,}/);
    return blocks
      .map((block) => {
        const lines = block.split("\n");
        if (lines.every((l) => /^\s*([-*•]|\d+\.)\s+/.test(l))) {
          return "<ul>" + lines.map((l) => `<li>${inline(l.replace(/^\s*([-*•]|\d+\.)\s+/, ""))}</li>`).join("") + "</ul>";
        }
        // mixed block: lead-in line followed by bullets
        const firstBullet = lines.findIndex((l) => /^\s*[-*•]\s+/.test(l));
        if (firstBullet > 0 && lines.slice(firstBullet).every((l) => /^\s*[-*•]\s+/.test(l))) {
          const head = lines.slice(0, firstBullet).map(inline).join("<br>");
          const items = lines.slice(firstBullet).map((l) => `<li>${inline(l.replace(/^\s*[-*•]\s+/, ""))}</li>`).join("");
          return `<p>${head}</p><ul>${items}</ul>`;
        }
        return `<p>${lines.map(inline).join("<br>")}</p>`;
      })
      .join("");
  }

  /** Wrap recognized term spans in <mark> elements (spans come from the backend). */
  function highlightTerms(text, terms) {
    const spans = [...terms].sort((a, b) => a.start - b.start);
    let out = "";
    let cursor = 0;
    for (const t of spans) {
      if (t.start < cursor || t.end > text.length) continue;
      out += escapeHtml(text.slice(cursor, t.start));
      const title = `${t.term} (${t.category})${t.negated ? " · negated" : ""}: ${t.definition}`;
      out += `<mark class="${t.negated ? "neg" : ""}" title="${escapeHtml(title)}">${escapeHtml(text.slice(t.start, t.end))}</mark>`;
      cursor = t.end;
    }
    return out + escapeHtml(text.slice(cursor));
  }

  function scrollToBottom() {
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function addMessage(role, html, meta) {
    $("welcome")?.remove();
    const wrap = document.createElement("div");
    wrap.className = `msg ${role}`;
    wrap.innerHTML = `<div class="bubble">${html}</div>${meta ? `<div class="meta">${escapeHtml(meta)}</div>` : ""}`;
    messagesEl.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  function addAlert(kind, html) {
    const el = document.createElement("div");
    el.className = `alert ${kind}`;
    el.setAttribute("role", kind === "emergency" ? "alert" : "status");
    el.innerHTML = html;
    messagesEl.appendChild(el);
    scrollToBottom();
    return el;
  }

  function showTyping() {
    const wrap = document.createElement("div");
    wrap.className = "msg assistant";
    wrap.innerHTML = `<div class="bubble typing" aria-label="MedChat is thinking"><span></span><span></span><span></span></div>`;
    messagesEl.appendChild(wrap);
    scrollToBottom();
    return wrap;
  }

  // ------------------------------------------------------------ terms panel
  function renderTerms(terms) {
    const unique = [];
    const seen = new Set();
    for (const t of terms) {
      const key = `${t.concept_id}|${t.negated}`;
      if (!seen.has(key)) { seen.add(key); unique.push(t); }
    }
    termCount.textContent = unique.length;
    if (!unique.length) {
      termList.innerHTML = `<p class="empty">No medical terms recognized in that question.</p>`;
      return;
    }
    termList.innerHTML = unique
      .map((t) => `
        <div class="term" style="--cat: var(--c-${escapeHtml(t.category)})">
          <div class="term-top">
            <span class="term-name">${escapeHtml(t.term)}</span>
            <span class="term-cat">${escapeHtml(t.category)}</span>
          </div>
          <p class="term-def">${escapeHtml(t.definition || "")}</p>
          <div class="chips">
            <span class="chip">“${escapeHtml(t.text)}”</span>
            <span class="chip">${escapeHtml(t.match_type)}</span>
            ${t.negated ? `<span class="chip neg">negated</span>` : ""}
          </div>
        </div>`)
      .join("");
  }

  // ------------------------------------------------------------ status
  async function loadStatus() {
    const box = $("status");
    const label = $("status-text");
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error();
      const data = await res.json();
      if (data.provider === "mock") {
        box.className = "status demo";
        label.textContent = "Demo mode · no GPT-4 key";
        box.title = "Set Azure OpenAI or OpenAI credentials to enable GPT-4 responses.";
      } else {
        box.className = "status live";
        label.textContent = `${data.provider === "azure" ? "Azure OpenAI" : "OpenAI"} · ${data.model}`;
      }
    } catch {
      box.className = "status down";
      label.textContent = "Server unavailable";
    }
  }

  // ------------------------------------------------------------ send
  async function send(raw) {
    const text = (raw || "").trim();
    if (busy || !text) return;
    busy = true;
    updateComposer();

    const userEl = addMessage("user", escapeHtml(text));
    input.value = "";
    autoresize();
    updateComposer();
    const typing = showTyping();

    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text, history }),
      });
      const data = await res.json().catch(() => ({}));
      typing.remove();

      if (!res.ok) {
        const detail = Array.isArray(data.detail) ? data.detail.map((d) => d.msg).join("; ") : data.detail;
        addAlert("error", escapeHtml(detail || `Request failed (${res.status}). Please try again.`));
        return;
      }

      userEl.querySelector(".bubble").innerHTML = highlightTerms(text, data.terms);
      renderTerms(data.terms);

      if (data.safety.emergency && !data.safety.crisis) {
        addAlert("emergency", `<strong>Possible emergency:</strong> ${escapeHtml(data.safety.emergency_reasons.join(", "))}. If this is happening now, call 911 or your local emergency number.`);
      }
      for (const n of data.notices || []) addAlert("notice", escapeHtml(n));

      const meta = data.provider === "safety"
        ? "Safety response"
        : `${data.provider === "mock" ? "Demo mode" : data.model} · ${data.latency_ms} ms`;
      addMessage("assistant", renderMarkdown(data.reply), meta);

      history.push({ role: "user", content: text }, { role: "assistant", content: data.reply });
      history = history.slice(-12);
    } catch (err) {
      typing.remove();
      addAlert("error", "Couldn't reach the MedChat server. Check your connection and try again.");
    } finally {
      busy = false;
      updateComposer();
      input.focus();
    }
  }

  // ------------------------------------------------------------ composer
  function autoresize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 160) + "px";
  }
  function updateComposer() {
    const len = input.value.length;
    counter.textContent = `${len} / ${MAX_CHARS}`;
    sendBtn.disabled = busy || !input.value.trim();
    sendBtn.textContent = busy ? "Sending…" : "Send";
  }

  input.addEventListener("input", () => { autoresize(); updateComposer(); });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
  });
  form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
  $("suggestions")?.addEventListener("click", (e) => {
    if (e.target.tagName === "BUTTON") send(e.target.textContent);
  });
  $("clear").addEventListener("click", () => {
    history = [];
    messagesEl.innerHTML = "";
    renderTerms([]);
    termCount.textContent = "0";
    termList.innerHTML = `<p class="empty">Terms will appear here after you ask a question.</p>`;
    input.focus();
  });

  loadStatus();
  updateComposer();
})();
