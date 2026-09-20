#!/usr/bin/env python3
"""Build the GitHub Pages catalogue from files in hdds/."""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote


ROOT = Path(__file__).resolve().parent
REPORTS_DIR = ROOT / "hdds"
AVAILABILITY_FILE = ROOT / "availability.json"
OUTPUT_FILE = ROOT / "index.html"
REPORT_PATTERN = re.compile(r"^(?P<number>.+)_(?P<kind>hdsentinel|smartctl)\.txt$")
# A neutral hosted placeholder is used until a correctly named local image exists.
PLACEHOLDER_IMAGE = "https://placehold.co/320x220/334155/e2e8f0?text=HDD+Image+Placeholder"


def natural_key(value: str) -> list[object]:
    """Sort text with its numeric parts as numbers (4TB2 before 4TB10)."""
    return [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]


def discover_drives() -> dict[str, dict[str, Path]]:
    drives: dict[str, dict[str, Path]] = {}
    if not REPORTS_DIR.is_dir():
        print("Warning: hdds/ directory does not exist; generating an empty catalogue.", file=sys.stderr)
        return drives

    for path in REPORTS_DIR.iterdir():
        if not path.is_file():
            continue
        match = REPORT_PATTERN.match(path.name)
        if match:
            drives.setdefault(match["number"], {})[match["kind"]] = path
    return drives


def parse_hdsentinel(path: Path | None) -> dict[str, str]:
    values = {"serial": "Unknown", "health": "Unknown", "performance": "Unknown"}
    if path is None:
        return values

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as error:
        print(f"Warning: could not read {path.relative_to(ROOT)}: {error}", file=sys.stderr)
        return values

    fields = {
        "serial": r"HDD\s+Serial\s+No",
        "health": r"Health",
        "performance": r"Performance",
    }
    for key, label in fields.items():
        match = re.search(rf"^\s*{label}\s*:\s*(.*?)\s*$", text, re.MULTILINE | re.IGNORECASE)
        if match and match.group(1).strip():
            values[key] = match.group(1).strip()
    return values


def load_availability() -> dict[str, str]:
    if not AVAILABILITY_FILE.exists():
        return {}
    try:
        data = json.loads(AVAILABILITY_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"Warning: could not parse availability.json: {error}", file=sys.stderr)
        return {}
    if not isinstance(data, dict):
        print("Warning: availability.json must contain a JSON object; ignoring its contents.", file=sys.stderr)
        return {}
    return data


def availability_for_drives(drives: dict[str, dict[str, Path]]) -> dict[str, str]:
    saved = load_availability()
    availability: dict[str, str] = {}
    for number in sorted(drives, key=natural_key):
        value = saved.get(number, "YES")
        if value not in {"YES", "NO"}:
            print(
                f"Warning: availability for {number!r} is {value!r}; expected YES or NO. "
                "Using YES for this generated page; fix availability.json.",
                file=sys.stderr,
            )
            value = "YES"
        availability[number] = value

    # Rewrite only the currently discovered drives: it adds new entries and removes stale ones.
    AVAILABILITY_FILE.write_text(json.dumps(availability, indent=2) + "\n", encoding="utf-8")
    return availability


def relative_url(path: Path) -> str:
    return quote(path.relative_to(ROOT).as_posix(), safe="/")


def image_url(number: str) -> str:
    # The final run of digits is the drive number: 4TB01 becomes 4TB#01.jpg.
    image_name = re.sub(r"(\d+)$", r"#\1", number) + ".jpg"
    return quote(f"Images/{image_name}", safe="/")


def report_link(path: Path | None, label: str) -> str:
    if path is None:
        return '<span class="unavailable-report">Unavailable</span>'
    url = relative_url(path)
    return f'<a href="{url}" target="_blank" rel="noopener">{label}</a>'


def make_row(number: str, reports: dict[str, Path], availability: str) -> str:
    details = parse_hdsentinel(reports.get("hdsentinel"))
    status_class = "available" if availability == "YES" else "unavailable"
    local_image = image_url(number)
    fallback = html.escape(PLACEHOLDER_IMAGE, quote=True)
    return f"""                <tr>
                  <th scope=\"row\">{html.escape(number)}</th>
                  <td><span class=\"status {status_class}\">{availability}</span></td>
                  <td>{report_link(reports.get('hdsentinel'), 'View HDSentinel')}</td>
                  <td>{report_link(reports.get('smartctl'), 'View SMART')}</td>
                  <td class=\"serial\">{html.escape(details['serial'])}</td>
                  <td>{html.escape(details['health'])}</td>
                  <td>{html.escape(details['performance'])}</td>
                  <td><a class=\"image-link\" href=\"{local_image}\" target=\"_blank\" rel=\"noopener\"><img src=\"{local_image}\" alt=\"{html.escape(number)} hard drive\" loading=\"lazy\" onerror=\"this.onerror=null;this.src='{fallback}';this.closest('a').href='{fallback}';\"></a></td>
                </tr>"""


