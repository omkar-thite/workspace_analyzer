import argparse
import ast
import json
from pathlib import Path
from typing import Any


ROUTE_METHODS = {"get", "post", "put", "patch", "delete", "options", "head"}
STRIPPED_CALLS = {
    "execute",
    "scalars",
    "commit",
    "refresh",
    "add",
    "delete",
    "Depends",
    "get",
    "post",
    "patch",
}
INFRA_LOCALS = {"db", "session", "conn", "cursor", "result"}


class FileContext:
    def __init__(self, file_path: Path, root: Path, tree: ast.AST):
        self.file_path = file_path
        self.root = root
        self.tree = tree
        self.module = self._module_name()
        self.imported_symbols: dict[str, str] = {}
        self.imported_modules: dict[str, str] = {}
        self.local_top_level: set[str] = set()

    def _module_name(self) -> str:
        rel = self.file_path.relative_to(self.root).with_suffix("")
        parts = list(rel.parts)
        if parts and parts[-1] == "__init__":
            parts = parts[:-1]
        return ".".join(parts)


def discover_python_files(root: Path) -> list[Path]:
    files = [
        path
        for path in root.rglob("*.py")
        if ".git" not in path.parts and ".venv" not in path.parts and "__pycache__" not in path.parts
    ]
    return sorted(files)


def parse_workspace(root: Path) -> list[FileContext]:
    contexts: list[FileContext] = []
    for path in discover_python_files(root):
        try:
            code = path.read_text(encoding="utf-8")
            tree = ast.parse(code)
            contexts.append(FileContext(path, root, tree))
        except (OSError, SyntaxError):
            continue
    return contexts


def collect_top_level_symbols(contexts: list[FileContext]) -> dict[str, str]:
    symbol_to_key: dict[str, str] = {}
    for ctx in contexts:
        for node in ctx.tree.body:
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                ctx.local_top_level.add(node.name)
                if ctx.module:
                    symbol_to_key[f"{ctx.module}.{node.name}"] = f"{ctx.module}.{node.name}"
                else:
                    symbol_to_key[node.name] = node.name
    return symbol_to_key


def resolve_relative_module(current_module: str, module: str | None, level: int) -> str:
    if level == 0:
        return module or ""

    parts = current_module.split(".") if current_module else []
    keep = max(0, len(parts) - level)
    base = parts[:keep]
    if module:
        base.extend(module.split("."))
    return ".".join(p for p in base if p)


def index_imports(contexts: list[FileContext], all_top_level: dict[str, str]) -> None:
    known_modules = {ctx.module for ctx in contexts}

    for ctx in contexts:
        for node in ctx.tree.body:
            if isinstance(node, ast.ImportFrom):
                resolved_module = resolve_relative_module(ctx.module, node.module, node.level)
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    candidate = f"{resolved_module}.{alias.name}" if resolved_module else alias.name
                    if candidate in all_top_level:
                        ctx.imported_symbols[local_name] = all_top_level[candidate]
                    else:
                        ctx.imported_symbols[local_name] = candidate
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    local_name = alias.asname or alias.name
                    if alias.name in known_modules:
                        ctx.imported_modules[local_name] = alias.name


def call_base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ast.unparse(node)


def assignment_targets(target: ast.AST) -> set[str]:
    names: set[str] = set()
    if isinstance(target, ast.Name):
        names.add(target.id)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for elt in target.elts:
            names.update(assignment_targets(elt))
    return names


def infer_return_type(node: ast.AST | None) -> str:
    if node is None:
        return "NoneType"
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    if isinstance(node, ast.Name):
        return "symbol"
    if isinstance(node, ast.Call):
        return "call_result"
    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Tuple):
        return "tuple"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.Set):
        return "set"
    if isinstance(node, ast.Lambda):
        return "function"
    if isinstance(node, ast.BinOp):
        return "expression"
    return type(node).__name__


def return_repr(node: ast.AST | None) -> str:
    if node is None:
        return "None"
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return ast.unparse(node)


def function_scope_walk(func_node: ast.AST):
    def _walk(node: ast.AST):
        if node is not func_node and isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
        ):
            return
        yield node
        for child in ast.iter_child_nodes(node):
            yield from _walk(child)

    yield from _walk(func_node)


def referenced_name_nodes(node: ast.AST) -> set[str]:
    refs: set[str] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.Name):
            refs.add(inner.id)
    return refs


