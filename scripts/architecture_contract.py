"""Executable dependency rules for Mystack Python packages.

Architecture references:
- https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html
- https://docs.python.org/3/reference/import.html#package-relative-imports
"""

from __future__ import annotations

import argparse
import ast
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class PackageBoundary:
    name: str
    source_root: Path
    package: str
    architecture: str


@dataclass(frozen=True, slots=True)
class ImportReference:
    source: Path
    source_module: str
    imported_module: str
    line: int


@dataclass(frozen=True, slots=True)
class ArchitectureViolation:
    source: Path
    line: int
    imported_module: str
    rule: str
    repair: str

    def render(self, root: Path) -> str:
        return (
            f"source={self.source.relative_to(root)}:{self.line} "
            f"imported={self.imported_module} rule={self.rule} repair={self.repair}"
        )


DEFAULT_BOUNDARIES = (
    PackageBoundary(
        "shared", Path("shared/src/mystack/aws_protocol"), "mystack.aws_protocol", "shared"
    ),
    PackageBoundary("proxy", Path("proxy/src/mystack/proxy"), "mystack.proxy", "proxy"),
    PackageBoundary("emr", Path("emr/src/mystack/emr"), "mystack.emr", "layered"),
    PackageBoundary("glue", Path("glue/src/mystack/glue"), "mystack.glue", "layered"),
)

# The only modules allowed to import concrete adapters from outside an adapter package.
COMPOSITION_ROOT_MODULES = frozenset({"mystack.emr.app", "mystack.glue.app"})

# Generated JSON/Markdown artifacts are outside Python source roots. No generated Python is exempt.
GENERATED_PYTHON_EXCLUSIONS: tuple[str, ...] = ()

_LAYERS = {"domain": 0, "application": 1, "adapters": 2, "composition": 3}
_TRANSPORT_PREFIXES = ("boto3", "botocore", "fastapi", "httpx", "starlette", "uvicorn")
_SQLITE_DRIVER_PREFIXES = ("sqlite3", "pysqlite3", "apsw")
_SQL_STATEMENT_PREFIXES = frozenset(
    {
        "ALTER",
        "ANALYZE",
        "BEGIN",
        "COMMIT",
        "CREATE",
        "DELETE",
        "DROP",
        "EXPLAIN",
        "INSERT",
        "PRAGMA",
        "REINDEX",
        "RELEASE",
        "ROLLBACK",
        "SAVEPOINT",
        "SELECT",
        "UPDATE",
        "VACUUM",
        "WITH",
    }
)
_GLUE_SQLITE_ADAPTER_PREFIX = "mystack.glue.adapters.outbound.sqlite_catalog"
_GLUE_DOMAIN_ERROR_NAMES = frozenset(
    {
        "AlreadyExistsError",
        "EntityNotFoundError",
        "GlueDomainError",
        "InvalidInputError",
        "VersionMismatchError",
    }
)


def _source_module(source: Path, boundary: PackageBoundary, root: Path) -> str:
    package_root = root / boundary.source_root
    relative = source.relative_to(package_root).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join((boundary.package, *parts)) if parts else boundary.package


def _relative_import(
    source: Path,
    source_module: str,
    level: int,
    module: str | None,
    aliases: Iterable[ast.alias],
) -> tuple[str, ...]:
    package = source_module if source.name == "__init__.py" else source_module.rpartition(".")[0]
    parts = package.split(".")
    parent_count = level - 1
    if parent_count >= len(parts):
        return ()
    base = ".".join(parts[: len(parts) - parent_count])
    if module:
        return (f"{base}.{module}",)
    return tuple(f"{base}.{alias.name}" for alias in aliases)


