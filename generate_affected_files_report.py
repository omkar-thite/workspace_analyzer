import argparse
import json
import subprocess
from pathlib import Path

from main import gather_workspace_snapshot
from test_impact_calculator import build_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate snapshot.json, read git diff, and write an affected-files report"
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root to analyze (default: .)",
    )
    parser.add_argument(
        "--snapshot",
        default="snapshot.json",
        help="Snapshot file to write (default: snapshot.json)",
    )
    parser.add_argument(
        "--output",
        default="affected_files.txt",
        help="Text report to write (default: affected_files.txt)",
    )
    parser.add_argument(
        "--cached",
        action="store_true",
        help="Use staged changes instead of working tree diff",
    )
    return parser.parse_args()


def git_diff_text(root: Path, cached: bool) -> str:
    command = ["git", "-C", str(root), "diff"]
    if cached:
        command.append("--cached")
    command.extend(["--", ".", ":(exclude)snapshot.json"])
    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return completed.stdout


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = root / snapshot_path

    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path

    snapshot = gather_workspace_snapshot(root)
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")

    diff_text = git_diff_text(root, args.cached)
    report_text = build_report(snapshot, diff_text)
    output_path.write_text(report_text, encoding="utf-8")

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