def canonicalize_name(
    expr: ast.AST,
    ctx: FileContext,
    local_symbols: dict[str, str],
    fallback_to_text: bool = True,
) -> str:
    if isinstance(expr, ast.Name):
        if expr.id in local_symbols:
            return local_symbols[expr.id]
        if expr.id in ctx.imported_symbols:
            return ctx.imported_symbols[expr.id]
        if ctx.module and expr.id in ctx.local_top_level:
            return f"{ctx.module}.{expr.id}"
        return expr.id if fallback_to_text else ""

    if isinstance(expr, ast.Attribute):
        if isinstance(expr.value, ast.Name) and expr.value.id in ctx.imported_modules:
            return f"{ctx.imported_modules[expr.value.id]}.{expr.attr}"
        if isinstance(expr.value, ast.Name) and expr.value.id in local_symbols:
            return f"{local_symbols[expr.value.id]}.{expr.attr}"
        return ast.unparse(expr) if fallback_to_text else ""

    return ast.unparse(expr) if fallback_to_text else ""


def is_pydantic_schema(class_node: ast.ClassDef, ctx: FileContext) -> bool:
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            if base.id == "BaseModel":
                return True
            imported = ctx.imported_symbols.get(base.id, "")
            if imported.endswith(".BaseModel") or imported == "BaseModel":
                return True
        elif isinstance(base, ast.Attribute) and base.attr == "BaseModel":
            return True
    return False


def annotation_optional_and_base(annotation: ast.AST) -> tuple[bool, str]:
    if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
        left_text = ast.unparse(annotation.left)
        right_text = ast.unparse(annotation.right)
        if right_text == "None":
            return True, left_text
        if left_text == "None":
            return True, right_text
        return False, ast.unparse(annotation)

    if isinstance(annotation, ast.Subscript) and isinstance(annotation.value, ast.Name):
        if annotation.value.id in {"Optional", "typing.Optional"}:
            return True, ast.unparse(annotation.slice)
        if annotation.value.id in {"Union", "typing.Union"} and isinstance(annotation.slice, ast.Tuple):
            parts = [ast.unparse(elt) for elt in annotation.slice.elts]
            filtered = [p for p in parts if p != "None"]
            if len(filtered) != len(parts):
                if filtered:
                    return True, " | ".join(filtered)
                return True, "Any"

    return False, ast.unparse(annotation)


def field_constraints(value: ast.AST | None) -> str:
    if not isinstance(value, ast.Call):
        return ""

    base = call_base_name(value.func)
    if base != "Field":
        return ""

    min_len = None
    max_len = None
    min_val = None
    max_val = None

    for kw in value.keywords:
        if kw.arg == "min_length" and isinstance(kw.value, ast.Constant):
            min_len = kw.value.value
        elif kw.arg == "max_length" and isinstance(kw.value, ast.Constant):
            max_len = kw.value.value
        elif kw.arg in {"ge", "gt", "min_value"} and isinstance(kw.value, ast.Constant):
            min_val = kw.value.value
        elif kw.arg in {"le", "lt", "max_value"} and isinstance(kw.value, ast.Constant):
            max_val = kw.value.value

    if min_len is not None and max_len is not None:
        return f"[{min_len}-{max_len}]"
    if min_len is not None:
        return f"[{min_len}+]"
    if max_len is not None:
        return f"[{max_len}]"
    if min_val is not None and max_val is not None:
        return f"[{min_val}-{max_val}]"
    if min_val is not None:
        return f"[{min_val}+]"
    if max_val is not None:
        return f"[{max_val}]"
    return ""


def extract_schema_fields(class_node: ast.ClassDef) -> str:
    fields: list[str] = []
    for stmt in class_node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            optional, base_type = annotation_optional_and_base(stmt.annotation)
            suffix = "?" if optional else ""
            constraints = field_constraints(stmt.value)
            fields.append(f"{stmt.target.id}:{base_type}{suffix}{constraints}")
    return ", ".join(fields)


def parse_http_exception_status(call: ast.Call) -> int | None:
    for kw in call.keywords:
        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, int):
            return kw.value.value

    if call.args:
        first = call.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, int):
            return first.value
    return None


def conditional_http_raise_codes(func_node: ast.AST) -> list[int]:
    codes: set[int] = set()

    def walk(node: ast.AST, conditional_depth: int) -> None:
        next_depth = conditional_depth
        if isinstance(node, (ast.If, ast.Match)):
            next_depth += 1

        if isinstance(node, ast.Raise) and next_depth > 0 and isinstance(node.exc, ast.Call):
            call = node.exc
            base = call_base_name(call.func)
            if base == "HTTPException":
                code = parse_http_exception_status(call)
                if code is not None:
                    codes.add(code)

        for child in ast.iter_child_nodes(node):
            walk(child, next_depth)

    walk(func_node, 0)
    return sorted(codes)


