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
    parser.add_argument(
        "--commit",
        help="Commit ID to diff against (uses git diff <commit>~1..<commit>)",
    )
    return parser.parse_args()


def git_diff_text(root: Path, cached: bool, commit: str | None = None) -> str:
    from main import load_ignore_patterns

    command = ["git", "-C", str(root), "diff"]
    if commit:
        command.extend([f"{commit}~1", commit])
    elif cached:
        command.append("--cached")
    
    # Initialize the separator and the base pathspecs
    command.extend(["--", ".", ":(exclude)snapshot.json"])

    # Append exclusions using pathspec magic
    ignore_patterns = load_ignore_patterns(root)
    for pattern in ignore_patterns:
        clean_pattern = pattern.strip()
        if not clean_pattern or clean_pattern.startswith("#"):
            continue  # Skip empty lines or comments
            
        if clean_pattern.endswith("/"):
            # Append ** to explicitly ignore all contents within the directory
            command.append(f":(exclude){clean_pattern}**")
        else:
            command.append(f":(exclude){clean_pattern}")

    completed = subprocess.run(command, capture_output=True, text=True, check=True)
    return completed.stdout


def main() -> None:
    args = parse_args()
    root = Path(args.root).resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = root / output_path

    snapshot_path = Path(args.snapshot)
    if not snapshot_path.is_absolute():
        snapshot_path = output_path.parent / snapshot_path

    snapshot = gather_workspace_snapshot(root)
    snapshot_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")

    diff_text = git_diff_text(root, args.cached, args.commit)
    report_text = build_report(snapshot, diff_text)
    output_path.write_text(report_text, encoding="utf-8")

    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()
