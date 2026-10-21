# SPDX-FileCopyrightText: 2026 AOT Technologies
# SPDX-License-Identifier: Apache-2.0
"""Render the mermaid sources in scripts/doc_media/mermaid/ to SVGs in docs/images/media/.

Usage: python scripts/doc_media/mermaid.py [NAME ...]

Plain mermaid fences can't render a light canvas in GitHub's dark mode, so these
diagrams are pre-rendered and embedded as images: GitHub and the MkDocs site then
show the same file. The palette, panel and edge-label chip are read from
docs/stylesheets/extra.css, so the images match the site's own mermaid theme.

Each source starts with `%% title:` and `%% desc:` lines, which become the SVG's
<title> and <desc>. Labels are SVG text, not HTML, because <foreignObject> doesn't
render reliably inside <img>.

Needs Node.js (runs @mermaid-js/mermaid-cli through npx).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "scripts/doc_media/mermaid"
OUT = ROOT / "docs/images/media"
CSS = ROOT / "docs/stylesheets/extra.css"
MMDC = ["npx", "-y", "-p", "@mermaid-js/mermaid-cli@11.17.0", "mmdc"]
# Arial and Helvetica share metrics and ship on every desktop OS (Liberation Sans
# on Linux matches them), so labels measured at render time still fit when viewed.
FONT = "Arial, Helvetica, 'Liberation Sans', sans-serif"
PAD = 12


def site_theme() -> dict:
    """The site's mermaid palette and panel, from extra.css."""
    css = CSS.read_text()
    var = dict(re.findall(r"--md-mermaid-([a-z-]+):\s*([^;]+);", css))
    panel = re.search(r"\.md-typeset \.mermaid \{(.*?)\}", css, re.S).group(1)
    chip = re.search(r"\.md-typeset \.mermaid \.edgeLabel \{(.*?)\}", css, re.S).group(1)

    def prop(block: str, name: str) -> str:
        return re.search(rf"{name}:\s*([^;!]+)", block).group(1).strip()

    border = prop(panel, "border").split(" ", 2)
    return {
        "variables": {
            "fontFamily": FONT,
            "fontSize": "14px",
            "background": "#ffffff",
            "primaryColor": var["node-bg-color"],
            "primaryBorderColor": var["node-fg-color"],
            "primaryTextColor": var["label-fg-color"],
            "textColor": var["label-fg-color"],
            "titleColor": var["label-fg-color"],
            "lineColor": var["edge-color"],
            "edgeLabelBackground": prop(chip, "background"),
            "actorBkg": var["sequence-actor-bg-color"],
            "actorBorder": var["sequence-actor-border-color"],
            "actorTextColor": var["sequence-actor-fg-color"],
            "actorLineColor": var["sequence-actor-line-color"],
            "signalColor": var["edge-color"],
            "signalTextColor": var["sequence-message-fg-color"],
            "noteBkgColor": var["sequence-note-bg-color"],
            "noteTextColor": var["sequence-note-fg-color"],
            "noteBorderColor": var["sequence-note-border-color"],
            "sequenceNumberColor": var["sequence-number-fg-color"],
        },
        "panel_fill": prop(panel, "background"),
        "panel_stroke": border[2],
        "panel_radius": int(re.sub(r"\D", "", prop(panel, "border-radius"))),
    }


def render(source: Path, theme: dict, tmp: Path) -> Path:
    text = source.read_text()
    title = re.search(r"^%% title: (.+)$", text, re.M).group(1)
    desc = re.search(r"^%% desc: (.+)$", text, re.M).group(1)
    body = re.sub(r"^%% (title|desc|SPDX-[A-Za-z]+): .*\n", "", text, flags=re.M)
    mmd = tmp / source.name
    mmd.write_text(body)
    config = tmp / "config.json"
    config.write_text(
        json.dumps(
            {
                "theme": "base",
                "themeVariables": theme["variables"],
                "htmlLabels": False,
                "flowchart": {"htmlLabels": False},
                "themeCSS": ".cluster-label text, .label text { font-weight: 600; }",
            }
        )
    )
    puppeteer = tmp / "puppeteer.json"
    puppeteer.write_text('{"args": ["--no-sandbox"]}')
    raw = tmp / f"{source.stem}.svg"
    subprocess.run(
        [*MMDC, "-i", str(mmd), "-o", str(raw), "-c", str(config), "-p", str(puppeteer), "-b", "transparent", "-q",
         "--svgId", source.stem],
        check=True,
    )
    svg = raw.read_text()
    if "<foreignObject" in svg:
        sys.exit(f"{source.name}: rendered HTML labels; they won't show inside <img>")

    x, y, w, h = (float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split())
    x, y, w, h = x - PAD, y - PAD, w + 2 * PAD, h + 2 * PAD
    open_tag = re.search(r"<svg[^>]*>", svg).group(0)
    new_open = (
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        # mermaid scopes its stylesheet to this id, so it must survive the rewrite
        f'id="{source.stem}" viewBox="{x:g} {y:g} {w:g} {h:g}" width="{w:.0f}" height="{h:.0f}" '
        f'role="img" aria-labelledby="{source.stem}-t {source.stem}-d">'
        # REUSE-IgnoreStart
        "<!--\n  SPDX-FileCopyrightText: 2026 AOT Technologies\n  SPDX-License-Identifier: Apache-2.0\n  -->"
        # REUSE-IgnoreEnd
        f"<!-- Generated by scripts/doc_media/mermaid.py from {source.relative_to(ROOT)}. Do not edit. -->"
        f'<title id="{source.stem}-t">{escape(title)}</title>'
        f'<desc id="{source.stem}-d">{escape(desc)}</desc>'
        f'<rect x="{x + 0.5:g}" y="{y + 0.5:g}" width="{w - 1:g}" height="{h - 1:g}" '
        f'rx="{theme["panel_radius"]}" fill="{theme["panel_fill"]}" stroke="{theme["panel_stroke"]}"/>'
    )
    svg = svg.replace(open_tag, new_open, 1)
    # mermaid writes 15-digit coordinates; two decimals is well below a pixel
    svg = re.sub(r"(-?\d+\.\d{2})\d+", r"\1", svg)
    out = OUT / f"{source.stem}.svg"
    out.write_text(svg)
    return out


def main() -> None:
    names = set(sys.argv[1:])
    theme = site_theme()
    with tempfile.TemporaryDirectory() as tmp:
        for source in sorted(SOURCES.glob("*.mmd")):
            if not names or source.stem in names:
                print(render(source, theme, Path(tmp)).relative_to(ROOT))


if __name__ == "__main__":
    main()