def extract_function_data(node: ast.AST) -> dict[str, Any]:
    local_vars: set[str] = set()
    stripped_assigned_vars: set[str] = set()
    returns: list[str] = []
    calls: set[str] = set()

    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        args = node.args.args if hasattr(node, "args") else []
        for arg in args:
            if arg.arg not in INFRA_LOCALS:
                local_vars.add(arg.arg)

    for child in function_scope_walk(node):
        if isinstance(child, ast.Assign):
            assigned_names: set[str] = set()
            for target in child.targets:
                assigned_names.update(assignment_targets(target))
            for name in assigned_names:
                if name not in INFRA_LOCALS:
                    local_vars.add(name)

            if isinstance(child.value, ast.Call):
                base = call_base_name(child.value.func)
                if base in STRIPPED_CALLS:
                    stripped_assigned_vars.update(assigned_names)

        elif isinstance(child, ast.AnnAssign):
            if isinstance(child.target, ast.Name) and child.target.id not in INFRA_LOCALS:
                local_vars.add(child.target.id)

            if isinstance(child.value, ast.Call):
                base = call_base_name(child.value.func)
                if base in STRIPPED_CALLS and isinstance(child.target, ast.Name):
                    stripped_assigned_vars.add(child.target.id)

        elif isinstance(child, ast.Return):
            returns.append(f"{return_repr(child.value)}:{infer_return_type(child.value)}")

        elif isinstance(child, ast.Call):
            base = call_base_name(child.func)
            if base in {"where", "filter"}:
                arg_refs: set[str] = set()
                for arg in child.args:
                    arg_refs.update(referenced_name_nodes(arg))
                for kw in child.keywords:
                    arg_refs.update(referenced_name_nodes(kw.value))

                for ref in sorted(arg_refs):
                    if ref in local_vars and ref not in INFRA_LOCALS:
                        calls.add(f"{base}:{ref}")
                continue

            if base in STRIPPED_CALLS:
                continue

            calls.add(base)

    clean_locals = sorted(name for name in local_vars if name not in stripped_assigned_vars and name not in INFRA_LOCALS)
    return {
        "locals": clean_locals,
        "returns": returns,
        "calls": sorted(calls),
    }


def route_decorator_data(node: ast.AST) -> tuple[str, str, ast.Call] | None:
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        return None

    method = node.func.attr.lower()
    if method not in ROUTE_METHODS:
        return None

    path_value = ""
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        path_value = node.args[0].value

    return method.upper(), path_value, node


def decorator_keyword(call: ast.Call, name: str) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == name:
            return kw.value
    return None


def status_code_from_decorator(method: str, call: ast.Call) -> int:
    value = decorator_keyword(call, "status_code")
    if isinstance(value, ast.Constant) and isinstance(value.value, int):
        return value.value

    if method == "POST":
        return 201
    return 200


def short_symbol(symbol: str) -> str:
    return symbol.split(".")[-1] if symbol else ""


def function_symbols_from_class(ctx: FileContext, class_node: ast.ClassDef) -> dict[str, ast.AST]:
    symbols: dict[str, ast.AST] = {}
    for child in class_node.body:
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            key = f"{ctx.module}.{class_node.name}.{child.name}" if ctx.module else f"{class_node.name}.{child.name}"
            symbols[key] = child
    return symbols


