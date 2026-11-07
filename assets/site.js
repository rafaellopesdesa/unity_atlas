"use strict";
document.documentElement.classList.add("js");
const toggle = document.querySelector(".menu-toggle");
const sidebar = document.querySelector(".sidebar");
toggle.hidden = false;
toggle.addEventListener("click", () => {
  const open = sidebar.classList.toggle("open");
  toggle.setAttribute("aria-expanded", String(open));
});
document.addEventListener("keydown", event => {
  if (event.key === "Escape" && sidebar.classList.contains("open")) {
    sidebar.classList.remove("open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.focus();
  }
});

document.querySelectorAll("article pre").forEach(pre => {
  const button = document.createElement("button");
  button.className = "copy";
  button.type = "button";
  button.textContent = "Copy";
  button.setAttribute("aria-label", "Copy code block");
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(pre.querySelector("code").textContent);
      button.textContent = "Copied";
    } catch {
      const selection = window.getSelection();
      const range = document.createRange();
      range.selectNodeContents(pre.querySelector("code"));
      selection.removeAllRanges();
      selection.addRange(range);
      button.textContent = "Press Ctrl/Cmd+C";
    }
    setTimeout(() => { button.textContent = "Copy"; }, 2200);
  });
  pre.append(button);
});
document.querySelectorAll("article table").forEach(table => {
  const wrapper = document.createElement("div");
  wrapper.className = "table-scroll";
  wrapper.tabIndex = 0;
  wrapper.setAttribute("role", "region");
  wrapper.setAttribute("aria-label", "Scrollable reference table");
  table.before(wrapper);
  wrapper.append(table);
});

const search = document.querySelector(".search");
const input = document.querySelector("#search-input");
const results = document.querySelector("#search-results");
const status = document.querySelector("#search-status");
if (window.UNITY_DOCS_INDEX) search.hidden = false;
input.addEventListener("input", () => {
  const query = input.value.toLowerCase().trim();
  results.replaceChildren();
  results.hidden = !query;
  if (!query) { status.textContent = ""; return; }
  const words = query.split(/\s+/);
  const matches = window.UNITY_DOCS_INDEX.filter(entry => words.every(word =>
    (entry.title + " " + entry.text).toLowerCase().includes(word)
  )).sort((a, b) => Number(b.title.toLowerCase().includes(query)) - Number(a.title.toLowerCase().includes(query)));
  status.textContent = matches.length ? `${Math.min(matches.length, 8)} results` : "No results. Try a shorter search.";
  matches.slice(0, 8).forEach(entry => {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = document.body.dataset.root + entry.url;
    a.textContent = entry.title;
    a.addEventListener("click", () => {
      sidebar.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    });
    li.append(a); results.append(li);
  });
});

if ("IntersectionObserver" in window) {
  const observer = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      document.querySelectorAll(".toc nav a").forEach(a => {
        a.classList.toggle("active", a.hash === "#" + entry.target.id);
      });
    });
  }, { rootMargin: "-90px 0px -65% 0px" });
  document.querySelectorAll("article h2[id]").forEach(h => observer.observe(h));
}
