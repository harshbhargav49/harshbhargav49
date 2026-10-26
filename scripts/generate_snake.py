import datetime as dt
import html
import json
import os
import urllib.error
import urllib.request
from pathlib import Path

USERNAME = os.environ["GITHUB_USERNAME"]
TOKEN = os.environ["GITHUB_TOKEN"]

QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
            contributionLevel
          }
        }
      }
    }
  }
}
"""

def fetch_calendar():
    payload = json.dumps({"query": QUERY, "variables": {"login": USERNAME}}).encode("utf-8")
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=payload,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
            "User-Agent": "harsh-non-eating-snake",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub GraphQL request failed ({exc.code}): {detail}") from exc

    if data.get("errors"):
        raise RuntimeError("GitHub GraphQL errors: " + json.dumps(data["errors"]))
    user = data.get("data", {}).get("user")
    if not user:
        raise RuntimeError(f"Could not read contribution calendar for @{USERNAME}.")
    return user["contributionsCollection"]["contributionCalendar"]["weeks"]

def main():
    weeks = fetch_calendar()
    if not weeks:
        raise RuntimeError("GitHub returned an empty contribution calendar.")

    # Keep the actual per-day contribution levels. Colors are the dark-theme
    # GitHub palette; the snake is drawn on top and never changes these cells.
    level_colors = {
        "NONE": "#161b22",
        "FIRST_QUARTILE": "#0e4429",
        "SECOND_QUARTILE": "#006d32",
        "THIRD_QUARTILE": "#26a641",
        "FOURTH_QUARTILE": "#39d353",
    }

    columns = len(weeks)
    rows = 7
    cell = 11
    gap = 4
    margin_x = 18
    margin_y = 18
    step = cell + gap
    width = margin_x * 2 + columns * cell + (columns - 1) * gap
    height = margin_y * 2 + rows * cell + (rows - 1) * gap

    cells = [[None for _ in range(rows)] for _ in range(columns)]
    for col, week in enumerate(weeks):
        for day in week["contributionDays"]:
            day_date = dt.date.fromisoformat(day["date"])
            # GitHub's contribution graph has Sunday on the first row.
            row = (day_date.weekday() + 1) % 7
            cells[col][row] = day

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Actual GitHub contributions with a moving purple snake">',
        '<rect width="100%" height="100%" rx="8" fill="#0d1117"/>',
    ]

    for col in range(columns):
        for row in range(rows):
            day = cells[col][row]
            x = margin_x + col * step
            y = margin_y + row * step
            if day is None:
                color = "#161b22"
                title = "No contribution data"
            else:
                level = day["contributionLevel"]
                color = level_colors.get(level, "#161b22")
                title = f'{day["date"]}: {day["contributionCount"]} contributions'
            svg.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{color}">'
                f'<title>{html.escape(title)}</title></rect>'
            )

    # A serpentine route crosses every week and row. Only the purple segments
    # are animated; the contribution cells remain unchanged underneath them.
    route = []
    for row in range(rows):
        col_indices = range(columns) if row % 2 == 0 else range(columns - 1, -1, -1)
        for col in col_indices:
            x = margin_x + col * step + cell / 2
            y = margin_y + row * step + cell / 2
            route.append((x, y))
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in route)

    # Short, evenly spaced body segments make one continuous-looking snake.
    segments = [
        ("#f0abfc", 10.5, 0.000),
        ("#e879f9", 10, -0.040),
        ("#d946ef", 9.5, -0.080),
        ("#c026d3", 9, -0.120),
        ("#a21caf", 9, -0.160),
        ("#86198f", 8.5, -0.200),
        ("#701a75", 8, -0.240),
    ]
    for color, size, delay in segments:
        svg.append(
            f'<rect width="{size}" height="{size}" rx="2.5" fill="{color}" stroke="#0d1117" stroke-width="0.5">'
            f'<animateMotion dur="30s" begin="{delay:.3f}s" repeatCount="indefinite" '
            f'calcMode="paced" rotate="0" path="{path}"/>'
            f'</rect>'
        )

    svg.append("</svg>")
    out = Path("dist")
    out.mkdir(exist_ok=True)
    target = out / "github-contribution-grid-snake-dark.svg"
    target.write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated {target} with {columns} contribution weeks for @{USERNAME}.")

if __name__ == "__main__":
    main()
