{
  "routes": {},
  "schemas": {},
  "functions": {
    "main.FileContext.__init__": {
      "locals": [
        "file_path",
        "root",
        "self",
        "tree"
      ],
      "returns": [],
      "calls": [
        "_module_name",
        "set"
      ]
    },
    "main.FileContext._module_name": {
      "locals": [
        "parts",
        "rel",
        "self"
      ],
      "returns": [
        "'.'.join(parts):call_result"
      ],
      "calls": [
        "join",
        "list",
        "relative_to",
        "with_suffix"
      ]
    },
    "main.annotation_optional_and_base": {
      "locals": [
        "annotation",
        "filtered",
        "left_text",
        "parts",
        "right_text"
      ],
      "returns": [
        "(True, left_text):tuple",
        "(True, right_text):tuple",
        "(False, ast.unparse(annotation)):tuple",
        "(True, ast.unparse(annotation.slice)):tuple",
        "(True, ' | '.join(filtered)):tuple",
        "(True, 'Any'):tuple",
        "(False, ast.unparse(annotation)):tuple"
      ],
      "calls": [
        "isinstance",
        "join",
        "len",
        "unparse"
      ]
    },
    "main.assignment_targets": {
      "locals": [
        "names",
        "target"
      ],
      "returns": [
        "names:symbol"
      ],
      "calls": [
        "assignment_targets",
        "isinstance",
        "set",
        "update"
      ]
    },
    "main.call_base_name": {
      "locals": [
        "node"
      ],
      "returns": [
        "node.id:Attribute",
        "node.attr:Attribute",
        "ast.unparse(node):call_result"
      ],
      "calls": [
        "isinstance",
        "unparse"
      ]
    },
    "main.canonicalize_name": {
      "locals": [
        "ctx",
        "expr",
        "fallback_to_text",
        "local_symbols"
      ],
      "returns": [
        "local_symbols[expr.id]:Subscript",
        "ctx.imported_symbols[expr.id]:Subscript",
        "f'{ctx.module}.{expr.id}':JoinedStr",
        "expr.id if fallback_to_text else '':IfExp",
        "f'{ctx.imported_modules[expr.value.id]}.{expr.attr}':JoinedStr",
        "f'{local_symbols[expr.value.id]}.{expr.attr}':JoinedStr",
        "ast.unparse(expr) if fallback_to_text else '':IfExp",
        "ast.unparse(expr) if fallback_to_text else '':IfExp"
      ],
      "calls": [
        "isinstance",
        "unparse"
      ]
    },
    "main.collect_top_level_symbols": {
      "locals": [
        "contexts",
        "symbol_to_key"
      ],
      "returns": [
        "symbol_to_key:symbol"
      ],
      "calls": [
        "isinstance"
      ]
    },
    "main.conditional_http_raise_codes": {
      "locals": [
        "codes",
        "func_node"
      ],
      "returns": [
        "sorted(codes):call_result"
      ],
      "calls": [
        "set",
        "sorted",
        "walk"
      ]
    },
    "main.decorator_keyword": {
      "locals": [
        "call",
        "name"
      ],
      "returns": [
        "kw.value:Attribute",
        "None:NoneType"
      ],
      "calls": []
    },
    "main.discover_python_files": {
      "locals": [
        "files",
        "root"
      ],
      "returns": [
        "sorted(files):call_result"
      ],
      "calls": [
        "rglob",
        "sorted"
      ]
    },
    "main.extract_function_data": {
      "locals": [
        "arg_refs",
        "args",
        "assigned_names",
        "base",
        "calls",
        "clean_locals",
        "local_vars",
        "node",
        "returns",
        "stripped_assigned_vars"
      ],
      "returns": [
        "{'locals': clean_locals, 'returns': returns, 'calls': sorted(calls)}:dict"
      ],
      "calls": [
        "append",
        "assignment_targets",
        "call_base_name",
        "function_scope_walk",
        "hasattr",
        "infer_return_type",
        "isinstance",
        "referenced_name_nodes",
        "return_repr",
        "set",
        "sorted",
        "update"
      ]
    },
    "main.extract_schema_fields": {
      "locals": [
        "base_type",
        "class_node",
        "constraints",
        "fields",
        "optional",
        "suffix"
      ],
      "returns": [
        "', '.join(fields):call_result"
      ],
      "calls": [
        "annotation_optional_and_base",
        "append",
        "field_constraints",
        "isinstance",
        "join"
      ]
    },
    "main.field_constraints": {
      "locals": [
        "base",
        "max_len",
        "max_val",
        "min_len",
        "min_val",
        "value"
      ],
      "returns": [
        "'':str",
        "'':str",
        "f'[{min_len}-{max_len}]':JoinedStr",
        "f'[{min_len}+]':JoinedStr",
        "f'[{max_len}]':JoinedStr",
        "f'[{min_val}-{max_val}]':JoinedStr",
        "f'[{min_val}+]':JoinedStr",
        "f'[{max_val}]':JoinedStr",
        "'':str"
      ],
      "calls": [
        "call_base_name",
        "isinstance"
      ]
    },
    "main.function_scope_walk": {
      "locals": [
        "func_node"
      ],
      "returns": [],
      "calls": [
        "_walk"
      ]
    },
    "main.function_symbols_from_class": {
      "locals": [
        "class_node",
        "ctx",
        "key",
        "symbols"
      ],
      "returns": [
        "symbols:symbol"
      ],
      "calls": [
        "isinstance"
      ]
    },
    "main.gather_workspace_snapshot": {
      "locals": [
        "_",
        "all_top_level",
        "ann_key",
        "base_key",
        "base_status",
        "call_key",
        "call_node",
        "codes_text",
        "contexts",
        "error_codes",
        "fn_key",
        "functions",
        "input_symbol",
        "local_symbols",
        "method",
        "model_key",
        "output_symbol",
        "path",
        "resolved",
        "resolved_out",
        "response_model_node",
        "reverse_dep",
        "root",
        "route_meta",
        "routes",
        "schema_key",
        "schemas",
        "snapshot",
        "user_symbols"
      ],
      "returns": [
        "snapshot:symbol"
      ],
      "calls": [
        "add_dep",
        "canonicalize_name",
        "collect_top_level_symbols",
        "conditional_http_raise_codes",
        "decorator_keyword",
        "dict",
        "extract_function_data",
        "extract_schema_fields",
        "function_scope_walk",
        "function_symbols_from_class",
        "index_imports",
        "is_pydantic_schema",
        "isinstance",
        "items",
        "join",
        "keys",
        "parse_workspace",
        "route_decorator_data",
        "set",
        "short_symbol",
        "sorted",
        "status_code_from_decorator",
        "str"
      ]
    },
    "main.index_imports": {
      "locals": [
        "all_top_level",
        "candidate",
        "contexts",
        "known_modules",
        "local_name",
        "resolved_module"
      ],
      "returns": [],
      "calls": [
        "isinstance",
        "resolve_relative_module"
      ]
    },
    "main.infer_return_type": {
      "locals": [
        "node"
      ],
      "returns": [
        "'NoneType':str",
        "type(node.value).__name__:Attribute",
        "'symbol':str",
        "'call_result':str",
        "'list':str",
        "'tuple':str",
        "'dict':str",
        "'set':str",
        "'function':str",
        "'expression':str",
        "type(node).__name__:Attribute"
      ],
      "calls": [
        "isinstance",
        "type"
      ]
    },
    "main.is_pydantic_schema": {
      "locals": [
        "class_node",
        "ctx"
      ],
      "returns": [
        "True:bool",
        "True:bool",
        "True:bool",
        "False:bool"
      ],
      "calls": [
        "endswith",
        "isinstance"
      ]
    },
    "main.main": {
      "locals": [
        "args",
        "output_path",
        "snapshot",
        "target"
      ],
      "returns": [],
      "calls": [
        "Path",
        "dumps",
        "gather_workspace_snapshot",
        "is_absolute",
        "parse_args",
        "resolve",
        "write_text"
      ]
    },
    "main.parse_args": {
      "locals": [
        "parser"
      ],
      "returns": [
        "parser.parse_args():call_result"
      ],
      "calls": [
        "ArgumentParser",
        "add_argument",
        "parse_args"
      ]
    },
    "main.parse_http_exception_status": {
      "locals": [
        "call",
        "first"
      ],
      "returns": [
        "kw.value.value:Attribute",
        "first.value:Attribute",
        "None:NoneType"
      ],
      "calls": [
        "isinstance"
      ]
    },
    "main.parse_workspace": {
      "locals": [
        "code",
        "contexts",
        "root",
        "tree"
      ],
      "returns": [
        "contexts:symbol"
      ],
      "calls": [
        "FileContext",
        "append",
        "discover_python_files",
        "parse",
        "read_text"
      ]
    },
    "main.referenced_name_nodes": {
      "locals": [
        "node",
        "refs"
      ],
      "returns": [
        "refs:symbol"
      ],
      "calls": [
        "isinstance",
        "set",
        "walk"
      ]
    },
    "main.resolve_relative_module": {
      "locals": [
        "base",
        "current_module",
        "keep",
        "level",
        "module",
        "parts"
      ],
      "returns": [
        "module or '':BoolOp",
        "'.'.join((p for p in base if p)):call_result"
      ],
      "calls": [
        "extend",
        "join",
        "len",
        "max",
        "split"
      ]
    },
    "main.return_repr": {
      "locals": [
        "node"
      ],
      "returns": [
        "'None':str",
        "node.id:Attribute",
        "repr(node.value):call_result",
        "ast.unparse(node):call_result"
      ],
      "calls": [
        "isinstance",
        "repr",
        "unparse"
      ]
    },
    "main.route_decorator_data": {
      "locals": [
        "method",
        "node",
        "path_value"
      ],
      "returns": [
        "None:NoneType",
        "None:NoneType",
        "(method.upper(), path_value, node):tuple"
      ],
      "calls": [
        "isinstance",
        "lower",
        "upper"
      ]
    },
    "main.short_symbol": {
      "locals": [
        "symbol"
      ],
      "returns": [
        "symbol.split('.')[-1] if symbol else '':IfExp"
      ],
      "calls": [
        "split"
      ]
    },
    "main.status_code_from_decorator": {
      "locals": [
        "call",
        "method",
        "value"
      ],
      "returns": [
        "value.value:Attribute",
        "201:int",
        "200:int"
      ],
      "calls": [
        "decorator_keyword",
        "isinstance"
      ]
    }
  },
  "reverse_dep": {
    "main.annotation_optional_and_base": [
      "main.extract_schema_fields"
    ],
    "main.assignment_targets": [
      "main.assignment_targets",
      "main.extract_function_data"
    ],
    "main.call_base_name": [
      "main.extract_function_data",
      "main.field_constraints"
    ],
    "main.canonicalize_name": [
      "main.gather_workspace_snapshot"
    ],
    "main.collect_top_level_symbols": [
      "main.gather_workspace_snapshot"
    ],
    "main.conditional_http_raise_codes": [
      "main.gather_workspace_snapshot"
    ],
    "main.decorator_keyword": [
      "main.gather_workspace_snapshot",
      "main.status_code_from_decorator"
    ],
    "main.discover_python_files": [
      "main.parse_workspace"
    ],
    "main.extract_function_data": [
      "main.gather_workspace_snapshot"
    ],
    "main.extract_schema_fields": [
      "main.gather_workspace_snapshot"
    ],
    "main.field_constraints": [
      "main.extract_schema_fields"
    ],
    "main.function_scope_walk": [
      "main.extract_function_data",
      "main.gather_workspace_snapshot"
    ],
    "main.function_symbols_from_class": [
      "main.gather_workspace_snapshot"
    ],
    "main.gather_workspace_snapshot": [
      "main.main"
    ],
    "main.index_imports": [
      "main.gather_workspace_snapshot"
    ],
    "main.infer_return_type": [
      "main.extract_function_data"
    ],
    "main.is_pydantic_schema": [
      "main.gather_workspace_snapshot"
    ],
    "main.parse_args": [
      "main.main"
    ],
    "main.parse_workspace": [
      "main.gather_workspace_snapshot"
    ],
    "main.referenced_name_nodes": [
      "main.extract_function_data"
    ],
    "main.resolve_relative_module": [
      "main.index_imports"
    ],
    "main.return_repr": [
      "main.extract_function_data"
    ],
    "main.route_decorator_data": [
      "main.gather_workspace_snapshot"
    ],
    "main.short_symbol": [
      "main.gather_workspace_snapshot"
    ],
    "main.status_code_from_decorator": [
      "main.gather_workspace_snapshot"
    ]
  }
}