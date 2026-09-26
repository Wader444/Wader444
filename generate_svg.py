#!/usr/bin/env python3
"""
generate_svg.py
───────────────
Reads ascii_art.txt + stats.json and renders profile.svg:
  - Amber-on-#0d1117 retro CRT terminal window
  - macOS-style traffic-light dots
  - Fira Code / JetBrains Mono monospace font via @font-face
  - Fixed-width columns so stat numbers never break layout
  - Explicit background (works on both GitHub light and dark themes)

Usage:
    python generate_svg.py          # reads stats.json, writes profile.svg
"""

import json
import os
import html

# ── Paths ────────────────────────────────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
ASCII_ART_PATH = os.path.join(HERE, "ascii_art.txt")
STATS_PATH = os.path.join(HERE, "stats.json")
SVG_PATH = os.path.join(HERE, "profile.svg")

# ── Static profile info ───────────────────────────────────────────────────────
STATIC = {
    "os":          "Windows 11",
    "host":        "Personal Laptop",
    "kernel":      "NT 10.0.26100",
    "ide":         "VS Code",
    "langs_prog":  "Python, TypeScript",
    "langs_markup":"HTML, CSS, Markdown",
    "hobbies":     "Coding, Gaming, Reading",
    "email":       "cherish@example.com",
    "linkedin":    "linkedin.com/in/cherish64",
}

# ── Layout constants ──────────────────────────────────────────────────────────
SVG_WIDTH        = 900
SVG_HEIGHT       = 480
PADDING          = 24          # outer padding from window edge
TITLE_BAR_H      = 36          # height of the macOS-style title bar
DOT_Y            = TITLE_BAR_H // 2
DOT_RADIUS       = 7
DOT_GAP          = 22
FONT_SIZE        = 13          # px  →  monospace cell ≈ 7.8 px wide, 18 px tall
LINE_H           = 20          # vertical step between text lines
CHAR_W           = 7.8         # estimated width of 1 monospace char
LEFT_PANEL_CHARS = 40          # max chars reserved for the ASCII art column
RIGHT_PANEL_X    = int(PADDING + LEFT_PANEL_CHARS * CHAR_W + 20)
TEXT_Y_START     = TITLE_BAR_H + PADDING + FONT_SIZE  # y of first text line

# ── Palette ───────────────────────────────────────────────────────────────────
BG_COLOR         = "#0d1117"
BORDER_COLOR     = "#2a2a3a"
TITLE_BAR_BG     = "#161b22"
DOT_RED          = "#ff5f57"
DOT_YELLOW       = "#febc2e"
DOT_GREEN        = "#28c840"
AMBER            = "#ffb347"   # primary amber (labels, ASCII)
AMBER_DIM        = "#cc8a30"   # dim amber (separator lines, frame text)
CYAN             = "#56d4c8"   # accent cyan for values
WHITE_DIM        = "#c9d1d9"   # dim white for plain values
CURSOR_COLOR     = "#ffb347"

# ── Font embed ────────────────────────────────────────────────────────────────
FONT_FACE = """
  @font-face {
    font-family: 'FiraCode';
    src: url('https://cdn.jsdelivr.net/npm/@fontsource/fira-code@5/files/fira-code-latin-400-normal.woff2') format('woff2');
    font-weight: 400;
    font-style: normal;
  }
"""
FONT_STACK = "'FiraCode', 'JetBrains Mono', 'Fira Code', 'Courier New', monospace"

# ── Helpers ───────────────────────────────────────────────────────────────────

def e(s: str) -> str:
    """HTML-escape a string for safe SVG text content."""
    return html.escape(str(s))


def fixed(value, width: int, fill: str = " ") -> str:
    """Right-pad `value` to exactly `width` chars (monospace fixed field)."""
    s = str(value)
    if len(s) >= width:
        return s[:width]
    return s + fill * (width - len(s))


def load_ascii_art() -> list[str]:
    """Load ascii_art.txt; strip comment lines; return list of raw strings."""
    if not os.path.exists(ASCII_ART_PATH):
        return ["[ascii_art.txt not found]"]
    with open(ASCII_ART_PATH, encoding="utf-8") as f:
        lines = f.read().splitlines()
    # Strip lines that start with '#'
    art = [ln for ln in lines if not ln.startswith("#")]
    # Remove leading/trailing blank lines
    while art and not art[0].strip():
        art.pop(0)
    while art and not art[-1].strip():
        art.pop()
    return art or ["[paste your art in ascii_art.txt]"]


