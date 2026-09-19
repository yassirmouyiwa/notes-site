#!/usr/bin/env python3
"""Générateur du site de notes :  notes/**/*.md  ->  dist/  (HTML statique).

Flux de publication : déposer un .md dans notes/, commit, push.
Cloudflare Pages détecte le push, lance ce script et publie dist/.

Usage :
  python3 build.py            construit dist/
  python3 build.py --serve    construit puis sert le site sur http://localhost:8000

Une note est un simple fichier Markdown. Le titre est lu dans le premier « # Titre »,
le résumé dans le premier paragraphe (ou la première citation). Un en-tête optionnel
permet de forcer ces valeurs :

  ---
  title: Mon titre
  date: 2026-09-19
  tags: web, appsec
  description: Une phrase de résumé.
  draft: true          # la note n'est pas publiée
  ---

Les fichiers dont le nom commence par « _ » sont ignorés. Les autres fichiers de notes/
(images…) sont copiés tels quels, donc ![](img/capture.png) fonctionne.
"""

import html
import re
import shutil
import subprocess
import sys
import unicodedata
from datetime import date
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import quote

from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.tasklists import tasklists_plugin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import get_lexer_by_name
from pygments.util import ClassNotFound

ROOT = Path(__file__).resolve().parent
NOTES = ROOT / "notes"
PUBLIC = ROOT / "public"      # copié tel quel à la racine du site (css, js, _headers…)
DIST = ROOT / "dist"

SITE_TITLE = "Notes"
SITE_TAGLINE = "Carnet technique — sécurité offensive, AppSec, systèmes embarqués."
AUTHOR = "Yassir Mouyiwa"

MOIS = ["janv.", "févr.", "mars", "avr.", "mai", "juin",
        "juil.", "août", "sept.", "oct.", "nov.", "déc."]


# ---------------------------------------------------------------------------
# Markdown -> HTML
# ---------------------------------------------------------------------------

CODE_FORMATTER = HtmlFormatter(nowrap=True)


def render_fence(self, tokens, idx, options, env):
    """Bloc de code : coloration Pygments + étiquette du langage."""
    token = tokens[idx]
    lang = token.info.strip().split(maxsplit=1)[0].lower() if token.info.strip() else ""
    body = None
    if lang:
        try:
            lexer = get_lexer_by_name(lang, startinline=True)  # startinline : PHP sans « <?php »
            body = highlight(token.content, lexer, CODE_FORMATTER)
        except ClassNotFound:
            pass
    if body is None:
        body = html.escape(token.content)
    label = f'<span class="lang">{html.escape(lang)}</span>' if lang else ""
    return f'<div class="codeblock">{label}<pre><code>{body}</code></pre></div>\n'


def render_heading_close(self, tokens, idx, options, env):
    token = tokens[idx]
    anchor = token.meta.get("anchor")
    link = f'<a class="anchor" href="#{anchor}" aria-hidden="true" tabindex="-1">#</a>' if anchor else ""
    return f"{link}</{token.tag}>\n"


def render_table_open(self, tokens, idx, options, env):
    return '<div class="table-wrap"><table>\n'


def render_table_close(self, tokens, idx, options, env):
    return "</table></div>\n"


# html=False : le HTML brut d'une note est affiché comme du texte, jamais exécuté.
# Indispensable pour des notes de sécu pleines de payloads <script>…
MD = (
    MarkdownIt("commonmark", {"html": False, "typographer": False})
    .enable(["table", "strikethrough"])
    .use(footnote_plugin)
    .use(tasklists_plugin)
)
MD.add_render_rule("fence", render_fence)
MD.add_render_rule("heading_close", render_heading_close)
MD.add_render_rule("table_open", render_table_open)
MD.add_render_rule("table_close", render_table_close)


def slugify(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "section"


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFD", text) if not unicodedata.combining(c))


def plain_text(inline):
    parts = []
    for child in inline.children or []:
        if child.type in ("text", "code_inline"):
            parts.append(child.content)
        elif child.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts).strip()


def rewrite_md_link(href):
    """[autre note](autre.md#section)  ->  autre#section"""
    if re.match(r"^[a-z][a-z0-9+.-]*:", href, re.I) or href.startswith("#"):
        return href
    path, sep, frag = href.partition("#")
    if path.endswith(".md"):
        head, _, stem = path[:-3].rpartition("/")
        path = (head + "/" if head else "") + slugify(stem)
    return path + sep + frag


