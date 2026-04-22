"""Tests for main.py - AST analysis and file discovery functions."""
import ast
import tempfile
from pathlib import Path

import pytest

from main import (
    FileContext,
    assignment_targets,
    call_base_name,
    discover_python_files,
    infer_return_type,
    is_pydantic_schema,
    load_ignore_patterns,
    matches_ignore,
    parse_ignore_file,
    parse_workspace,
    return_repr,
)


class TestParseIgnoreFile:
    """Tests for parse_ignore_file function."""

    def test_empty_file(self, tmp_path):
        ignore_file = tmp_path / ".analyzeignore"
        ignore_file.write_text("")
        result = parse_ignore_file(ignore_file)
        assert result == set()

    def test_comments_ignored(self, tmp_path):
        ignore_file = tmp_path / ".analyzeignore"
        ignore_file.write_text("# This is a comment\npackage/\n# Another comment\n*.pyc")
        result = parse_ignore_file(ignore_file)
        assert result == {"package/", "*.pyc"}

    def test_empty_lines_ignored(self, tmp_path):
        ignore_file = tmp_path / ".analyzeignore"
        ignore_file.write_text("\n\npackage/\n\n\n")
        result = parse_ignore_file(ignore_file)
        assert result == {"package/"}

    def test_nonexistent_file(self, tmp_path):
        ignore_file = tmp_path / "nonexistent.txt"
        result = parse_ignore_file(ignore_file)
        assert result == set()