def load_stats() -> dict:
    if not os.path.exists(STATS_PATH):
        # Fallback placeholder stats (so SVG is still renderable)
        return {
            "public_repos": "—",
            "stars": "—",
            "followers": "—",
            "commits": "—",
            "lines_changed": "—",
            "uptime": "?",
        }
    with open(STATS_PATH, encoding="utf-8") as f:
        return json.load(f)


def fmt_num(n) -> str:
    """Format integer with thousands separator, or return as-is if string."""
    try:
        return f"{int(n):,}"
    except (ValueError, TypeError):
        return str(n)

# ── SVG building blocks ───────────────────────────────────────────────────────

def make_text(x: float, y: float, text: str, color: str,
              anchor: str = "start", opacity: float = 1.0,
              font_size: int = FONT_SIZE) -> str:
    style = f"fill:{color};font-family:{FONT_STACK};font-size:{font_size}px;"
    if opacity < 1:
        style += f"opacity:{opacity};"
    return (
        f'<text x="{x}" y="{y}" text-anchor="{anchor}" '
        f'xml:space="preserve" style="{style}">{e(text)}</text>'
    )


def make_label_value(x: float, y: float, label: str, value: str,
                     label_color: str = AMBER,
                     value_color: str = CYAN,
                     label_width: int = 22) -> str:
    """Render `LABEL          value` with fixed-width label column."""
    label_fixed = fixed(label, label_width)
    style_label = (
        f"fill:{label_color};font-family:{FONT_STACK};"
        f"font-size:{FONT_SIZE}px;"
    )
    style_value = (
        f"fill:{value_color};font-family:{FONT_STACK};"
        f"font-size:{FONT_SIZE}px;"
    )
    value_x = x + label_width * CHAR_W
    return (
        f'<text x="{x}" y="{y}" xml:space="preserve" style="{style_label}">'
        f'{e(label_fixed)}</text>'
        f'<text x="{value_x}" y="{y}" xml:space="preserve" style="{style_value}">'
        f'{e(value)}</text>'
    )

# ── Main SVG generator ────────────────────────────────────────────────────────

