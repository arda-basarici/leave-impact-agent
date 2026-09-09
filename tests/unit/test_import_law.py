"""The import law as tests — DESIGN's "Package boundaries and the import law", enforced.

Ranks give the default direction: a module imports only its own package or a lower
rank. Denied edges sit on top of the ranks and carry the trust boundaries a rank law
cannot express — above all that the investigator (``agent``) never imports the
benchmark (``world``, ``generator``, ``validator``, ``evaluator``), so the answer key
is unreachable at source level and not only by credential. The rank-3 shells never
import one another, so the validator's read-only role and the evaluator's independence
from the generator are architectural rather than aspirational. Sibling adapters never
import one another. The pure packages import no I/O library — a cheap guard, not a proof
of purity. World time comes only from an explicit ``RunContext``: the wall clock is read
at a composition root and nowhere else.

The law refuses to fail open (the SteamLens precedent): every package under ``src`` must
hold a rank before the build accepts it, and relative imports — which the edge scan
cannot rank — are banned outright. The rank table names packages that do not exist yet
(``evaluator``, ``agent``, ``app``); declared ahead is fine, existing unranked is not.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from pathlib import Path

PKG = "leaveimpact"
SRC = Path(__file__).resolve().parents[2] / "src" / PKG

# Rank: a module may import only its own package or a lower rank. Packages named
# ahead of their milestone keep their place in the law from day one.
_RANK: dict[str, int] = {
    "core": 0,
    "world": 1,
    "adapters": 2,
    "generator": 3,
    "validator": 3,
    "evaluator": 3,  # the investigator milestone's
    "agent": 3,  # the investigator milestone's
    "app": 4,  # the demo milestone's
}
# The shells at this rank compose the same lower packages and never one another.
_LATERAL_FORBIDDEN_RANK = 3
# Trust boundaries: the investigator and the demo surface are blind to the benchmark.
_DENIED_EDGES: dict[str, frozenset[str]] = {
    "agent": frozenset({"world", "generator", "validator", "evaluator"}),
    "app": frozenset({"world", "generator", "validator", "evaluator"}),
}
_PURE = frozenset({"core", "world"})
# Top-level module names whose presence in a pure package means it performs I/O.
_IO_MODULES = frozenset(
    {
        "boto3",
        "botocore",
        "google",
        "googleapiclient",
        "httpx",
        "psycopg",
        "requests",
        "socket",
        "sqlite3",
        "subprocess",
        "urllib",
    }
)
# Composition roots: the only files that may read the wall clock, converting it into
# an explicit context at once. Monotonic timing for retries is infrastructure and
# is not matched here.
_CLOCK_ROOTS = frozenset({"__main__.py", "cli.py"})
_CLOCK_READ = re.compile(r"\b(?:datetime|date)\.(?:now|utcnow|today)\(|\btime\.time\(")


def _modules() -> Iterator[tuple[Path, list[str]]]:
    """Every module under ``src``, as (path, dotted parts starting with the package)."""
    for path in sorted(SRC.rglob("*.py")):
        yield path, [PKG, *path.relative_to(SRC).with_suffix("").parts]


def _package(parts: list[str]) -> str | None:
    """The ranked package a dotted module belongs to, or None for the top level.

    >>> _package(["leaveimpact", "core", "rules"])
    'core'
    >>> _package(["leaveimpact", "__main__"]) is None
    True
    """
    if len(parts) < 2:
        return None
    sub = parts[1]
    return sub if sub in _RANK else None


def _imports(path: Path) -> list[list[str]]:
    """Every absolute import made by the module at ``path``, as dotted part lists.

    Relative imports carry no dotted prefix and are unrankable here; they are banned
    wholesale by ``test_no_relative_imports``.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[list[str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.append(node.module.split("."))
        elif isinstance(node, ast.Import):
            found.extend(alias.name.split(".") for alias in node.names)
    return found


def _intra_imports(path: Path) -> list[list[str]]:
    """The subset of ``_imports`` that stays inside this package."""
    return [parts for parts in _imports(path) if parts[0] == PKG]


def test_every_package_is_ranked() -> None:
    """Declaring a rank is a precondition for adding a package, not a courtesy.

    ``_package`` returns None for anything missing from the rank table and the law
    skips None — correct for the top-level modules, fail-open for a package someone
    forgot to rank. A new package under ``src`` is red until it takes its place.
    """
    unranked = sorted(
        entry.name
        for entry in SRC.iterdir()
        if entry.is_dir() and (entry / "__init__.py").exists() and entry.name not in _RANK
    )
    assert not unranked, (
        f"packages missing from the rank table: {unranked} — declare each one's rank "
        f"so the import law can see it"
    )


def test_no_relative_imports() -> None:
    """Relative imports are banned in ``src`` — the law can only rank what it can name."""
    violations: list[str] = []
    for path, _ in _modules():
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.level > 0:
                target = f"{'.' * node.level}{node.module or ''}"
                violations.append(f"{path.relative_to(SRC)}: from {target} import ...")
    assert not violations, "relative imports in src (invisible to the import law):\n" + "\n".join(
        violations
    )


def test_rank_law() -> None:
    """No module imports a higher rank, and the rank-3 shells never import one another."""
    violations: list[str] = []
    for path, parts in _modules():
        src_pkg = _package(parts)
        if src_pkg is None:
            continue
        for imported in _intra_imports(path):
            dst_pkg = _package(imported)
            if dst_pkg is None or dst_pkg == src_pkg:
                continue
            src_rank, dst_rank = _RANK[src_pkg], _RANK[dst_pkg]
            if src_rank < dst_rank:
                violations.append(
                    f"{'.'.join(parts)} ({src_pkg}, rank {src_rank}) imports higher-ranked "
                    f"'{dst_pkg}' (rank {dst_rank})"
                )
            elif src_rank == dst_rank == _LATERAL_FORBIDDEN_RANK:
                violations.append(
                    f"{'.'.join(parts)} ({src_pkg}) imports its lateral shell '{dst_pkg}'"
                )
    assert not violations, "rank-law violations:\n" + "\n".join(violations)


def test_denied_edges() -> None:
    """The investigator and the demo surface never import the benchmark, whatever the ranks say."""
    violations: list[str] = []
    for path, parts in _modules():
        src_pkg = _package(parts)
        if src_pkg is None or src_pkg not in _DENIED_EDGES:
            continue
        for imported in _intra_imports(path):
            dst_pkg = _package(imported)
            if dst_pkg in _DENIED_EDGES[src_pkg]:
                violations.append(
                    f"{'.'.join(parts)} ({src_pkg}) imports '{dst_pkg}' across a trust boundary"
                )
    assert not violations, "denied-edge violations:\n" + "\n".join(violations)


def test_sibling_adapters_do_not_import_one_another() -> None:
    """Each adapter translates one external boundary; orchestration across systems lives above them.

    A module inside ``adapters/<x>/`` may import ``adapters`` itself (a shared retry
    policy, say) and anything lower, never ``adapters/<y>/``.
    """
    violations: list[str] = []
    for path, parts in _modules():
        if _package(parts) != "adapters" or len(parts) < 4:
            continue  # modules at the adapters level are the shared helpers, not a sibling
        own = parts[2]
        for imported in _intra_imports(path):
            if len(imported) >= 3 and imported[1] == "adapters" and imported[2] != own:
                violations.append(
                    f"{'.'.join(parts)} imports sibling adapter '{imported[2]}'"
                )
    assert not violations, "sibling-adapter imports:\n" + "\n".join(violations)


def test_pure_packages_import_no_io() -> None:
    """``core`` and ``world`` never import an I/O library — a cheap guard, not a proof of purity."""
    violations: list[str] = []
    for path, parts in _modules():
        if _package(parts) not in _PURE:
            continue
        for imported in _imports(path):
            if imported[0] in _IO_MODULES:
                violations.append(f"{'.'.join(parts)} imports '{imported[0]}'")
    assert not violations, "I/O imports in a pure package:\n" + "\n".join(violations)


def test_wall_clock_only_at_composition_roots() -> None:
    """World time comes from ``RunContext``; the wall clock is read only where a run is composed.

    A textual scan rather than an import ban, because the offending call is a method on a
    type every module legitimately imports. Monotonic timing for retries is not matched.
    """
    violations: list[str] = []
    for path, parts in _modules():
        if path.name in _CLOCK_ROOTS:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _CLOCK_READ.search(line):
                violations.append(f"{'.'.join(parts)}:{lineno}: {line.strip()}")
    assert not violations, "wall-clock reads outside a composition root:\n" + "\n".join(
        violations
    )
