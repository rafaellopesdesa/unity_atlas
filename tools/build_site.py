#!/usr/bin/env python3
"""Render Markdown with Pandoc into tracked, build-free GitHub Pages output."""
import html
import json
import posixpath
import subprocess
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Sections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.headings = []
        self.heading = None
        self.text = []
        self.all_text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h2", "h3"):
            self.heading = (tag, dict(attrs).get("id", ""))
            self.text = []

    def handle_data(self, data):
        self.all_text.append(data)
        if self.heading:
            self.text.append(data)

    def handle_endtag(self, tag):
        if self.heading and tag == self.heading[0]:
            self.headings.append((*self.heading, "".join(self.text)))
            self.heading = None


def main():
    pages = json.loads((ROOT / "docs/pages.json").read_text())
    template = (ROOT / "tools/template.html").read_text()
    search = []
    for page in pages:
        body = subprocess.run(
            ["pandoc", "--from=markdown-smart", "--to=html5", "--wrap=none",
             "--no-highlight", str(ROOT / "docs" / page["source"])],
            check=True, capture_output=True, text=True,
        ).stdout
        parsed = Sections()
        parsed.feed(body)
        parent = posixpath.dirname(page["output"]) or "."
        prefix = posixpath.relpath(".", parent) + "/"
        nav = "".join(
            '<a{} href="{}">{}</a>'.format(
                ' aria-current="page"' if entry == page else "",
                html.escape(posixpath.relpath(entry["output"], parent)),
                html.escape(entry["label"]),
            ) for entry in pages
        )
        toc = "".join(
            f'<a href="#{html.escape(anchor)}">{html.escape(title)}</a>'
            for level, anchor, title in parsed.headings if level == "h2" and anchor
        )
        values = {
            "title": html.escape(page["title"]),
            "description": html.escape(page["description"]),
            "label": html.escape(page["label"]), "prefix": prefix,
            "nav": nav, "toc": toc, "body": body,
            "source": html.escape(page["source"]),
        }
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("@@" + key + "@@", value)
        output = ROOT / page["output"]
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered)
        search.append({"title": page["title"], "url": page["output"],
                       "text": " ".join(parsed.all_text)})
        # Index each section separately so results can jump to a precise heading.
        parts = body.split('<h2 id="')
        for part in parts[1:]:
            anchor = part.split('"', 1)[0]
            section = Sections()
            section.feed('<h2 id="' + part)
            search.append({"title": section.headings[0][2],
                           "url": page["output"] + "#" + anchor,
                           "text": " ".join(section.all_text)})
    (ROOT / "assets/search-index.js").write_text(
        "window.UNITY_DOCS_INDEX = " + json.dumps(search, ensure_ascii=False) + ";\n"
    )
    (ROOT / ".nojekyll").touch()
    print(f"Built {len(pages)} pages and {len(search)} search entries.")


if __name__ == "__main__":
    main()