def render(drives: dict[str, dict[str, Path]], availability: dict[str, str]) -> str:
    numbers = sorted(drives, key=natural_key)
    available = sum(availability[number] == "YES" for number in numbers)
    unavailable = len(numbers) - available
    rows = "\n".join(make_row(number, drives[number], availability[number]) for number in numbers)
    if not rows:
        rows = '                <tr><td colspan="8" class="empty">No HDD diagnostic reports were found.</td></tr>'
    return f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>HDD's for Sale</title>
  <!-- Generated by generate.py. Edit availability.json rather than manually changing availability in this file. -->
  <style>
    :root {{ color-scheme: dark; --page: #26313d; --panel: #303d4b; --row: #344252; --row-alt: #2f3c4a; --text: #edf2f7; --muted: #b4c0ce; --line: #4a5a6b; --link: #76c7dd; --yes-bg: #305c4b; --yes-text: #c8e4d3; --no-bg: #663f46; --no-text: #f0ced0; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; min-width: 320px; background: var(--page); color: var(--text); font: 16px/1.5 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ width: min(1440px, calc(100% - 2rem)); margin: 2rem auto; padding: clamp(1.25rem, 4vw, 2.5rem); background: var(--panel); border: 1px solid var(--line); border-radius: 18px; box-shadow: 0 18px 45px rgb(0 0 0 / 16%); }}
    h1 {{ margin: 0; font-size: clamp(2rem, 5vw, 3rem); letter-spacing: -.035em; }}
    h2 {{ margin: 0 0 .75rem; font-size: 1.15rem; }}
    .intro {{ max-width: 70ch; margin: .75rem 0 1.75rem; color: var(--muted); }}
    .diagnostics {{ margin-bottom: 1.5rem; padding: 1rem 1.15rem; background: #293643; border: 1px solid var(--line); border-radius: 12px; }}
    .diagnostics p {{ margin: 0 0 .75rem; color: var(--muted); }}
    pre {{ margin: 0; overflow-x: auto; padding: .9rem 1rem; border-radius: 8px; background: #202b35; color: #d8edf2; font: .9rem/1.6 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }}
    .summary {{ display: flex; flex-wrap: wrap; gap: .75rem; margin: 1.25rem 0; }}
    .metric {{ min-width: 9rem; padding: .7rem .9rem; background: #2a3744; border: 1px solid var(--line); border-radius: 10px; color: var(--muted); }}
    .metric strong {{ display: block; color: var(--text); font-size: 1.35rem; }}
    .table-wrap {{ overflow-x: auto; border: 1px solid var(--line); border-radius: 12px; }}
    table {{ width: 100%; min-width: 1040px; border-collapse: collapse; }}
    th, td {{ padding: .8rem .9rem; border-bottom: 1px solid var(--line); text-align: left; vertical-align: middle; }}
    thead th {{ position: sticky; top: 0; z-index: 1; background: #26323e; color: #dce6ef; font-size: .8rem; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; }}
    tbody tr {{ background: var(--row); }} tbody tr:nth-child(even) {{ background: var(--row-alt); }} tbody tr:hover {{ background: #3b4c5d; }} tbody tr:last-child th, tbody tr:last-child td {{ border-bottom: 0; }}
    a {{ color: var(--link); text-underline-offset: .18em; }} a:hover {{ color: #a3e0ed; }}
    .status {{ display: inline-block; min-width: 3.5rem; padding: .18rem .55rem; border: 1px solid currentColor; border-radius: 999px; text-align: center; font-size: .78rem; font-weight: 700; letter-spacing: .06em; }}
    .available {{ background: var(--yes-bg); color: var(--yes-text); }} .unavailable {{ background: var(--no-bg); color: var(--no-text); }}
    .serial {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }} .unavailable-report {{ color: var(--muted); font-style: italic; }}
    .image-link {{ display: block; width: 104px; }} .image-link img {{ display: block; width: 100%; max-width: 104px; height: 70px; object-fit: contain; border: 1px solid var(--line); border-radius: 7px; background: #25313d; }}
    .empty {{ color: var(--muted); text-align: center; }} footer {{ margin-top: 1.5rem; color: var(--muted); font-size: .88rem; }}
    @media (max-width: 600px) {{ main {{ width: min(100% - 1rem, 1440px); margin: .5rem auto; border-radius: 12px; }} .summary {{ gap: .5rem; }} .metric {{ flex: 1 1 30%; min-width: 7rem; }} }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>HDD's for Sale</h1>
      <p class=\"intro\">This catalogue lists hard drives and their availability alongside the diagnostic reports collected for each drive.</p>
    </header>
    <section class=\"diagnostics\" aria-labelledby=\"diagnostics-title\">
      <h2 id=\"diagnostics-title\">Drive Diagnostics</h2>
      <p>The linked diagnostic reports were generated on Linux using these commands.</p>
      <pre><code>/usr/local/bin/hdsentinel -verbose -dev /dev/${{HDD}}
smartctl -a /dev/${{HDD}}</code></pre>
    </section>
    <section class=\"summary\" aria-label=\"HDD availability summary\">
      <div class=\"metric\"><strong>{len(numbers)}</strong>Total HDDs</div>
      <div class=\"metric\"><strong>{available}</strong>Available</div>
      <div class=\"metric\"><strong>{unavailable}</strong>Unavailable</div>
    </section>
    <div class=\"table-wrap\">
      <table>
        <thead><tr><th>HDD Number</th><th>Available</th><th>hdsentinel output</th><th>smartctl output</th><th>Serial Number</th><th>Health</th><th>Performance</th><th>Image</th></tr></thead>
        <tbody>
{rows}
        </tbody>
      </table>
    </div>
    <footer>HDD diagnostic information was generated using HDSentinel and smartctl.</footer>
  </main>
</body>
</html>
"""


def main() -> None:
    drives = discover_drives()
    availability = availability_for_drives(drives)
    OUTPUT_FILE.write_text(render(drives, availability), encoding="utf-8")
    available = sum(value == "YES" for value in availability.values())
    print(f"Discovered {len(drives)} HDDs")
    print(f"Available: {available}")
    print(f"Unavailable: {len(drives) - available}")
    print("Generated index.html")


if __name__ == "__main__":
    main()
