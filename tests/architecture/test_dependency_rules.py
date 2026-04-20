import ast
import os
import pytest

DOMAIN_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "domain")
FORBIDDEN_MODULES = ("application", "infrastructure", "ui")

def get_domain_files():
    for root, _, files in os.walk(DOMAIN_DIR):
        for f in files:
            if f.endswith(".py"):
                yield os.path.join(root, f)

def check_imports(filepath):
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        pytest.fail(f"Syntax error in {filepath}: {e}")

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                base_module = alias.name.split('.')[0]
                if base_module in FORBIDDEN_MODULES:
                    violations.append(f"Line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            # 1. Check if the module path itself references a forbidden layer (e.g. from ..application import X)
            if node.module:
                base_module = node.module.split('.')[0]
                if base_module in FORBIDDEN_MODULES:
                    violations.append(f"Line {node.lineno}: from {'.' * node.level}{node.module} import ...")
            
            # 2. Check if the relative import is directly importing the forbidden layer as an alias (e.g. from .. import application)
            if node.level > 0:
                for alias in node.names:
                    if alias.name in FORBIDDEN_MODULES:
                        violations.append(f"Line {node.lineno}: from {'.' * node.level} import {alias.name}")

    return violations

def test_domain_layer_independence():
    """
    Ensures that Uncle Bob's Dependency Rule is respected:
    The Domain layer must not import from Application, Infrastructure, or UI layers.
    """
    all_violations = {}
    for filepath in get_domain_files():
        violations = check_imports(filepath)
        if violations:
            rel_path = os.path.relpath(filepath, DOMAIN_DIR)
            all_violations[rel_path] = violations

    if all_violations:
        error_msg = ["Dependency rule violations found in domain layer:\n"]
        for rel_path, violations in all_violations.items():
            error_msg.append(f"In domain/{rel_path}:")
            for v in violations:
                error_msg.append(f"  - {v}")
        
        pytest.fail("\n".join(error_msg))
