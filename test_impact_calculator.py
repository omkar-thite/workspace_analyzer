import argparse
import json
import re
import sys
from collections import deque
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute impacted test context from snapshot.json and a git diff"
    )
    parser.add_argument(
        "--snapshot",
        default="snapshot.json",
        help="Path to snapshot.json (default: snapshot.json)",
    )
    parser.add_argument(
        "--diff-file",
        help="Path to a diff file. If omitted, diff is read from stdin.",
    )
    return parser.parse_args()


def load_snapshot(snapshot_path: Path) -> dict[str, Any]:
    try:
        return json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in snapshot file: {e}")
    except OSError as e:
        raise SystemExit(f"Cannot read snapshot file: {e}")


def read_diff_text(diff_file: str | None) -> str:
    MAX_DIFF_SIZE = 10 * 1024 * 1024  # 10 MB limit
    
    if diff_file:
        path = Path(diff_file)
        try:
            with path.open("rb") as fh:
                data = fh.read(MAX_DIFF_SIZE + 1)
        except OSError as e:
            raise SystemExit(f"Cannot read diff file: {e}")
        if len(data) > MAX_DIFF_SIZE:
            raise SystemExit(
                f"Diff file too large ({len(data)} bytes). Maximum allowed: {MAX_DIFF_SIZE} bytes."
            )
        return data.decode("utf-8", errors="replace")
    
    # Avoid blocking forever when no stdin is piped.
    if sys.stdin.isatty():
        raise SystemExit(
            "No diff input detected on stdin. Pipe a git diff or pass --diff-file <path>."
        )
    
    # Read with size limit to prevent DoS
    stdin = sys.stdin.buffer
    read_chunk = stdin.read(MAX_DIFF_SIZE + 1)
    if len(read_chunk) > MAX_DIFF_SIZE:
        raise SystemExit(f"Diff input too large ({len(read_chunk)} bytes). Maximum allowed: {MAX_DIFF_SIZE} bytes.")
    
    return read_chunk.decode("utf-8", errors="replace")


def diff_change_lines(diff_text: str) -> tuple[list[str], list[str]]:
    plus_lines: list[str] = []
    minus_lines: list[str] = []

    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            plus_lines.append(line[1:])
        elif line.startswith("-"):
            minus_lines.append(line[1:])

    return plus_lines, minus_lines


def changed_diff_only_text(diff_text: str) -> str:
    changed_lines: list[str] = []
    for line in diff_text.splitlines():
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+") or line.startswith("-"):
            changed_lines.append(line)
    return "\n".join(changed_lines)


def extract_file_changes(diff_text: str) -> dict[str, list[str]]:
    """Extract file paths with their associated changed lines."""
    file_changes: dict[str, list[str]] = {}
    current_file: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("+++"):
            # Format: +++ b/path/to/file or +++ /dev/null
            path = line[4:].strip()
            if path.startswith("b/"):
                path = path[2:]
            if path and path != "/dev/null":
                current_file = path
                if current_file not in file_changes:
                    file_changes[current_file] = []
        elif current_file and (line.startswith("+") or line.startswith("-")):
            file_changes[current_file].append(line)
        elif line.startswith("diff ") or line.startswith("index "):
            # Reset on new diff header
            current_file = None

    return file_changes


def render_file_changes(file_changes: dict[str, list[str]]) -> str:
    """Render file paths with their changes."""
    if not file_changes:
        return ""

    lines: list[str] = []
    for file_path in sorted(file_changes.keys()):
        changes = file_changes[file_path]
        if changes:
            lines.append(f"{file_path}")
            lines.extend(changes)
    return "\n".join(lines)


def all_known_symbol_keys(snapshot: dict[str, Any]) -> set[str]:
    routes = set(snapshot.get("routes", {}).keys())
    schemas = set(snapshot.get("schemas", {}).keys())
    functions = set(snapshot.get("functions", {}).keys())
    return routes | schemas | functions


def key_variants(symbol_key: str) -> set[str]:
    parts = symbol_key.split(".")
    variants = {symbol_key, parts[-1]}

    # Include trailing namespace chunks to improve matching when diffs use
    # partially-qualified names.
    for size in range(2, len(parts)):
        variants.add(".".join(parts[-size:]))

    return {v for v in variants if v}


def symbol_in_line(symbol: str, line: str) -> bool:
    pattern = re.compile(rf"(?<![A-Za-z0-9_\.]){re.escape(symbol)}(?![A-Za-z0-9_\.])")
    return bool(pattern.search(line))


