#!/usr/bin/env python3
"""Check local links/anchors and shell syntax without running cluster commands."""
import json
import subprocess
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = set()
        self.links = []
        self.blocks = []
        self.code = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids, f'Duplicate id: {attrs["id"]}'
            self.ids.add(attrs["id"])
        if tag in ("a", "link", "script"):
            self.links.append(attrs.get("href", attrs.get("src", "")))
        if tag == "pre" and "bash" in attrs.get("class", "").split():
            self.code = []

    def handle_data(self, data):
        if self.code is not None:
            self.code.append(data)

    def handle_endtag(self, tag):
        if tag == "pre" and self.code is not None:
            self.blocks.append("".join(self.code))
            self.code = None


pages = {}
metadata = json.loads((ROOT / "docs/pages.json").read_text())
for entry in metadata:
    path = (ROOT / entry["output"]).resolve()
    page = Page()
    page.feed(path.read_text())
    pages[path] = page

links = 0
blocks = 0
for path, page in pages.items():
    for link in page.links:
        url = urlsplit(link)
        if url.scheme or url.netloc:
            continue
        target = (path.parent / unquote(url.path)).resolve() if url.path else path
        if target.is_dir():
            target = target / "index.html"
        assert target.is_relative_to(ROOT), f'Link escapes site: {link}'
        assert target.exists(), f'Missing target in {path.name}: {link}'
        if url.fragment:
            assert target in pages and unquote(url.fragment) in pages[target].ids, f'Missing anchor: {link}'
        links += 1
    for block in page.blocks:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".sh") as script:
            script.write(block)
            script.flush()
            subprocess.run(["bash", "-n", script.name], check=True)
        blocks += 1
assert blocks > 0, "No Bash code blocks were checked"
print(f"Checked {len(pages)} pages, {links} local links, and {blocks} Bash blocks.")