def generate_svg() -> str:
    art_lines = load_ascii_art()
    stats = load_stats()

    # ── Right-panel field rows ────────────────────────────────────────────────
    uptime_str = stats.get("uptime", "?")

    # Build label-value pairs; values are fixed-width to prevent drift
    VAL_W = 26  # max chars for value column

    fields = [
        ("OS",                   fixed(STATIC["os"],          VAL_W)),
        ("Uptime",               fixed(uptime_str,            VAL_W)),
        ("Host",                 fixed(STATIC["host"],        VAL_W)),
        ("Kernel",               fixed(STATIC["kernel"],      VAL_W)),
        ("IDE",                  fixed(STATIC["ide"],         VAL_W)),
        ("Languages.Programming",fixed(STATIC["langs_prog"],  VAL_W)),
        ("Languages.Markup",     fixed(STATIC["langs_markup"],VAL_W)),
        ("Hobbies",              fixed(STATIC["hobbies"],     VAL_W)),
        ("Contact.Email",        fixed(STATIC["email"],       VAL_W)),
        ("Contact.LinkedIn",     fixed(STATIC["linkedin"],    VAL_W)),
        # Separator
        None,
        # GitHub stats
        ("GitHub Stats",         ""),
        ("  Repos",              fixed(fmt_num(stats.get("public_repos","—")), VAL_W)),
        ("  Stars",              fixed(fmt_num(stats.get("stars","—")),        VAL_W)),
        ("  Followers",          fixed(fmt_num(stats.get("followers","—")),    VAL_W)),
        ("  Commits",            fixed(fmt_num(stats.get("commits","—")),      VAL_W)),
        ("  Lines Changed",      fixed(fmt_num(stats.get("lines_changed","—")),VAL_W)),
    ]

    # ── Calculate required height ─────────────────────────────────────────────
    right_rows = len(fields) + 2           # +2 for header + prompt line
    left_rows  = len(art_lines) + 2
    content_rows = max(right_rows, left_rows)
    height = max(SVG_HEIGHT, TEXT_Y_START + content_rows * LINE_H + PADDING + 10)

    # ── Assemble SVG elements ─────────────────────────────────────────────────
    elements: list[str] = []

    # Background + border
    elements.append(
        f'<rect width="{SVG_WIDTH}" height="{height}" rx="12" ry="12" '
        f'fill="{BG_COLOR}" stroke="{BORDER_COLOR}" stroke-width="1.5"/>'
    )
    # Title bar
    elements.append(
        f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{TITLE_BAR_H}" '
        f'rx="12" ry="12" fill="{TITLE_BAR_BG}"/>'
    )
    # Cover bottom-round of title bar so it looks flat at the bottom edge
    elements.append(
        f'<rect x="0" y="{TITLE_BAR_H//2}" width="{SVG_WIDTH}" '
        f'height="{TITLE_BAR_H//2}" fill="{TITLE_BAR_BG}"/>'
    )

    # Traffic-light dots
    dot_x = PADDING
    for color, label in [(DOT_RED, "●"), (DOT_YELLOW, "●"), (DOT_GREEN, "●")]:
        elements.append(
            f'<circle cx="{dot_x + DOT_RADIUS}" cy="{DOT_Y}" r="{DOT_RADIUS}" '
            f'fill="{color}"/>'
        )
        dot_x += DOT_GAP

    # Title bar label
    title_text = "wader444@github ~ zsh"
    elements.append(make_text(
        SVG_WIDTH / 2, DOT_Y + FONT_SIZE // 2 - 1,
        title_text, AMBER_DIM, anchor="middle"
    ))

    # ── Left panel: ASCII art ─────────────────────────────────────────────────
    for i, line in enumerate(art_lines):
        y = TEXT_Y_START + i * LINE_H
        elements.append(make_text(PADDING, y, line, AMBER))

    # ── Divider line ──────────────────────────────────────────────────────────
    div_x = RIGHT_PANEL_X - 12
    elements.append(
        f'<line x1="{div_x}" y1="{TITLE_BAR_H + 8}" '
        f'x2="{div_x}" y2="{height - 8}" '
        f'stroke="{AMBER_DIM}" stroke-width="1" stroke-dasharray="4 4" opacity="0.5"/>'
    )

    # ── Right panel: header ───────────────────────────────────────────────────
    LABEL_W = 22   # chars for label column in right panel
    rx = RIGHT_PANEL_X
    ry = TEXT_Y_START

    header = f"wader444@github"
    elements.append(make_text(rx, ry, header, AMBER))
    ry += LINE_H
    separator_line = "─" * (LABEL_W + VAL_W)
    elements.append(make_text(rx, ry, separator_line, AMBER_DIM, opacity=0.6))
    ry += LINE_H

    # ── Right panel: fields ───────────────────────────────────────────────────
    for row in fields:
        if row is None:
            # blank separator
            elements.append(make_text(rx, ry, "", AMBER_DIM))
        elif row[1] == "":
            # Section header (e.g. "GitHub Stats")
            elements.append(make_text(rx, ry, row[0], AMBER))
        else:
            label, value = row
            # Determine value color
            v_color = CYAN if not label.startswith("  ") else WHITE_DIM
            if label.startswith("  "):
                # stat sub-row: show stat value in amber
                v_color = AMBER
            elements.append(make_label_value(rx, ry, label, value,
                                             label_color=AMBER_DIM if label.startswith("  ") else AMBER,
                                             value_color=v_color,
                                             label_width=LABEL_W))
        ry += LINE_H

    # Blinking cursor prompt line
    prompt = "$ _"
    elements.append(make_text(PADDING, ry + LINE_H, prompt, CURSOR_COLOR))

    # ── Compose full SVG ──────────────────────────────────────────────────────
    style_block = f"<style>{FONT_FACE}</style>"

    elements_str = "\n  ".join(elements)
    svg = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg"\n'
        f'     width="{SVG_WIDTH}" height="{height}"\n'
        f'     viewBox="0 0 {SVG_WIDTH} {height}"\n'
        f'     role="img"\n'
        f'     aria-label="Wader444 GitHub profile card">\n'
        f'  {style_block}\n'
        f'  {elements_str}\n'
        f'</svg>\n'
    )
    return svg


def main():
    svg_content = generate_svg()
    with open(SVG_PATH, "w", encoding="utf-8") as f:
        f.write(svg_content)
    print(f"profile.svg written ({len(svg_content):,} bytes)")


if __name__ == "__main__":
    main()