def render_markdown(body):
    """Retourne (html, sommaire, résumé) pour le corps d'une note."""
    tokens = MD.parse(body, {})
    toc, used, summary = [], set(), ""

    for i, token in enumerate(tokens):
        if token.type == "heading_open" and token.tag in ("h2", "h3", "h4"):
            text = plain_text(tokens[i + 1])
            anchor = base = slugify(text)
            n = 2
            while anchor in used:
                anchor, n = f"{base}-{n}", n + 1
            used.add(anchor)
            token.attrSet("id", anchor)
            tokens[i + 2].meta["anchor"] = anchor          # heading_close
            if token.tag in ("h2", "h3"):
                toc.append((int(token.tag[1]), text, anchor))
        elif token.type == "paragraph_open" and not summary:
            summary = plain_text(tokens[i + 1])
        elif token.type == "inline":
            for child in token.children or []:
                if child.type == "link_open":
                    child.attrSet("href", rewrite_md_link(child.attrGet("href") or ""))
                elif child.type == "image":
                    child.attrSet("loading", "lazy")

    return MD.renderer.render(tokens, MD.options, {}), toc, summary


# ---------------------------------------------------------------------------
# Lecture des notes
# ---------------------------------------------------------------------------

def split_front_matter(text):
    meta = {}
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            for line in text[4:end].splitlines():
                key, sep, value = line.partition(":")
                if sep and not line.lstrip().startswith("#"):
                    meta[key.strip().lower()] = value.split(" #")[0].strip().strip("\"'")
            text = text[end + 4:].lstrip("\n")
    return meta, text


def git_date(path):
    """Date du dernier commit qui a touché le fichier (None hors dépôt git)."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path)],
                             cwd=ROOT, capture_output=True, text=True, timeout=10)
        return date.fromisoformat(out.stdout.strip()) if out.stdout.strip() else None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def truncate(text, limit=220):
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:—-") + "…"


def load_note(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta, body = split_front_matter(text)
    if meta.get("draft", "").lower() in ("true", "yes", "oui", "1"):
        return None

    # Le premier « # Titre » devient le titre de la page (et sort du corps)
    title = meta.get("title", "")
    lines = body.split("\n")
    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None and (m := re.match(r"^#\s+(.+?)\s*#*\s*$", lines[first])):
        title = title or m.group(1)
        body = "\n".join(lines[first + 1:])
    title = title or path.stem.replace("-", " ").replace("_", " ").capitalize()

    content, toc, summary = render_markdown(body)

    try:
        when = date.fromisoformat(meta["date"]) if meta.get("date") else None
    except ValueError:
        sys.exit(f"{path.relative_to(ROOT)} : date invalide « {meta['date']} » (attendu AAAA-MM-JJ)")
    when = when or git_date(path) or date.fromtimestamp(path.stat().st_mtime)

    tags = [t.strip().strip("\"'") for t in meta.get("tags", "").strip("[]").split(",") if t.strip()]
    rel = path.relative_to(NOTES)
    url = "/" + (rel.parent.as_posix() + "/" if rel.parent != Path(".") else "") + slugify(path.stem)
    words = len(re.findall(r"\w+", body))

    return {
        "source": path,
        "url": url,
        "title": title,
        "title_html": MD.renderInline(title),
        "description": truncate(meta.get("description") or summary),
        "date": when,
        "tags": tags,
        "minutes": max(1, round(words / 200)),
        "content": content,
        "toc": toc,
    }


# ---------------------------------------------------------------------------
# Gabarits
# ---------------------------------------------------------------------------

def fmt_date(d):
    return f"{d.day} {MOIS[d.month - 1]} {d.year}"


def esc(text):
    return html.escape(text, quote=True)


def page(title, description, body, body_class=""):
    full_title = SITE_TITLE if title == SITE_TITLE else f"{title} · {SITE_TITLE}"
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="author" content="{esc(AUTHOR)}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta name="color-scheme" content="light dark">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css">
<script src="/assets/site.js" defer></script>
</head>
<body class="{body_class}">
<a class="skip" href="#contenu">Aller au contenu</a>
<header class="site-header">
  <div class="wrap">
    <a class="brand" href="/"><span class="prompt">~/</span>notes</a>
  </div>
</header>
{body}
<footer class="site-footer">
  <div class="wrap">© {date.today().year} {esc(AUTHOR)} · écrit en Markdown, publié par Cloudflare Pages</div>
</footer>
</body>
</html>
"""


def tags_html(tags):
    return "".join(f'<a class="tag" href="/?q={esc(quote(t))}">#{esc(t)}</a>' for t in tags)


def meta_line(note):
    parts = [f'<time datetime="{note["date"].isoformat()}">{fmt_date(note["date"])}</time>',
             f'{note["minutes"]} min de lecture']
    return " <span aria-hidden=\"true\">·</span> ".join(parts)


def toc_html(toc):
    items = "".join(f'<li class="lvl{lvl}"><a href="#{anchor}">{esc(text)}</a></li>'
                    for lvl, text, anchor in toc)
    return f"<ol>{items}</ol>"