def extract_modified_symbols(
    plus_lines: list[str],
    minus_lines: list[str],
    known_keys: set[str],
) -> tuple[set[str], set[str]]:
    plus_text = "\n".join(plus_lines)
    minus_text = "\n".join(minus_lines)

    modified_symbols: set[str] = set()

    for key in known_keys:
        variants = key_variants(key)
        if any(symbol_in_line(variant, plus_text) for variant in variants) or any(
            symbol_in_line(variant, minus_text) for variant in variants
        ):
            modified_symbols.add(key)

    # Deleted symbols are identified only by full namespaced key and only when
    # present in deleted lines and absent from added lines.
    deleted_symbols = {
        key
        for key in known_keys
        if symbol_in_line(key, minus_text) and not symbol_in_line(key, plus_text)
    }

    return modified_symbols, deleted_symbols


def traverse_reverse_deps(
    seeds: set[str],
    reverse_dep: dict[str, list[str]],
    max_depth: int = 3,
) -> set[str]:
    visited: set[str] = set(seeds)
    queue: deque[tuple[str, int]] = deque((seed, 0) for seed in seeds)

    while queue:
        symbol, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for dep in reverse_dep.get(symbol, []):
            if dep in visited:
                continue
            visited.add(dep)
            queue.append((dep, depth + 1))

    return visited


def namespace_to_file_path(symbol_key: str) -> str:
    if "." not in symbol_key:
        return f"{symbol_key}.py"
    module_ns = symbol_key.rsplit(".", 1)[0]
    return f"{module_ns.replace('.', '/')}.py"


def payload_entry(symbol: str, payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def impacted_by_type(
    impacted_symbols: set[str],
    snapshot: dict[str, Any],
) -> tuple[list[tuple[str, str]], list[tuple[str, str]], list[tuple[str, str]]]:
    routes = snapshot.get("routes", {})
    schemas = snapshot.get("schemas", {})
    functions = snapshot.get("functions", {})

    route_entries: list[tuple[str, str]] = []
    schema_entries: list[tuple[str, str]] = []
    function_entries: list[tuple[str, str]] = []

    for symbol in sorted(impacted_symbols):
        if symbol in routes:
            route_entries.append((symbol, payload_entry(symbol, routes[symbol])))
        if symbol in schemas:
            schema_entries.append((symbol, payload_entry(symbol, schemas[symbol])))
        if symbol in functions:
            function_entries.append((symbol, payload_entry(symbol, functions[symbol])))

    return route_entries, schema_entries, function_entries


def render_section(entries: list[tuple[str, str]]) -> str:
    if not entries:
        return ""

    lines: list[str] = []
    for symbol, payload in entries:
        lines.append(f"# {namespace_to_file_path(symbol)}")
        lines.append(payload)
    return "\n".join(lines)


def render_deleted_section(
    deleted_symbols: set[str], reverse_dep: dict[str, list[str]]
) -> str:
    if not deleted_symbols:
        return ""

    lines: list[str] = []
    for symbol in sorted(deleted_symbols):
        refs = sorted(set(reverse_dep.get(symbol, [])))
        refs_text = ", ".join(refs)
        lines.append(f"{symbol} — was referenced by [{refs_text}]")
    return "\n".join(lines)


def build_report(snapshot: dict[str, Any], diff_text: str) -> str:
    plus_lines, minus_lines = diff_change_lines(diff_text)
    changed_only_diff = changed_diff_only_text(diff_text)

    # Extract changed file paths with their changes
    file_changes = extract_file_changes(diff_text)
    changed_files = set(file_changes.keys())

    known_keys = all_known_symbol_keys(snapshot)
    modified_symbols, deleted_symbols = extract_modified_symbols(
        plus_lines, minus_lines, known_keys
    )

    # Deleted symbols are handled separately and should not pull stale payloads.
    traversal_seeds = modified_symbols - deleted_symbols

    impacted_symbols = traverse_reverse_deps(
        traversal_seeds,
        snapshot.get("reverse_dep", {}),
        max_depth=3,
    )

    route_entries, schema_entries, function_entries = impacted_by_type(
        impacted_symbols,
        snapshot,
    )

    deleted_text = render_deleted_section(deleted_symbols, snapshot.get("reverse_dep", {}))
    routes_text = render_section(route_entries)
    schemas_text = render_section(schema_entries)
    functions_text = render_section(function_entries)

    output: list[str] = ["GIT DIFF:", render_file_changes(file_changes), "", "CHANGED FILES:", "\n".join(sorted(changed_files)) if changed_files else "(none)", "", "DELETED SYMBOLS:", deleted_text, "", "AFFECTED ROUTES:", routes_text, "", "AFFECTED SCHEMAS:", schemas_text, "", "AFFECTED FUNCTIONS:", functions_text]

    return "\n".join(output)


def main() -> None:
    args = parse_args()

    snapshot = load_snapshot(Path(args.snapshot))
    diff_text = read_diff_text(args.diff_file)
    print(build_report(snapshot, diff_text))


if __name__ == "__main__":
    main()
