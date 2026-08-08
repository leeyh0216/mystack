"""Enforce inward-only imports for service bounded contexts.

Architecture reference:
https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[2]
LAYERS = {"domain": 0, "application": 1, "adapters": 2, "bootstrap": 3, "api": 3}


def internal_imports(source: Path, package_name: str) -> set[str]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(
                alias.name for alias in node.names if alias.name.startswith(package_name)
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            if node.level == 0 and node.module.startswith(package_name):
                modules.add(node.module)
    return modules


def test_service_modules_only_depend_inward() -> None:
    violations: list[str] = []
    for service, package_name in (("emr", "mystack.emr"), ("glue", "mystack.glue")):
        package_root = ROOT / service / "src" / Path(*package_name.split("."))
        if not package_root.exists():
            continue
        for source in package_root.rglob("*.py"):
            relative = source.relative_to(package_root)
            source_layer = relative.parts[0] if len(relative.parts) > 1 else "bootstrap"
            if source_layer not in LAYERS:
                continue
            for imported in internal_imports(source, package_name):
                relative_import = imported.removeprefix(package_name).lstrip(".")
                target_layer = relative_import.split(".", maxsplit=1)[0]
                if target_layer not in LAYERS:
                    continue
                if LAYERS[target_layer] > LAYERS[source_layer]:
                    violations.append(
                        f"{source.relative_to(ROOT)}: {source_layer} imports outer {target_layer}"
                    )
    assert not violations, "Dependency rule violations:\n" + "\n".join(violations)


def test_inner_layers_do_not_import_composition_modules() -> None:
    violations: list[str] = []
    for service, package_name in (("emr", "mystack.emr"), ("glue", "mystack.glue")):
        package_root = ROOT / service / "src" / Path(*package_name.split("."))
        for layer in ("domain", "application"):
            for source in (package_root / layer).rglob("*.py"):
                for imported in internal_imports(source, package_name):
                    if imported.startswith(f"{package_name}.app"):
                        violations.append(f"{source.relative_to(ROOT)} imports {imported}")
    assert not violations, "Composition dependency violations:\n" + "\n".join(violations)


def test_shared_protocol_package_does_not_import_service_packages() -> None:
    package_root = ROOT / "shared" / "src" / "mystack" / "aws_protocol"
    violations: list[str] = []
    for source in package_root.rglob("*.py"):
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            else:
                continue
            for name in names:
                if name.startswith(("mystack.glue", "mystack.emr", "mystack.proxy")):
                    violations.append(f"{source.relative_to(ROOT)} imports {name}")
    assert not violations, "Shared service dependency violations:\n" + "\n".join(violations)
