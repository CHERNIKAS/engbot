"""Drive gen_constructor.py across every topic that still needs phrases.

One long run rather than twenty-nine invocations pasted by hand: the specs
live in `constructor_specs.py`, and each topic writes its own file, so an
interrupted run resumes where it stopped instead of starting over.

Usage:
    python scripts/run_constructor.py --out-dir /tmp/ctor --count 100
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.constructor_specs import MAX_WORDS, SPECS  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--count", type=int, default=100)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--only", nargs="*", help="limit to these slugs")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    slugs = args.only or list(SPECS)

    for i, slug in enumerate(slugs, 1):
        out = out_dir / f"{slug}.json"
        if out.exists():
            have = len(json.loads(out.read_text(encoding="utf-8")))
            if have >= args.count:
                print(f"[{i}/{len(slugs)}] {slug}: уже {have}, пропускаю", flush=True)
                continue
        print(f"[{i}/{len(slugs)}] {slug}", flush=True)
        subprocess.run(
            [
                sys.executable, "scripts/gen_constructor.py",
                "--topic", slug,
                "--count", str(args.count),
                "--batch", str(args.batch),
                "--out", str(out),
                "--spec", SPECS[slug],
                *(["--max-words", str(MAX_WORDS[slug])] if slug in MAX_WORDS else []),
            ],
            check=False,
        )

    total = 0
    for slug in slugs:
        out = out_dir / f"{slug}.json"
        n = len(json.loads(out.read_text(encoding="utf-8"))) if out.exists() else 0
        total += n
        print(f"{slug:30} {n}")
    print(f"итого {total}")


if __name__ == "__main__":
    main()