class TestLoadIgnorePatterns:
    """Tests for load_ignore_patterns function."""

    def test_loads_multiple_ignore_files(self, tmp_path):
        (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n")
        (tmp_path / ".cursorignore").write_text("node_modules/\n")
        (tmp_path / ".analyzeignore").write_text("dist/\n")

        result = load_ignore_patterns(tmp_path)
        assert result == {"*.pyc", "__pycache__/", "node_modules/", "dist/"}

    def test_missing_ignore_files_handled(self, tmp_path):
        # Only create .gitignore
        (tmp_path / ".gitignore").write_text("*.pyc\n")
        result = load_ignore_patterns(tmp_path)
        assert result == {"*.pyc"}


class TestMatchesIgnore:
    """Tests for matches_ignore function."""

    def test_exact_match(self, tmp_path):
        root = tmp_path
        patterns = {"test.py"}
        path = tmp_path / "test.py"
        assert matches_ignore(path, root, patterns) is True

    def test_prefix_match(self, tmp_path):
        root = tmp_path
        patterns = {"src/"}
        path = tmp_path / "src" / "module.py"
        assert matches_ignore(path, root, patterns) is True

    def test_filename_match(self, tmp_path):
        root = tmp_path
        patterns = {"test.pyc"}
        path = tmp_path / "test.pyc"
        assert matches_ignore(path, root, patterns) is True

    def test_no_match(self, tmp_path):
        root = tmp_path
        patterns = {"ignored.py"}
        path = tmp_path / "other.py"
        assert matches_ignore(path, root, patterns) is False

    def test_directory_pattern(self, tmp_path):
        root = tmp_path
        patterns = {"tests/"}
        path = tmp_path / "tests" / "test_main.py"
        assert matches_ignore(path, root, patterns) is True

    def test_rejects_parent_traversal_patterns(self, tmp_path):
        root = tmp_path
        patterns = {"../evil/", "/absolute/"}
        path = tmp_path / "test.py"
        # These patterns should be rejected/skipped
        assert matches_ignore(path, root, patterns) is False


class TestDiscoverPythonFiles:
    """Tests for discover_python_files function."""

    def test_finds_python_files(self, tmp_path):
        (tmp_path / "a.py").write_text("x = 1")
        (tmp_path / "b.py").write_text("y = 2")
        (tmp_path / "c.txt").write_text("not python")

        files = discover_python_files(tmp_path)
        assert len(files) == 2
        assert all(p.suffix == ".py" for p in files)

    def test_excludes_git_directory(self, tmp_path):
        git_config = tmp_path / ".git" / "config"
        git_config.parent.mkdir(parents=True, exist_ok=True)
        git_config.write_text("")
        (tmp_path / "main.py").write_text("x = 1")

        files = discover_python_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "main.py"

    def test_excludes_pycache(self, tmp_path):
        pycache_file = tmp_path / "__pycache__" / "cache.pyc"
        pycache_file.parent.mkdir(parents=True, exist_ok=True)
        pycache_file.write_text("")
        (tmp_path / "main.py").write_text("x = 1")

        files = discover_python_files(tmp_path)
        assert len(files) == 1

    def test_respects_ignore_patterns(self, tmp_path):
        (tmp_path / ".analyzeignore").write_text("ignored.py\n")
        (tmp_path / "ignored.py").write_text("x = 1")
        (tmp_path / "kept.py").write_text("y = 2")

        files = discover_python_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "kept.py"

    def test_nested_files(self, tmp_path):
        mod_file = tmp_path / "pkg" / "mod.py"
        deep_file = tmp_path / "pkg" / "sub" / "deep.py"
        mod_file.parent.mkdir(parents=True, exist_ok=True)
        deep_file.parent.mkdir(parents=True, exist_ok=True)
        mod_file.write_text("x = 1")
        deep_file.write_text("y = 2")

        files = discover_python_files(tmp_path)
        assert len(files) == 2


class TestFileContext:
    """Tests for FileContext class."""

    def test_module_name_simple(self, tmp_path):
        path = tmp_path / "module.py"
        tree = ast.parse("x = 1")
        ctx = FileContext(path, tmp_path, tree)
        assert ctx.module == "module"

    def test_module_name_nested(self, tmp_path):
        path = tmp_path / "pkg" / "module.py"
        tree = ast.parse("x = 1")
        ctx = FileContext(path, tmp_path, tree)
        assert ctx.module == "pkg.module"

    def test_module_name_init(self, tmp_path):
        path = tmp_path / "pkg" / "__init__.py"
        tree = ast.parse("x = 1")
        ctx = FileContext(path, tmp_path, tree)
        assert ctx.module == "pkg"


class TestCallBaseName:
    """Tests for call_base_name function."""

    def test_name_node(self):
        node = ast.Name(id="func", ctx=ast.Load())
        assert call_base_name(node) == "func"

    def test_attribute_node(self):
        node = ast.Attribute(
            value=ast.Name(id="obj", ctx=ast.Load()),
            attr="method",
            ctx=ast.Load(),
        )
        assert call_base_name(node) == "method"

    def test_call_node(self):
        node = ast.Call(
            func=ast.Name(id="func", ctx=ast.Load()),
            args=[],
            keywords=[],
        )
        assert call_base_name(node) == "func()"


class TestAssignmentTargets:
    """Tests for assignment_targets function."""

    def test_simple_assignment(self):
        target = ast.Name(id="x", ctx=ast.Store())
        result = assignment_targets(target)
        assert result == {"x"}

    def test_tuple_unpacking(self):
        target = ast.Tuple(
            elts=[
                ast.Name(id="x", ctx=ast.Store()),
                ast.Name(id="y", ctx=ast.Store()),
            ],
            ctx=ast.Store(),
        )
        result = assignment_targets(target)
        assert result == {"x", "y"}

    def test_list_unpacking(self):
        target = ast.List(
            elts=[
                ast.Name(id="a", ctx=ast.Store()),
                ast.Name(id="b", ctx=ast.Store()),
            ],
            ctx=ast.Store(),
        )
        result = assignment_targets(target)
        assert result == {"a", "b"}


class TestInferReturnType:
    """Tests for infer_return_type function."""

    def test_none_node(self):
        assert infer_return_type(None) == "NoneType"

    def test_constant(self):
        node = ast.Constant(value=42)
        assert infer_return_type(node) == "int"

    def test_name(self):
        node = ast.Name(id="x", ctx=ast.Load())
        assert infer_return_type(node) == "symbol"

    def test_call(self):
        node = ast.Call(
            func=ast.Name(id="func", ctx=ast.Load()),
            args=[],
            keywords=[],
        )
        assert infer_return_type(node) == "call_result"

    def test_list(self):
        node = ast.List(elts=[])
        assert infer_return_type(node) == "list"

    def test_dict(self):
        node = ast.Dict(keys=[], values=[])
        assert infer_return_type(node) == "dict"


class TestReturnRepr:
    """Tests for return_repr function."""

    def test_none(self):
        assert return_repr(None) == "None"

    def test_name(self):
        node = ast.Name(id="my_var", ctx=ast.Load())
        assert return_repr(node) == "my_var"

    def test_constant_int(self):
        node = ast.Constant(value=42)
        assert return_repr(node) == "42"

    def test_constant_string(self):
        node = ast.Constant(value="hello")
        assert return_repr(node) == "'hello'"


class TestIsPydanticSchema:
    """Tests for is_pydantic_schema function."""

    def test_direct_base_model(self):
        code = "class User(BaseModel): pass"
        tree = ast.parse(code)
        class_node = tree.body[0]
        ctx = FileContext(Path("test.py"), Path("."), tree)
        assert is_pydantic_schema(class_node, ctx) is True

    def test_imported_base_model(self):
        code = "from pydantic import BaseModel\nclass User(BaseModel): pass"
        tree = ast.parse(code)
        class_node = tree.body[1]
        ctx = FileContext(Path("test.py"), Path("."), tree)
        assert is_pydantic_schema(class_node, ctx) is True

    def test_not_pydantic(self):
        code = "class User: pass"
        tree = ast.parse(code)
        class_node = tree.body[0]
        ctx = FileContext(Path("test.py"), Path("."), tree)
        assert is_pydantic_schema(class_node, ctx) is False