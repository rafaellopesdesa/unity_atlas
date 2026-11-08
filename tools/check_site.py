#!/usr/bin/env python3
"""Check local links/anchors and shell syntax without running cluster commands."""
import ast
import json
import subprocess
import tempfile
import tomllib
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
        self.typed_blocks = []
        self.code = None
        self.language = ""

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "id" in attrs:
            assert attrs["id"] not in self.ids, f'Duplicate id: {attrs["id"]}'
            self.ids.add(attrs["id"])
        if tag in ("a", "link", "script"):
            self.links.append(attrs.get("href", attrs.get("src", "")))
        if tag == "pre":
            self.code = []
            self.language = attrs.get("class", "").split()

    def handle_data(self, data):
        if self.code is not None:
            self.code.append(data)

    def handle_endtag(self, tag):
        if tag == "pre" and self.code is not None:
            block = "".join(self.code)
            self.typed_blocks.append((self.language, block))
            if "bash" in self.language:
                self.blocks.append(block)
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
    for languages, block in page.typed_blocks:
        if "json" in languages:
            json.loads(block)
        if "toml" in languages:
            tomllib.loads(block)
assert blocks > 0, "No Bash code blocks were checked"
# The examples readers download must be the same scripts they see on the page.
examples = [(ROOT / "examples/atlas-bashrc.sh", "setting-up-environment/index.html")]
examples += [(example, "submitting-jobs/index.html")
             for example in (ROOT / "examples/slurm").iterdir()
             if example.suffix in (".sh", ".sbatch")]
for example, page_path in examples:
    subprocess.run(["bash", "-n", str(example)], check=True)
    page = pages[(ROOT / page_path).resolve()]
    assert example.read_text().strip() in [block.strip() for block in page.blocks], \
        f"Displayed script differs from download: {example.name}"
# The VS Code launchers are linked downloads; the Python/JSON examples are
# also displayed in full and must stay synchronized with their downloads.
for example in (ROOT / "examples/vscode").glob("*.sh"):
    subprocess.run(["bash", "-n", str(example)], check=True)
vscode_page = pages[(ROOT / "using-vscode/index.html").resolve()]
for name in ("check_atlas.py", "launch.json"):
    example = ROOT / "examples/vscode" / name
    content = example.read_text()
    if example.suffix == ".py":
        ast.parse(content, filename=str(example))
    else:
        json.loads(content)
    assert content.strip() in [block.strip() for _, block in vscode_page.typed_blocks], \
        f"Displayed example differs from download: {name}"
# Codex's launcher is a linked download. Its TOML configuration and package
# manifest are also displayed in full and must match the downloaded files.
for example in (ROOT / "examples/codex").glob("*.sh"):
    subprocess.run(["bash", "-n", str(example)], check=True)
codex_page = pages[(ROOT / "codex-agents/index.html").resolve()]
for example in (ROOT / "examples/codex").glob("*.toml"):
    content = example.read_text()
    tomllib.loads(content)
    assert content.strip() in [block.strip() for _, block in codex_page.typed_blocks], \
        f"Displayed example differs from download: {example.name}"
print(f"Checked {len(pages)} pages, {links} local links, and {blocks} Bash blocks.")
