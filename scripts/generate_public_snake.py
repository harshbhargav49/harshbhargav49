import datetime as dt
import html.parser
import os
import re
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "harshbhargav49")
LEVEL_COLORS = {0: "#161b22", 1: "#0e4429", 2: "#006d32", 3: "#26a641", 4: "#39d353"}

class CalendarParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "td" and "ContributionCalendar-day" in a.get("class", ""):
            date_text, level_text = a.get("data-date"), a.get("data-level")
            if date_text and level_text is not None and re.fullmatch(r"\\d{4}-\\d{2}-\\d{2}", date_text):
                try:
                    self.days[dt.date.fromisoformat(date_text)] = max(0, min(4, int(level_text)))
                except ValueError:
                    pass

def main():
    url = f"https://github.com/users/{USERNAME}/contributions"
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; HarshPurpleSnake/1.0)",
        "Accept": "text/html,application/xhtml+xml"
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    parser = CalendarParser()
    parser.feed(page)
    days = parser.days
    if len(days) < 300:
        raise RuntimeError(f"Expected at least 300 real contribution cells; parsed {len(days)}. GitHub may have changed its page markup.")

    earliest, latest = min(days), max(days)
    start = earliest - dt.timedelta(days=(earliest.weekday() + 1) % 7)
    end = latest + dt.timedelta(days=(5 - latest.weekday()) % 7)
    columns = ((end - start).days + 1) // 7
    rows, cell, gap, margin = 7, 10, 3, 16
    step = cell + gap
    width = margin * 2 + columns * cell + (columns - 1) * gap
    height = margin * 2 + rows * cell + (rows - 1) * gap
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Actual GitHub contributions with a moving purple snake">',
           '<rect width="100%" height="100%" rx="8" fill="#0d1117"/>']

    for col in range(columns):
        for row in range(rows):
            day = start + dt.timedelta(days=col * 7 + row)
            x, y = margin + col * step, margin + row * step
            level = days.get(day, 0)
            svg.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[level]}"><title>{day.isoformat()}: contribution level {level}</title></rect>')

    # Sweep over every row and connect the end back around the top/right edge.
    route = []
    for row in range(rows):
        cols = range(columns) if row % 2 == 0 else range(columns - 1, -1, -1)
        for col in cols:
            route.append((margin + col * step + cell / 2, margin + row * step + cell / 2))
    sx, sy = route[0]
    ex, ey = route[-1]
    route.extend([(ex + cell + gap, ey), (ex + cell + gap, margin - 5), (sx, margin - 5), (sx, sy)])
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in route)
    length = sum(((b[0]-a[0])**2 + (b[1]-a[1])**2)**0.5 for a, b in zip(route, route[1:]))
    duration = 38.0
    delay_step = 13.0 / (length / duration)
    for i, color in enumerate(["#f0abfc", "#e879f9", "#d946ef", "#c026d3", "#a21caf", "#86198f", "#701a75"]):
        size = 11
        delay = -i * delay_step
        svg.append(f'<rect x="-{size/2:.1f}" y="-{size/2:.1f}" width="{size}" height="{size}" rx="2.8" fill="{color}" stroke="#0d1117" stroke-width="0.4"><animateMotion dur="{duration}s" begin="{delay:.3f}s" repeatCount="indefinite" calcMode="paced" rotate="0" path="{path}"/></rect>')

    svg.append("</svg>")
    Path("dist").mkdir(exist_ok=True)
    Path("dist/github-contribution-grid-snake-dark.svg").write_text("\\n".join(svg), encoding="utf-8")
    print(f"Generated real contribution grid for @{USERNAME} with a non-eating purple snake.")

if __name__ == "__main__":
    main()
