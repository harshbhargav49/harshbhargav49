import datetime as dt
import html.parser
import os
import re
import urllib.request
from pathlib import Path

USERNAME = os.environ.get("GITHUB_USERNAME", "harshbhargav49").strip()
LEVEL_COLORS = {
    0: "#161b22",
    1: "#0e4429",
    2: "#006d32",
    3: "#26a641",
    4: "#39d353",
}


class CalendarParser(html.parser.HTMLParser):
    """Parse contribution levels from GitHub's public profile contribution calendar."""

    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if (
            tag == "td"
            and "ContributionCalendar-day" in attrs.get("class", "")
            and attrs.get("data-date")
            and attrs.get("data-level") is not None
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", attrs["data-date"])
        ):
            try:
                self.days[dt.date.fromisoformat(attrs["data-date"])] = max(0, min(4, int(attrs["data-level"])))
            except ValueError:
                pass


def fetch_contribution_levels():
    url = f"https://github.com/users/{USERNAME}/contributions"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; HarshPurpleSnake/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        page = response.read().decode("utf-8", errors="replace")

    parser = CalendarParser()
    parser.feed(page)
    if len(parser.days) < 300:
        raise RuntimeError(
            f"Expected at least 300 contribution cells, parsed {len(parser.days)}. "
            "GitHub may have changed its calendar markup or rate-limited the request."
        )
    return parser.days


def ordered_neighbors(node):
    row, col = node
    horizontal = [(row, col + 1), (row, col - 1)] if row % 2 == 0 else [(row, col - 1), (row, col + 1)]
    return horizontal + [(row + 1, col), (row - 1, col)]


def create_safe_route(levels, columns, rows):
    """
    Route only through empty cells. Every green contribution cell is an obstacle,
    and its 8 surrounding cells are a clearance buffer so the purple snake turns
    before it gets visually close to any contribution.
    """
    occupied = {
        (row, col)
        for row in range(rows)
        for col in range(columns)
        if levels[row][col] > 0
    }
    blocked = set(occupied)
    for row, col in occupied:
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                blocked.add((row + dr, col + dc))

    safe = set()
    for row in range(-1, rows + 1):
        for col in range(-1, columns + 1):
            is_outer_ring = row in (-1, rows) or col in (-1, columns)
            in_grid = 0 <= row < rows and 0 <= col < columns
            if is_outer_ring or (in_grid and (row, col) not in blocked):
                safe.add((row, col))

    start = (-1, -1)
    route = [start]
    visited = {start}

    def walk(node):
        for neighbor in ordered_neighbors(node):
            if neighbor in safe and neighbor not in visited:
                visited.add(neighbor)
                route.append(neighbor)
                walk(neighbor)
                route.append(node)

    walk(start)
    covered = sum(
        1 for row in range(rows) for col in range(columns)
        if (row, col) in visited and levels[row][col] == 0
    )
    total_safe = sum(
        1 for row in range(rows) for col in range(columns)
        if (row, col) in safe
    )
    print(f"Snake route covers {covered}/{total_safe} safe empty cells; contribution cells and their neighbors are avoided.")
    return route


def main():
    if not USERNAME:
        raise RuntimeError("GITHUB_USERNAME must be set.")

    days = fetch_contribution_levels()
    first_day, last_day = min(days), max(days)
    start_day = first_day - dt.timedelta(days=(first_day.weekday() + 1) % 7)
    end_day = last_day + dt.timedelta(days=(5 - last_day.weekday()) % 7)
    columns = ((end_day - start_day).days + 1) // 7
    rows = 7

    levels = [
        [days.get(start_day + dt.timedelta(days=col * 7 + row), 0) for col in range(columns)]
        for row in range(rows)
    ]

    cell, gap, margin = 10, 3, 16
    step = cell + gap
    width = margin * 2 + columns * cell + (columns - 1) * gap
    height = margin * 2 + rows * cell + (rows - 1) * gap
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Actual GitHub contribution calendar with a purple snake routed around contributions">',
        '<rect width="100%" height="100%" rx="8" fill="#0d1117"/>',
    ]

    # Draw contribution history unchanged.
    for col in range(columns):
        for row in range(rows):
            day = start_day + dt.timedelta(days=col * 7 + row)
            x, y = margin + col * step, margin + row * step
            level = levels[row][col]
            svg.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[level]}">'
                f'<title>{day.isoformat()}: contribution level {level}</title></rect>'
            )

    route_nodes = create_safe_route(levels, columns, rows)
    route_points = [
        (margin + col * step + cell / 2, margin + row * step + cell / 2)
        for row, col in route_nodes
    ]
    path = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in route_points)
    path_length = sum(
        ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        for (x1, y1), (x2, y2) in zip(route_points, route_points[1:])
    )
    duration = 50.0
    step_delay = step / (path_length / duration) if path_length else 0.1

    # Small purple segments stay centered in empty cells; contribution cells and
    # their immediate 8-neighborhood are excluded from the route.
    snake_colors = ["#f0abfc", "#e879f9", "#d946ef", "#c026d3", "#a21caf", "#86198f", "#701a75"]
    snake_size = 7
    for index, color in enumerate(snake_colors):
        delay = -index * step_delay
        svg.append(
            f'<rect x="{-snake_size / 2:.1f}" y="{-snake_size / 2:.1f}" '
            f'width="{snake_size}" height="{snake_size}" rx="2" fill="{color}" '
            f'stroke="#0d1117" stroke-width="0.5">'
            f'<animateMotion dur="{duration:.1f}s" begin="{delay:.4f}s" repeatCount="indefinite" '
            f'calcMode="paced" rotate="0" path="{path}"/></rect>'
        )

    svg.append("</svg>")
    Path("dist").mkdir(exist_ok=True)
    Path("dist/github-contribution-grid-snake-dark.svg").write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated actual contribution calendar with a purple snake that turns early around green cells for @{USERNAME}.")


if __name__ == "__main__":
    main()
