"""Publish a run's outputs to the GitHub Pages site under docs/.

    python -m space_opps.publish --out out/ --docs docs/ [--date YYYY-MM-DD]

Copies out/digest.md and out/opportunities.csv to docs/digests/<date>.{md,csv} and
regenerates docs/digests/index.json, which docs/index.html reads to list all runs.
The site only serves files under docs/, so digests must live there.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEADER_RE = re.compile(r"^Window: .*?\. (\d+) total, \*\*(\d+) new\*\*", re.M)
FAILED_RE = re.compile(r"^- ([\w.\-]+): FAILED", re.M)


def _summary(md_path: Path) -> dict:
    text = md_path.read_text(encoding="utf-8", errors="replace")
    m = HEADER_RE.search(text)
    return {
        "date": md_path.stem,
        "total": int(m.group(1)) if m else None,
        "new": int(m.group(2)) if m else None,
        "failed_sources": FAILED_RE.findall(text),
        "md": f"digests/{md_path.stem}.md",
        "csv": f"digests/{md_path.stem}.csv" if md_path.with_suffix(".csv").exists() else None,
    }


def build_index(digests_dir: Path) -> list[dict]:
    digests_dir.mkdir(parents=True, exist_ok=True)
    runs = [_summary(p) for p in digests_dir.glob("*.md") if DATE_RE.match(p.stem)]
    runs.sort(key=lambda r: r["date"], reverse=True)
    (digests_dir / "index.json").write_text(json.dumps(runs, indent=1) + "\n", encoding="utf-8")
    return runs


def import_legacy(legacy: Path, digests: Path) -> int:
    """Copy dated digests from a pre-Pages `digests/` dir into docs/digests (never overwrites)."""
    n = 0
    if not legacy.is_dir() or legacy.resolve() == digests.resolve():
        return 0
    digests.mkdir(parents=True, exist_ok=True)
    for p in legacy.iterdir():
        if p.suffix in {".md", ".csv"} and DATE_RE.match(p.stem) and not (digests / p.name).exists():
            shutil.copyfile(p, digests / p.name)
            n += 1
    return n


def publish(out: Path, docs: Path, run_date: str, legacy: Path | None = None) -> list[dict]:
    if not DATE_RE.match(run_date):
        raise SystemExit(f"invalid --date {run_date!r}; expected YYYY-MM-DD")
    digests = docs / "digests"
    digests.mkdir(parents=True, exist_ok=True)
    if legacy:
        import_legacy(legacy, digests)
    shutil.copyfile(out / "digest.md", digests / f"{run_date}.md")
    csv = out / "opportunities.csv"
    if csv.exists():
        shutil.copyfile(csv, digests / f"{run_date}.csv")
    return build_index(digests)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("out"))
    ap.add_argument("--docs", type=Path, default=Path("docs"))
    ap.add_argument("--date", default=date.today().isoformat())
    ap.add_argument("--legacy", type=Path, default=Path("digests"),
                    help="pre-Pages digests dir to import into docs/digests (default: digests/)")
    ap.add_argument("--index-only", action="store_true", help="only rebuild docs/digests/index.json")
    args = ap.parse_args(argv)
    if args.index_only:
        import_legacy(args.legacy, args.docs / "digests")
        runs = build_index(args.docs / "digests")
    else:
        runs = publish(args.out, args.docs, args.date, args.legacy)
    print(f"{len(runs)} digest(s) indexed in {args.docs / 'digests' / 'index.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
