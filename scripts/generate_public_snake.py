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
    """Parse the contribution levels rendered on GitHub's public profile page."""

    def __init__(self):
        super().__init__()
        self.days = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "")
        date_text = attrs.get("data-date")
        level_text = attrs.get("data-level")
        if (
            tag == "td"
            and "ContributionCalendar-day" in classes
            and date_text
            and level_text is not None
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text)
        ):
            try:
                self.days[dt.date.fromisoformat(date_text)] = max(0, min(4, int(level_text)))
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
            f"Expected at least 300 real contribution cells; parsed {len(parser.days)}. "
            "GitHub may have changed its markup or rate-limited the request."
        )
    return parser.days


def ordered_neighbors(node):
    row, col = node
    # Favor horizontal movement first, alternating direction by row.
    horizontal = [(row, col + 1), (row, col - 1)] if row % 2 == 0 else [(row, col - 1), (row, col + 1)]
    return horizontal + [(row + 1, col), (row - 1, col)]


def create_safe_route(levels, columns, rows):
    """
    Build a continuous DFS route through empty cells only.
    Contribution cells (level > 0) are blocked. A safe outer ring lets the
    snake turn around the grid and reach the other side without crossing greens.
    """
    safe = set()
    for row in range(-1, rows + 1):
        for col in range(-1, columns + 1):
            is_outer_ring = row in (-1, rows) or col in (-1, columns)
            is_empty_cell = 0 <= row < rows and 0 <= col < columns and levels[row][col] == 0
            if is_outer_ring or is_empty_cell:
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
                # Retrace the same safe corridor; never cross a contribution cell.
                route.append(node)

    walk(start)
    covered = sum(1 for row in range(rows) for col in range(columns) if levels[row][col] == 0 and (row, col) in visited)
    total_empty = sum(1 for row in range(rows) for col in range(columns) if levels[row][col] == 0)
    print(f"Snake route covers {covered}/{total_empty} empty cells without entering contribution cells.")
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

    levels = []
    for row in range(rows):
        # Each column is one Sunday-to-Saturday week; GitHub's visible calendar is column-oriented.
        levels.append([
            days.get(start_day + dt.timedelta(days=col * 7 + row), 0)
            for col in range(columns)
        ])

    cell, gap = 10, 3
    step = cell + gap
    margin = 16
    width = margin * 2 + columns * cell + (columns - 1) * gap
    height = margin * 2 + rows * cell + (rows - 1) * gap

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Actual GitHub contributions with a purple snake that turns around green squares">',
        '<rect width="100%" height="100%" rx="8" fill="#0d1117"/>',
    ]

    # Draw the true contribution intensities first. These are never animated or changed.
    for col in range(columns):
        for row in range(rows):
            day = start_day + dt.timedelta(days=col * 7 + row)
            x = margin + col * step
            y = margin + row * step
            level = levels[row][col]
            svg.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" fill="{LEVEL_COLORS[level]}">'
                f'<title>{day.isoformat()}: contribution level {level}</title></rect>'
            )

    route_nodes = create_safe_route(levels, columns, rows)

    # Coordinates include one safe cell just outside the graph, making a visible route around edges.
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

    # The head/body are purple overlays, sized smaller than each cell so they stay in safe lanes.
    snake_colors = ["#f0abfc", "#e879f9", "#d946ef", "#c026d3", "#a21caf", "#86198f", "#701a75"]
    snake_size = 8
    for index, color in enumerate(snake_colors):
        delay = -index * step_delay
        svg.append(
            f'<rect x="{-snake_size / 2:.1f}" y="{-snake_size / 2:.1f}" '
            f'width="{snake_size}" height="{snake_size}" rx="2" fill="{color}" '
            f'stroke="#0d1117" stroke-width="0.4">'
            f'<animateMotion dur="{duration:.1f}s" begin="{delay:.4f}s" repeatCount="indefinite" '
            f'calcMode="paced" rotate="0" path="{path}"/>'
            f'</rect>'
        )

    svg.append("</svg>")
    output_dir = Path("dist")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "github-contribution-grid-snake-dark.svg"
    output_file.write_text("\n".join(svg), encoding="utf-8")
    print(f"Generated real contribution grid with a purple snake that avoids all green contribution cells for @{USERNAME}.")


if __name__ == "__main__":
    main()
