## Reads the workspace and builds a graph of classes/functions and their relationships. 

import json
import sys
import argparse
from pathlib import Path
from typing import Any

import ast

with open("code.txt") as f:
    code = f.read()

tree = ast.parse(code)
        
     
# for node in ast.walk(tree):
#     if isinstance(node, ast.FunctionDef):
#         print(f"Found function: {node.name} at line {node.lineno}")

# Visitor pattern — more structured
class FunctionAnalyzer(ast.NodeVisitor):
    
    def __init__(self):
        super().__init__()
        self.name = ""
        self.locals = set()
        self.returns = []
        self.calls = []

    def __str__(self):
        return f"Name: {self.name}, Locals: {self.locals}, Returns: {self.returns}, Calls: {self.calls}"

    def visit_FunctionDef(self, node):
        self.name = node.name
        self.locals = self.return_locals(node)
        self.returns = self.return_names(node)
        self.calls = self.return_calls(node)
        return self

    def visit_AsyncFunctionDef(self, node):
        self.name = node.name
        self.locals = self.return_locals(node)
        self.returns = self.return_names(node)
        self.calls = self.return_calls(node)
        return self

    def visit_Lambda(self, node):
        return self.analyze_lambda(node)

    def analyze_lambda(self, node, label=None):
        self.name = label or f"<lambda@L{node.lineno}:C{node.col_offset}>"
        self.locals = {arg.arg for arg in node.args.args}
        self.returns = [self._build_return_entry(node.body)]
        self.calls = self.return_calls(node)
        return self
    
    def return_locals(self, func_node):
        local_vars = {arg.arg for arg in func_node.args.args}

        def walk_without_nested_scopes(node):
            if node is not func_node and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
            ):
                return
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        local_vars.add(target.id)
            for child in ast.iter_child_nodes(node):
                walk_without_nested_scopes(child)

        walk_without_nested_scopes(func_node)
        return local_vars or ''
        
    def return_names(self, func_node):
        returns = []

        def walk_without_nested_scopes(node):
            if node is not func_node and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
            ):
                return

            if isinstance(node, ast.Return):
                returns.append(self._build_return_entry(node.value))

            for child in ast.iter_child_nodes(node):
                walk_without_nested_scopes(child)

        
        walk_without_nested_scopes(func_node)
        return returns

    def return_calls(self, func_node):
        calls = set()

        def walk_without_nested_scopes(node):
            if node is not func_node and isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)
            ):
                return

            if isinstance(node, ast.Call):
                calls.add(self._call_name(node.func))

            for child in ast.iter_child_nodes(node):
                walk_without_nested_scopes(child)

        walk_without_nested_scopes(func_node)
        return sorted(calls)

    def _build_return_entry(self, value_node):
        return {
            self._return_value_repr(value_node): self._infer_return_type(value_node),
        }

    def _return_value_repr(self, value_node):
        if value_node is None:
            return None
        if isinstance(value_node, ast.Name):
            return value_node.id
        if isinstance(value_node, ast.Constant):
            return value_node.value
        return ast.unparse(value_node)

    def _infer_return_type(self, value_node):
        if value_node is None:
            return "NoneType"
        if isinstance(value_node, ast.Constant):
            return type(value_node.value).__name__
        if isinstance(value_node, ast.Name):
            return "symbol"
        if isinstance(value_node, ast.Call):
            return "call_result"
        if isinstance(value_node, ast.List):
            return "list"
        if isinstance(value_node, ast.Tuple):
            return "tuple"
        if isinstance(value_node, ast.Dict):
            return "dict"
        if isinstance(value_node, ast.Set):
            return "set"
        if isinstance(value_node, ast.Lambda):
            return "function"
        if isinstance(value_node, ast.BinOp):
            return "expression"
        return type(value_node).__name__

    def _call_name(self, call_func_node):
        if isinstance(call_func_node, ast.Name):
            return call_func_node.id
        if isinstance(call_func_node, ast.Attribute):
            return self._attribute_call_name(call_func_node)
        return ast.unparse(call_func_node)

    def _attribute_call_name(self, attr_node):
        # For object method calls, keep the method name only.
        # Example: result.scalars() -> scalars
        if isinstance(attr_node.value, (ast.Name, ast.Attribute)):
            return attr_node.attr

        # For chained method calls, preserve the meaningful method chain.
        # Example: result.scalars().first() -> scalars().first
        if isinstance(attr_node.value, ast.Call):
            inner_func = attr_node.value.func
            if isinstance(inner_func, ast.Attribute):
                return f"{self._attribute_call_name(inner_func)}().{attr_node.attr}"
            return attr_node.attr

        return attr_node.attr


def _format_collection(value):
    if isinstance(value, set):
        return ", ".join(sorted(str(item) for item in value))
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _format_returns(returns):
    parts = []
    for item in returns:
        if isinstance(item, dict):
            for key, value in item.items():
                parts.append(f"{key}: {value}")
        else:
            parts.append(str(item))
    return ", ".join(parts)


def _format_function_entry(func_entry):
    name, details = next(iter(func_entry.items()))
    locals_text = _format_collection(details.get("locals", ""))
    returns_text = _format_returns(details.get("returns", []))
    calls_text = _format_collection(details.get("calls", ""))
    return f"{{{name}: {{locals: {locals_text}, returns: {returns_text}, calls: {calls_text}}}}}"


class NestedFunctionAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.nested_functions = []

    def visit_FunctionDef(self, node):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func = FunctionAnalyzer().visit(child)
                self.nested_functions.append({child.name: {
                    "locals": func.locals,
                    "returns": func.returns,
                    "calls": func.calls,
                }})
            elif isinstance(child, ast.Lambda):
                label = f"<lambda@L{child.lineno}:C{child.col_offset}>"
                func = FunctionAnalyzer().analyze_lambda(child, label=label)
                self.nested_functions.append({label: {
                    "locals": func.locals,
                    "returns": func.returns,
                    "calls": func.calls,
                }})
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)


class ModuleAnalyzer(ast.NodeVisitor):
    def __init__(self):
        self.functions = []
        self.classes = []

    def visit_FunctionDef(self, node):
        func = FunctionAnalyzer().visit(node)
        self.functions.append({node.name: {
            "locals": func.locals,
            "returns": func.returns,
            "calls": func.calls,
        }})
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node):
        func = FunctionAnalyzer().visit(node)
        self.functions.append({node.name: {
            "locals": func.locals,
            "returns": func.returns,
            "calls": func.calls,
        }})
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.classes.append(node.name)
        self.generic_visit(node)

analyzer = ModuleAnalyzer()
analyzer.visit(tree)
nested_analyzer = NestedFunctionAnalyzer()
nested_analyzer.visit(tree)
print("Functions:")
for func in analyzer.functions:
    print(_format_function_entry(func))