def _imports(source: Path, source_module: str) -> tuple[ImportReference, ...]:
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    references: list[ImportReference] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules = tuple(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules = _relative_import(
                    source,
                    source_module,
                    node.level,
                    node.module,
                    node.names,
                )
            elif node.module:
                modules = (node.module,)
            else:
                modules = ()
        else:
            continue
        references.extend(
            ImportReference(source, source_module, imported, node.lineno) for imported in modules
        )
    return tuple(references)


def _sqlite_boundary_violations(
    source: Path,
    source_module: str,
    boundary: PackageBoundary,
) -> list[ArchitectureViolation]:
    """Reject database-driver leakage without mistaking non-SQL ``execute`` calls for SQL.

    The check deliberately recognizes only literal SQL statement prefixes. For example,
    ``SparkTableOptimizerExecutor.execute(work)`` remains an application port invocation, while
    ``connection.execute(\"SELECT ...\")`` is a persistence responsibility that belongs to an
    outbound adapter.
    """

    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    source_layer = _layer(source_module, boundary.package)
    violations: list[ArchitectureViolation] = []
    if source_layer in {"domain", "application"}:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules = tuple(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = (node.module,)
            else:
                modules = ()
            for module in modules:
                if module in _SQLITE_DRIVER_PREFIXES or module.startswith(
                    tuple(f"{prefix}." for prefix in _SQLITE_DRIVER_PREFIXES)
                ):
                    violations.append(
                        ArchitectureViolation(
                            source=source,
                            line=node.lineno,
                            imported_module=module,
                            rule="inner-sqlite-driver-dependency",
                            repair=(
                                "Keep SQLite DB-API imports in an outbound adapter and depend on "
                                "an application-owned catalog port instead."
                            ),
                        )
                    )
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in {"execute", "executemany"} or not node.args:
                continue
            statement = _literal_sql_statement(node.args[0])
            if statement is None:
                continue
            violations.append(
                ArchitectureViolation(
                    source=source,
                    line=node.lineno,
                    imported_module=f"SQL:{statement}",
                    rule="inner-sql-execution",
                    repair=(
                        "Move literal SQL execution to an outbound adapter and expose a typed "
                        "application port operation."
                    ),
                )
            )

    if source_module.startswith(_GLUE_SQLITE_ADAPTER_PREFIX):
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported_errors = {
                    alias.name for alias in node.names if alias.name in _GLUE_DOMAIN_ERROR_NAMES
                }
                if module == "mystack.glue.domain.errors" or imported_errors:
                    violations.append(
                        ArchitectureViolation(
                            source=source,
                            line=node.lineno,
                            imported_module=module or ",".join(sorted(imported_errors)),
                            rule="sqlite-adapter-domain-error-dependency",
                            repair=(
                                "Return neutral persistence outcomes; application handlers own "
                                "Glue error precedence and translation."
                            ),
                        )
                    )
            if isinstance(node, ast.Raise) and _raised_domain_error(node.exc):
                violations.append(
                    ArchitectureViolation(
                        source=source,
                        line=node.lineno,
                        imported_module=_raise_name(node.exc),
                        rule="sqlite-adapter-domain-error-raise",
                        repair=(
                            "Return neutral persistence outcomes; application handlers own "
                            "Glue error precedence and translation."
                        ),
                    )
                )
    return violations


def _literal_sql_statement(argument: ast.expr) -> str | None:
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        text = argument.value
    elif isinstance(argument, ast.JoinedStr):
        text = "".join(
            value.value
            for value in argument.values
            if isinstance(value, ast.Constant) and isinstance(value.value, str)
        )
    else:
        return None
    statement = text.lstrip().split(maxsplit=1)
    if not statement:
        return None
    return statement[0].upper() if statement[0].upper() in _SQL_STATEMENT_PREFIXES else None


def _raised_domain_error(value: ast.expr | None) -> bool:
    return _raise_name(value) in _GLUE_DOMAIN_ERROR_NAMES


def _raise_name(value: ast.expr | None) -> str:
    if isinstance(value, ast.Call):
        return _raise_name(value.func)
    if isinstance(value, ast.Name):
        return value.id
    if isinstance(value, ast.Attribute):
        return value.attr
    return ""


def _layer(module: str, package: str) -> str | None:
    if module == package:
        return "composition"
    if not module.startswith(f"{package}."):
        return None
    first = module.removeprefix(f"{package}.").split(".", maxsplit=1)[0]
    return first if first in {"domain", "application", "adapters"} else "composition"


def _violation(reference: ImportReference, rule: str, repair: str) -> ArchitectureViolation:
    return ArchitectureViolation(
        source=reference.source,
        line=reference.line,
        imported_module=reference.imported_module,
        rule=rule,
        repair=repair,
    )


def _dependency_violations(
    reference: ImportReference,
    boundary: PackageBoundary,
    all_boundaries: tuple[PackageBoundary, ...],
) -> list[ArchitectureViolation]:
    violations: list[ArchitectureViolation] = []
    imported = reference.imported_module

    if boundary.architecture == "shared":
        if imported.startswith("mystack.") and not imported.startswith(boundary.package):
            violations.append(
                _violation(
                    reference,
                    "shared-service-dependency",
                    "Move the abstraction to the owning service or keep it at the wire boundary.",
                )
            )
        return violations

    service_packages = tuple(
        item.package for item in all_boundaries if item.architecture == "layered"
    )
    if boundary.architecture == "proxy":
        if imported.startswith(service_packages):
            violations.append(
                _violation(
                    reference,
                    "proxy-service-dependency",
                    "Register service routing in YAML; Proxy must not import emulator packages.",
                )
            )
        return violations

    for other in all_boundaries:
        if (
            other.architecture == "layered"
            and other.package != boundary.package
            and imported.startswith(other.package)
        ):
            violations.append(
                _violation(
                    reference,
                    "cross-service-dependency",
                    "Communicate through the public protocol instead of importing another service.",
                )
            )

    source_layer = _layer(reference.source_module, boundary.package)
    target_layer = _layer(imported, boundary.package)
    if (
        source_layer in {"domain", "application", "adapters"}
        and target_layer is not None
        and _LAYERS[target_layer] > _LAYERS[source_layer]
    ):
        violations.append(
            _violation(
                reference,
                "outward-dependency",
                f"Move the port or policy inward; {source_layer} cannot import {target_layer}.",
            )
        )

    if source_layer in {"domain", "application"} and imported.startswith(_TRANSPORT_PREFIXES):
        violations.append(
            _violation(
                reference,
                "inner-transport-dependency",
                "Translate transport and SDK types in an adapter owned by the outer layer.",
            )
        )

    adapter_prefix = f"{boundary.package}.adapters"
    if (
        imported.startswith(adapter_prefix)
        and not reference.source_module.startswith(adapter_prefix)
        and reference.source_module not in COMPOSITION_ROOT_MODULES
    ):
        violations.append(
            _violation(
                reference,
                "composition-only-adapter",
                f"Import and construct concrete adapters only in {boundary.package}.app.",
            )
        )

    inbound_prefix = f"{boundary.package}.adapters.inbound"
    outbound_prefix = f"{boundary.package}.adapters.outbound"
    if (
        reference.source_module.startswith(inbound_prefix) and imported.startswith(outbound_prefix)
    ) or (
        reference.source_module.startswith(outbound_prefix) and imported.startswith(inbound_prefix)
    ):
        violations.append(
            _violation(
                reference,
                "adapter-sibling-dependency",
                "Connect inbound and outbound adapters through application-owned ports.",
            )
        )

    if reference.source_module.startswith(inbound_prefix) and imported.startswith(
        f"{boundary.package}.application"
    ):
        allowed = (
            f"{boundary.package}.application.commands",
            f"{boundary.package}.application.policies",
            f"{boundary.package}.application.use_cases",
        )
        if not imported.startswith(allowed):
            violations.append(
                _violation(
                    reference,
                    "inbound-concrete-facade",
                    "Depend on application.use_cases Protocols, policies, and command values, "
                    "not the facade.",
                )
            )
    return violations


def _cycle_violations(
    root: Path,
    module_sources: dict[str, Path],
    references: tuple[ImportReference, ...],
) -> list[ArchitectureViolation]:
    graph: dict[str, set[str]] = {module: set() for module in module_sources}
    for reference in references:
        if (
            reference.imported_module in graph
            and reference.imported_module != reference.source_module
        ):
            graph[reference.source_module].add(reference.imported_module)

    index = 0
    indices: dict[str, int] = {}
    low_links: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    cycles: list[tuple[str, ...]] = []

    def visit(module: str) -> None:
        nonlocal index
        indices[module] = index
        low_links[module] = index
        index += 1
        stack.append(module)
        on_stack.add(module)
        for target in graph[module]:
            if target not in indices:
                visit(target)
                low_links[module] = min(low_links[module], low_links[target])
            elif target in on_stack:
                low_links[module] = min(low_links[module], indices[target])
        if low_links[module] != indices[module]:
            return
        component: list[str] = []
        while stack:
            target = stack.pop()
            on_stack.remove(target)
            component.append(target)
            if target == module:
                break
        if len(component) > 1:
            cycles.append(tuple(sorted(component)))

    for module in sorted(graph):
        if module not in indices:
            visit(module)

    return [
        ArchitectureViolation(
            source=module_sources[cycle[0]],
            line=1,
            imported_module=" -> ".join((*cycle, cycle[0])),
            rule="service-import-cycle",
            repair=(
                "Extract an inward port/value or reverse the dependency at the composition root."
            ),
        )
        for cycle in cycles
    ]


def scan_repository(
    root: Path,
    boundaries: tuple[PackageBoundary, ...] = DEFAULT_BOUNDARIES,
) -> tuple[ArchitectureViolation, ...]:
    resolved_root = root.resolve()
    references: list[ImportReference] = []
    module_sources: dict[str, Path] = {}
    source_boundaries: dict[Path, PackageBoundary] = {}
    for boundary in boundaries:
        package_root = resolved_root / boundary.source_root
        for source in sorted(package_root.rglob("*.py")):
            module = _source_module(source, boundary, resolved_root)
            module_sources[module] = source
            source_boundaries[source] = boundary
            references.extend(_imports(source, module))

    collected = tuple(references)
    violations: list[ArchitectureViolation] = []
    for reference in collected:
        violations.extend(
            _dependency_violations(
                reference,
                source_boundaries[reference.source],
                boundaries,
            )
        )
    for source, boundary in source_boundaries.items():
        violations.extend(
            _sqlite_boundary_violations(
                source,
                _source_module(source, boundary, resolved_root),
                boundary,
            )
        )
    violations.extend(_cycle_violations(resolved_root, module_sources, collected))
    return tuple(
        sorted(
            violations,
            key=lambda item: (str(item.source), item.line, item.rule, item.imported_module),
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).parents[1])
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    print(
        json.dumps(
            {
                "event": "architecture.scan.before",
                "root": str(root),
                "generated_python_exclusions": GENERATED_PYTHON_EXCLUSIONS,
            },
            sort_keys=True,
        )
    )
    violations = scan_repository(root)
    if violations:
        for violation in violations:
            print(
                json.dumps(
                    {
                        "event": "architecture.violation",
                        "source": str(violation.source.relative_to(root)),
                        "line": violation.line,
                        "imported_module": violation.imported_module,
                        "rule": violation.rule,
                        "repair": violation.repair,
                    },
                    sort_keys=True,
                )
            )
        raise SystemExit(
            "Architecture contract violations:\n"
            + "\n".join(violation.render(root) for violation in violations)
        )
    print(
        json.dumps(
            {
                "event": "architecture.scan.after",
                "status": "clean",
                "composition_roots": sorted(COMPOSITION_ROOT_MODULES),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