def note_page(note):
    tags = f'<div class="tags">{tags_html(note["tags"])}</div>' if note["tags"] else ""
    toc_side = toc_mobile = ""
    if len(note["toc"]) >= 2:
        toc_side = f'<aside class="toc-side"><nav aria-label="Sommaire"><p class="toc-title">Sommaire</p>{toc_html(note["toc"])}</nav></aside>'
        toc_mobile = f'<details class="toc-mobile"><summary>Sommaire</summary>{toc_html(note["toc"])}</details>'
    body = f"""<main id="contenu" class="wrap note-layout">
  <article class="note">
    <header class="note-head">
      <a class="back" href="/">← Toutes les notes</a>
      <h1>{note["title_html"]}</h1>
      <p class="meta">{meta_line(note)}</p>
      {tags}
    </header>
    {toc_mobile}
    <div class="prose">
{note["content"]}
    </div>
  </article>
  {toc_side}
</main>"""
    return page(note["title"], note["description"], body, "is-note")


def index_page(notes):
    items = []
    for n in notes:
        search = strip_accents(" ".join([n["title"], n["description"], *n["tags"]])).lower()
        tags = f'<div class="tags">{tags_html(n["tags"])}</div>' if n["tags"] else ""
        items.append(f"""<li data-search="{esc(search)}">
  <a class="card" href="{esc(n["url"])}">
    <h2>{n["title_html"]}</h2>
    <p>{esc(n["description"])}</p>
    <p class="meta">{meta_line(n)}</p>
  </a>
  {tags}
</li>""")
    count = f'{len(notes)} note{"s" if len(notes) > 1 else ""}'
    body = f"""<main id="contenu" class="wrap home">
  <section class="hero">
    <h1>{esc(SITE_TITLE)}</h1>
    <p>{esc(SITE_TAGLINE)}</p>
  </section>
  <div class="toolbar">
    <label class="search">
      <span class="visually-hidden">Rechercher</span>
      <input id="search" type="search" placeholder="Rechercher une note…" autocomplete="off">
    </label>
    <span id="count" class="count" data-total="{len(notes)}">{count}</span>
  </div>
  <ol class="note-list">
{"".join(items)}
  </ol>
  <p id="empty" class="empty" hidden>Aucune note ne correspond.</p>
</main>"""
    return page(SITE_TITLE, SITE_TAGLINE, body, "is-home")


def not_found_page():
    body = """<main id="contenu" class="wrap home">
  <section class="hero">
    <h1>404</h1>
    <p>Cette page n'existe pas (ou plus). <a href="/">Retour aux notes</a>.</p>
  </section>
</main>"""
    return page("Page introuvable", "Page introuvable", body)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

def build():
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(PUBLIC, DIST)

    notes, seen = [], {}
    for path in sorted(NOTES.rglob("*")):
        rel = path.relative_to(NOTES)
        if path.is_dir() or any(p.startswith(".") for p in rel.parts):
            continue
        if path.suffix.lower() != ".md":
            dest = DIST / rel                       # image, pdf… copiée telle quelle
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            continue
        if path.name.startswith("_"):
            continue
        note = load_note(path)
        if note is None:
            continue
        if note["url"] in seen:
            sys.exit(f"Deux notes donnent la même adresse {note['url']} : {seen[note['url']]} et {rel}")
        seen[note["url"]] = rel
        notes.append(note)

    notes.sort(key=lambda n: (n["date"], n["title"].lower()), reverse=True)
    for note in notes:
        out = DIST / (note["url"].lstrip("/") + ".html")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(note_page(note), encoding="utf-8")

    (DIST / "index.html").write_text(index_page(notes), encoding="utf-8")
    (DIST / "404.html").write_text(not_found_page(), encoding="utf-8")

    print(f"{len(notes)} note(s) -> {DIST.relative_to(ROOT)}/")
    for note in notes:
        print(f"  {note['url']:<40} {note['title']}")


class PrettyURLHandler(SimpleHTTPRequestHandler):
    """Comme Cloudflare Pages : /ma-note sert ma-note.html, et 404.html si rien."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def translate_path(self, path):
        fs_path = super().translate_path(path)
        if not Path(fs_path).exists() and Path(fs_path + ".html").exists():
            return fs_path + ".html"
        return fs_path

    def send_error(self, code, message=None, explain=None):
        if code != 404:
            return super().send_error(code, message, explain)
        content = (DIST / "404.html").read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


if __name__ == "__main__":
    build()
    if "--serve" in sys.argv:
        server = ThreadingHTTPServer(("127.0.0.1", 8000), PrettyURLHandler)
        print("Aperçu sur http://localhost:8000  (Ctrl+C pour arrêter)")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
