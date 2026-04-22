"""Tests for test_impact_calculator.py - Impact calculation from diffs."""
import json
import sys
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from test_impact_calculator import (
    all_known_symbol_keys,
    build_report,
    changed_diff_only_text,
    diff_change_lines,
    extract_file_changes,
    extract_modified_symbols,
    impacted_by_type,
    key_variants,
    load_snapshot,
    namespace_to_file_path,
    parse_args,
    payload_entry,
    read_diff_text,
    render_deleted_section,
    render_file_changes,
    render_section,
    symbol_in_line,
    traverse_reverse_deps,
)


class TestParseArgs:
    """Tests for parse_args function."""

    def test_default_values(self):
        # Save original argv
        original = sys.argv
        try:
            sys.argv = ["prog", "--snapshot", "custom.json"]
            args = parse_args()
            assert args.snapshot == "custom.json"
            assert args.diff_file is None
        finally:
            sys.argv = original

    def test_diff_file_argument(self, monkeypatch):
        original = sys.argv
        try:
            sys.argv = ["prog", "--diff-file", "mydiff.txt"]
            args = parse_args()
            assert args.diff_file == "mydiff.txt"
        finally:
            sys.argv = original


class TestLoadSnapshot:
    """Tests for load_snapshot function."""

    def test_valid_json(self, tmp_path):
        snapshot_file = tmp_path / "snapshot.json"
        data = {"routes": {"a.b": "route"}, "schemas": {}, "functions": {}}
        snapshot_file.write_text(json.dumps(data))

        result = load_snapshot(snapshot_file)
        assert result == data

    def test_invalid_json(self, tmp_path):
        snapshot_file = tmp_path / "snapshot.json"
        snapshot_file.write_text("{invalid}")

        with pytest.raises(SystemExit, match="Invalid JSON"):
            load_snapshot(snapshot_file)

    def test_missing_file(self, tmp_path):
        snapshot_file = tmp_path / "nonexistent.json"
        with pytest.raises(SystemExit, match="Cannot read snapshot"):
            load_snapshot(snapshot_file)


class TestReadDiffText:
    """Tests for read_diff_text function."""

    def test_read_from_file(self, tmp_path):
        diff_file = tmp_path / "diff.txt"
        diff_file.write_text("diff --git a/test.py b/test.py")

        result = read_diff_text(str(diff_file))
        assert "diff --git" in result

    def test_file_too_large(self, tmp_path):
        diff_file = tmp_path / "large.txt"
        # Write more than 10MB
        diff_file.write_text("x" * (11 * 1024 * 1024))

        with pytest.raises(SystemExit, match="too large"):
            read_diff_text(str(diff_file))

    def test_missing_file(self):
        with pytest.raises(SystemExit, match="Cannot read diff file"):
            read_diff_text("/nonexistent/path.diff")


class TestDiffChangeLines:
    """Tests for diff_change_lines function."""

    def test_separates_plus_minus(self):
        diff = """--- a/test.py
+++ b/test.py
@@ -1,2 +1,3 @@
-old
+new
+added
"""
        plus, minus = diff_change_lines(diff)
        assert "new" in plus
        assert "added" in plus
        assert "old" in minus

    def test_ignores_headers(self):
        diff = """+++ b/test.py
--- a/test.py
+added
-removed
"""
        plus, minus = diff_change_lines(diff)
        assert "added" in plus
        assert "removed" in minus
        assert "+++ b/test.py" not in plus
        assert "--- a/test.py" not in minus


class TestChangedDiffOnlyText:
    """Tests for changed_diff_only_text function."""

    def test_filters_headers(self):
        diff = """diff --git a/test.py b/test.py
index 1234567..89abcdef 100644
--- a/test.py
+++ b/test.py
+added
-removed
"""
        result = changed_diff_only_text(diff)
        assert "diff --git" not in result
        assert "index " not in result
        assert "+added" in result
        assert "-removed" in result


