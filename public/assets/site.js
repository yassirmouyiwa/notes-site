// Notes — petites améliorations ; le site reste lisible sans JavaScript.

// Bouton « Copier » sur chaque bloc de code
document.querySelectorAll(".codeblock").forEach((block) => {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "copy";
  button.textContent = "Copier";
  button.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(block.querySelector("code").innerText);
      button.textContent = "Copié ✓";
    } catch {
      button.textContent = "Échec";
    }
    setTimeout(() => (button.textContent = "Copier"), 1500);
  });
  block.appendChild(button);
});

// Accueil : filtre instantané (titre, résumé, tags), sans tenir compte des accents
const search = document.getElementById("search");
if (search) {
  const items = [...document.querySelectorAll(".note-list li")];
  const count = document.getElementById("count");
  const empty = document.getElementById("empty");
  const total = Number(count.dataset.total);
  const normalize = (s) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

  const apply = () => {
    const terms = normalize(search.value).split(/\s+/).filter(Boolean);
    let shown = 0;
    for (const item of items) {
      const match = terms.every((t) => item.dataset.search.includes(t));
      item.hidden = !match;
      if (match) shown++;
    }
    const label = count.dataset.label || "note";
    count.textContent = terms.length
      ? `${shown} / ${total}`
      : `${total} ${label}${total > 1 ? "s" : ""}`;
    empty.hidden = shown > 0;
  };

  const q = new URLSearchParams(location.search).get("q");
  if (q) search.value = q;
  search.addEventListener("input", apply);
  apply();
}

// Note : surligner dans le sommaire la section en cours de lecture
const tocLinks = new Map(
  [...document.querySelectorAll(".toc-side a")].map((a) => [decodeURIComponent(a.hash.slice(1)), a])
);
if (tocLinks.size) {
  const headings = [...tocLinks.keys()].map((id) => document.getElementById(id)).filter(Boolean);
  let pending = false;
  const update = () => {
    pending = false;
    let current = headings[0];
    for (const h of headings) {
      if (h.getBoundingClientRect().top < 120) current = h;
      else break;
    }
    tocLinks.forEach((a) => a.classList.remove("active"));
    tocLinks.get(current.id)?.classList.add("active");
  };
  addEventListener("scroll", () => {
    if (!pending) {
      pending = true;
      requestAnimationFrame(update);
    }
  }, { passive: true });
  update();
}
