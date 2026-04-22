# AST Analyzer

AST Analyzer is a small Python toolchain for building a static snapshot of a codebase and turning a git diff into a plain-text impact report.

It is designed for test-impact analysis: given a snapshot of known symbols and the current diff, it identifies modified symbols, traverses reverse dependencies, and prints the affected routes, schemas, and functions.

## What It Produces

The report is written as plain text with these sections:

- `GIT DIFF:` changed lines grouped by file, with file paths shown before their `+`/`-` changes
- `CHANGED FILES:` list of files that were modified
- `DELETED SYMBOLS:` symbols that appear only in removed diff lines
- `AFFECTED ROUTES:` impacted route entries from the snapshot
- `AFFECTED SCHEMAS:` impacted schema entries from the snapshot
- `AFFECTED FUNCTIONS:` impacted function entries from the snapshot

## Files

- [main.py](main.py): scans the workspace and generates `snapshot.json`
- [snapshot.json](snapshot.json): the static symbol graph used for impact analysis
- [test_impact_calculator.py](test_impact_calculator.py): reads a snapshot plus a diff and prints the report to stdout
- [generate_affected_files_report.py](generate_affected_files_report.py): one-command automation that regenerates the snapshot, reads git diff, and writes the report to a text file

## How It Works

1. The workspace is scanned and `snapshot.json` is regenerated.
2. The git diff is read from the working tree or from staged changes.
3. Changed lines are matched against known symbol names from the snapshot.
4. Matching symbols are expanded through `reverse_dep` with a depth cap of 3 hops.
5. The final report is emitted as text.

Deleted symbols are handled separately so stale payloads are not pulled from the snapshot.

## Usage

### Generate the snapshot only

```bash
python3 main.py .
```

This writes a fresh `snapshot.json` for the current workspace.

### Generate the report from a diff on stdin

```bash
git diff | python3 test_impact_calculator.py
```

Use `--diff-file` if you already saved a diff to disk:

```bash
python3 test_impact_calculator.py --diff-file /tmp/changes.diff
```

### Generate the snapshot and report in one command

```bash
python3 generate_affected_files_report.py --output affected_files.txt
```

That command:

- regenerates `snapshot.json`
- reads `git diff` automatically
- excludes `snapshot.json` from the diff
- writes the final report to `affected_files.txt`

To analyze staged changes instead of the working tree, add `--cached`:

```bash
python3 generate_affected_files_report.py --cached --output affected_files.txt
```

To diff against a specific commit (shows changes in that commit vs its parent):

```bash
python3 generate_affected_files_report.py --commit abc123 --output affected_files.txt
python3 generate_affected_files_report.py --commit HEAD --output affected_files.txt
python3 generate_affected_files_report.py --commit HEAD~3 --output affected_files.txt
```

## Output Format Example

```text
GIT DIFF:
/schema.py
+    postgres_user: str
+    postgres_password: SecretStr
/database.py
+from config import settings

CHANGED FILES:
schema.py
database.py

DELETED SYMBOLS:
users.schemas.UserCreate — was referenced by [users.router.create_user_api]

AFFECTED ROUTES:
# users/router.py
POST /users  create_user_api  in:UserCreate  out:UserResponse(201, 400?, 404?)

AFFECTED SCHEMAS:
# users/schemas.py
UserCreate: ...

AFFECTED FUNCTIONS:
# users/router.py
{'locals': [...], 'returns': [...], 'calls': [...]} 
```

The exact payload shape depends on what was captured in `snapshot.json`.

## Requirements

- Python 3.12+
- A git repository if you want automatic diff collection

## Notes

- The diff parser only considers added and removed lines.
- Context lines are intentionally ignored.
- Reverse dependency traversal is capped at 3 hops to avoid runaway expansion.

### Ignore Files

Files can be excluded from analysis using ignore patterns in:

- `.gitignore` — standard git ignore patterns
- `.cursorignore` — cursor-specific ignore patterns
- `.analyzeignore` — analyzer-specific ignore patterns

Patterns support:
- Directory patterns (e.g., `tests/`, `docs/`)
- Exact file paths (e.g., `legacy.py`)
- Filename matches (e.g., `*.generated.py`)

Ignored files are excluded from both the workspace snapshot and the git diff.