class TestExtractFileChanges:
    """Tests for extract_file_changes function."""

    def test_single_file(self):
        diff = """diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1 +1,2 @@
-old
+new
+added
"""
        result = extract_file_changes(diff)
        assert "src/main.py" in result

    def test_multiple_files(self):
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
+change a
diff --git a/b.py b/b.py
--- b/b.py
+++ b/b.py
+change b
"""
        result = extract_file_changes(diff)
        assert "a.py" in result
        assert "b.py" in result


class TestRenderFileChanges:
    """Tests for render_file_changes function."""

    def test_empty(self):
        result = render_file_changes({})
        assert result == ""

    def test_single_file(self):
        result = render_file_changes({"test.py": ["+added", "-removed"]})
        assert "test.py" in result
        assert "+added" in result


class TestAllKnownSymbolKeys:
    """Tests for all_known_symbol_keys function."""

    def test_combines_all_types(self):
        snapshot = {
            "routes": {"api.users": "route"},
            "schemas": {"User": "schema"},
            "functions": {"helper": "func"},
        }
        result = all_known_symbol_keys(snapshot)
        assert result == {"api.users", "User", "helper"}

    def test_empty_snapshot(self):
        result = all_known_symbol_keys({})
        assert result == set()


class TestKeyVariants:
    """Tests for key_variants function."""

    def test_simple_key(self):
        result = key_variants("func")
        assert "func" in result

    def test_namespaced_key(self):
        result = key_variants("module.sub.func")
        assert "func" in result
        assert "sub.func" in result
        assert "module.sub.func" in result


class TestSymbolInLine:
    """Tests for symbol_in_line function."""

    def test_exact_match(self):
        assert symbol_in_line("func", "def func():") is True

    def test_no_partial_match(self):
        assert symbol_in_line("func", "def function():") is False

    def test_word_boundary(self):
        assert symbol_in_line("get", "value = get(user)") is True
        assert symbol_in_line("get", "if get == fallback:") is True

    def test_underscore_handling(self):
        assert symbol_in_line("get_user", "get_user()") is True
        assert symbol_in_line("get", "get_user()") is False


class TestExtractModifiedSymbols:
    """Tests for extract_modified_symbols function."""

    def test_finds_modified_symbol(self):
        plus_lines = ["def my_func():", "pass"]
        minus_lines = ["def my_func():", "pass"]
        known = {"module.my_func"}

        modified, deleted = extract_modified_symbols(plus_lines, minus_lines, known)
        assert "module.my_func" in modified

    def test_finds_deleted_symbol(self):
        plus_lines = ["def new_func():", "pass"]
        minus_lines = ["module.old_func = removed_impl", "pass"]
        known = {"module.old_func"}

        modified, deleted = extract_modified_symbols(plus_lines, minus_lines, known)
        assert "module.old_func" in deleted


class TestTraverseReverseDeps:
    """Tests for traverse_reverse_deps function."""

    def test_no_deps(self):
        result = traverse_reverse_deps({"a"}, {})
        assert result == {"a"}

    def test_single_level(self):
        reverse_dep = {"a": ["b", "c"]}
        result = traverse_reverse_deps({"a"}, reverse_dep)
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_max_depth(self):
        reverse_dep = {"a": ["b"], "b": ["c"], "c": ["d"]}
        result = traverse_reverse_deps({"a"}, reverse_dep, max_depth=1)
        assert "a" in result
        assert "b" in result
        assert "c" not in result


class TestNamespaceToFilePath:
    """Tests for namespace_to_file_path function."""

    def test_simple_name(self):
        assert namespace_to_file_path("func") == "func.py"

    def test_namespaced(self):
        assert namespace_to_file_path("module.func") == "module.py"

    def test_deeply_nested(self):
        assert namespace_to_file_path("a.b.c.func") == "a/b/c.py"


class TestPayloadEntry:
    """Tests for payload_entry function."""

    def test_string_payload(self):
        result = payload_entry("key", "value")
        assert result == "value"

    def test_dict_payload(self):
        result = payload_entry("key", {"a": 1})
        assert result == '{"a": 1}'


class TestImpactedByType:
    """Tests for impacted_by_type function."""

    def test_separates_by_type(self):
        snapshot = {
            "routes": {"api.users": "GET /users"},
            "schemas": {"User": '{"name": "str"}'},
            "functions": {"helper": "def helper()"},
        }
        impacted = {"api.users", "User", "helper"}

        routes, schemas, functions = impacted_by_type(impacted, snapshot)
        assert len(routes) == 1
        assert len(schemas) == 1
        assert len(functions) == 1


class TestRenderSection:
    """Tests for render_section function."""

    def test_empty(self):
        result = render_section([])
        assert result == ""

    def test_single_entry(self):
        result = render_section([("symbol", "payload")])
        assert "symbol" in result
        assert "payload" in result


class TestRenderDeletedSection:
    """Tests for render_deleted_section function."""

    def test_empty(self):
        result = render_deleted_section(set(), {})
        assert result == ""

    def test_with_references(self):
        deleted = {"old_func"}
        reverse_dep = {"old_func": ["used_by"]}
        result = render_deleted_section(deleted, reverse_dep)
        assert "old_func" in result
        assert "used_by" in result


class TestBuildReport:
    """Tests for build_report function."""

    def test_empty_diff(self):
        snapshot = {
            "routes": {},
            "schemas": {},
            "functions": {},
            "reverse_dep": {},
        }
        result = build_report(snapshot, "")
        assert "GIT DIFF:" in result
        assert "CHANGED FILES:" in result

    def test_with_changes(self):
        snapshot = {
            "routes": {"api.test": "GET /test"},
            "schemas": {},
            "functions": {},
            "reverse_dep": {},
        }
        diff = """diff --git a/api.py b/api.py
--- a/api.py
+++ b/api.py
@@ -1 +1,2 @@
-def api():
+def api():
+    pass
"""
        result = build_report(snapshot, diff)
        assert "api.py" in result