def gather_workspace_snapshot(root: Path) -> dict[str, Any]:
    contexts = parse_workspace(root)
    all_top_level = collect_top_level_symbols(contexts)
    index_imports(contexts, all_top_level)

    schemas: dict[str, str] = {}
    functions: dict[str, dict[str, Any]] = {}
    routes: dict[str, str] = {}

    # First extraction pass: collect schemas and functions/routes.
    for ctx in contexts:
        local_symbols = {name: f"{ctx.module}.{name}" if ctx.module else name for name in ctx.local_top_level}

        for node in ctx.tree.body:
            if isinstance(node, ast.ClassDef):
                if is_pydantic_schema(node, ctx):
                    schema_key = f"{ctx.module}.{node.name}" if ctx.module else node.name
                    schemas[schema_key] = extract_schema_fields(node)

                for fn_key, fn_node in function_symbols_from_class(ctx, node).items():
                    functions[fn_key] = extract_function_data(fn_node)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_key = f"{ctx.module}.{node.name}" if ctx.module else node.name
                functions[fn_key] = extract_function_data(node)

                for decorator in node.decorator_list:
                    route_meta = route_decorator_data(decorator)
                    if route_meta is None:
                        continue

                    method, path, call_node = route_meta
                    input_symbol = ""
                    for arg in node.args.args:
                        if arg.annotation is None:
                            continue
                        resolved = canonicalize_name(arg.annotation, ctx, local_symbols)
                        if resolved in schemas:
                            input_symbol = short_symbol(resolved)
                            break

                    response_model_node = decorator_keyword(call_node, "response_model")
                    output_symbol = ""
                    if response_model_node is not None:
                        resolved_out = canonicalize_name(response_model_node, ctx, local_symbols)
                        output_symbol = short_symbol(resolved_out)

                    base_status = status_code_from_decorator(method, call_node)
                    error_codes = conditional_http_raise_codes(node)
                    codes_text = ", ".join([str(base_status)] + [f"{code}?" for code in error_codes])

                    routes[fn_key] = (
                        f"{method} {path}  in:{input_symbol or '-'}  out:{output_symbol or '-'}({codes_text})"
                    )

    user_symbols = set(schemas.keys()) | set(functions.keys())

    reverse_dep: dict[str, set[str]] = {key: set() for key in user_symbols}

    # Second pass: build reverse dependency index from annotations and call sites.
    for ctx in contexts:
        local_symbols = {name: f"{ctx.module}.{name}" if ctx.module else name for name in ctx.local_top_level}

        def add_dep(target: str, source: str) -> None:
            if target in reverse_dep:
                reverse_dep[target].add(source)

        for node in ctx.tree.body:
            if isinstance(node, ast.ClassDef):
                schema_key = f"{ctx.module}.{node.name}" if ctx.module else node.name

                if schema_key in schemas:
                    for base in node.bases:
                        base_key = canonicalize_name(base, ctx, local_symbols)
                        add_dep(base_key, schema_key)

                for child in node.body:
                    if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        continue
                    fn_key = (
                        f"{ctx.module}.{node.name}.{child.name}"
                        if ctx.module
                        else f"{node.name}.{child.name}"
                    )
                    if fn_key not in functions:
                        continue

                    for arg in child.args.args:
                        if arg.annotation is None:
                            continue
                        ann_key = canonicalize_name(arg.annotation, ctx, local_symbols)
                        add_dep(ann_key, fn_key)

                    if child.returns is not None:
                        ann_key = canonicalize_name(child.returns, ctx, local_symbols)
                        add_dep(ann_key, fn_key)

                    for call_node in function_scope_walk(child):
                        if isinstance(call_node, ast.Call):
                            call_key = canonicalize_name(call_node.func, ctx, local_symbols)
                            add_dep(call_key, fn_key)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn_key = f"{ctx.module}.{node.name}" if ctx.module else node.name
                if fn_key not in functions:
                    continue

                for arg in node.args.args:
                    if arg.annotation is None:
                        continue
                    ann_key = canonicalize_name(arg.annotation, ctx, local_symbols)
                    add_dep(ann_key, fn_key)

                if node.returns is not None:
                    ann_key = canonicalize_name(node.returns, ctx, local_symbols)
                    add_dep(ann_key, fn_key)

                for decorator in node.decorator_list:
                    route_meta = route_decorator_data(decorator)
                    if route_meta is None:
                        continue
                    _, _, call_node = route_meta
                    response_model_node = decorator_keyword(call_node, "response_model")
                    if response_model_node is not None:
                        model_key = canonicalize_name(response_model_node, ctx, local_symbols)
                        add_dep(model_key, fn_key)

                for call_node in function_scope_walk(node):
                    if isinstance(call_node, ast.Call):
                        call_key = canonicalize_name(call_node.func, ctx, local_symbols)
                        add_dep(call_key, fn_key)

    snapshot = {
        "routes": dict(sorted(routes.items())),
        "schemas": dict(sorted(schemas.items())),
        "functions": dict(sorted(functions.items())),
        "reverse_dep": {k: sorted(v) for k, v in sorted(reverse_dep.items()) if v},
    }
    return snapshot


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate workspace static snapshot")
    parser.add_argument("target", nargs="?", default=".", help="Target directory to analyze")
    parser.add_argument(
        "--output",
        default="snapshot.json",
        help="Snapshot file path (default: target/snapshot.json)",
    )
    return parser.parse_args()

def main() -> None:
    args = parse_args()
    target = Path(args.target).resolve()
    output_path = Path(args.output)
    if not output_path.is_absolute():
        output_path = target / output_path

    snapshot = gather_workspace_snapshot(target)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=False), encoding="utf-8")


if __name__ == "__main__":
    main()
