"""The import law as tests — DESIGN's "Keeping the benchmark out of the product", enforced.

Ranks give the default direction: a module imports only its own package or a lower
rank. Denied edges sit on top of the ranks and carry the trust boundaries a rank law
cannot express — above all that the investigator (``agent``) never imports the
benchmark (``world``, ``generator``, ``validator``, ``evaluator``), so the answer key
is unreachable at source level and not only by credential. The rank-3 shells never
import one another, so the validator's read-only role and the evaluator's independence
from the generator are architectural rather than aspirational. Sibling adapters never
import one another. The write capabilities — the vendor write ports and the object
store's writer — are imported only by ``adapters`` and ``generator``, so the validator
and the investigator are read-only at source level. The truth manifest's decoder, the
capability to read the answer key, is gated the same way and tighter: by module path, to
the exact modules named as its readers. The pure packages
import no I/O library — a cheap guard, not a proof of purity. World time comes only from
an explicit ``RunContext``: the wall clock is read at a composition root and nowhere else.

The law refuses to fail open (the SteamLens precedent): every package under ``src`` must
hold a rank before the build accepts it; relative imports — which the edge scan cannot
rank — are banned outright; the top level holds only the package docstring and the
composition root, so no unranked module can launder an import for a ranked one; and an
``ImportFrom`` is read with its aliases, so ``from leaveimpact import world`` names
``world`` as plainly as ``import leaveimpact.world`` does. The rank table names a package
that does not exist yet (``app``); declared ahead is fine, existing unranked is not.
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
    "cache": 3,  # the corpus cache loader, the application's own job on the instance
    "app": 4,  # the demo milestone's
}
# The shells at this rank compose the same lower packages and never one another.
_LATERAL_FORBIDDEN_RANK = 3
# Trust boundaries: the investigator and the demo surface are blind to the benchmark.
_DENIED_EDGES: dict[str, frozenset[str]] = {
    "agent": frozenset({"world", "generator", "validator", "evaluator"}),
    "app": frozenset({"world", "generator", "validator", "evaluator"}),
    # The cache loader reads sealed world objects through the adapters and the world
    # codecs, and never a benchmark job: the generator writes what it reads, the validator
    # judges it, the evaluator holds the answer key's reader.
    "cache": frozenset({"generator", "validator", "evaluator"}),
}
# The write capabilities are gated by module path, not by domain name: only the packages
# that realize a world may import a module that declares one. An allowlist rather than a
# denied edge, so a re-export from anywhere else (``core/__init__`` included) is caught
# too; and no ``__init__`` may name a gated module at all, since a package that re-exported
# the writer would put it behind an import the law reads as the package. Gated: the
# vendor write ports, the object store's writer protocol, and the concrete writers'
# modules — a protocol gate alone left ``S3ObjectStore.overwrite`` nameable from the
# validator (the step 12 part-1 review), so the concrete classes are split by capability
# and the writing half of each backend is gated with the protocol.
_GATED_WRITE_MODULES: dict[tuple[str, ...], frozenset[str]] = {
    ("core", "ports", "write"): frozenset({"adapters", "generator"}),
    ("adapters", "object_store", "write"): frozenset({"adapters", "generator"}),
    ("adapters", "object_store", "s3_write"): frozenset({"adapters", "generator"}),
    ("adapters", "object_store", "local_write"): frozenset({"adapters", "generator"}),
    ("adapters", "object_store", "documents_write"): frozenset({"adapters", "generator"}),
    # The corpus cache loader writes rows and implements no write port; it is gated all the
    # same, to the adapters and the cache shell that runs it on the instance, so neither the
    # investigator nor the validator can fill or alter the cache (the M2 step 9 design).
    ("adapters", "corpus", "loader"): frozenset({"adapters", "cache"}),
}
# A module-scope import makes the imported names attributes of the importing module, so a
# non-gated ``adapters`` module that imported an object-store writer at module scope would
# hand the writer to every package allowed to import ``adapters`` — the wiring did exactly
# that (the step 12 part-5 review). Inside ``adapters``, only a gated module imports these
# at module scope; a shared helper that needs a writer builds it inside a function, where
# the name is local to the call. The generator is exempt: no shell may import it at all.
# The writer *protocol* is not in this set: a protocol is a type an annotation names and
# writes nothing without an instance, and the concrete classes are what the rule keeps out.
_OBJECT_STORE_WRITERS = frozenset(
    gated
    for gated in _GATED_WRITE_MODULES
    if gated[:2] == ("adapters", "object_store") and gated[2] != "write"
)
# The truth manifest's decoder reads the answer key, so its module is gated like a writer
# and the allowlist names exact importing modules, not packages: a second reader inside
# the generator or the evaluator is a deliberate edit here. The types and the encoder stay
# ungated in ``world.artifacts``, since an encoder needs an assembled world as input and
# gives a reader nothing. The readers are named ahead of the code that imports the
# decoder, as the rank table names packages ahead of their milestone. Three, by their
# full dotted path: the generator's resume, the evaluator's world loading, and the audit
# sheet, the operator's program that renders a sealed world for the hand audit under the
# administrative profile. This one gate reaches past ``src``: the operator's programs
# under ``scripts`` and ``probes`` run in the repository with the package importable, so
# a script that read the answer key without being named here would make "its named
# readers" false (the step 3 batch review found the audit sheet doing exactly that). The
# tests stay outside it; they exercise the decoder and hold no truth.
_TRUTH_DECODER: tuple[str, ...] = ("world", "truth_decoder")
_TRUTH_DECODER_READERS: frozenset[tuple[str, ...]] = frozenset(
    {
        (PKG, "generator", "resume"),
        (PKG, "evaluator", "sealed_world"),
        ("scripts", "audit_sheet"),
    }
)
REPOSITORY = Path(__file__).resolve().parents[2]
_OPERATOR_ROOTS = ("scripts", "probes")
_PURE = frozenset({"core", "world"})
# The top level is the package docstring and the composition root, nothing else: a module
# here has no rank, so the edge scan could not see what it re-exports.
_TOP_LEVEL_MODULES = frozenset({"__init__.py", "__main__.py"})
# The subpackages of ``adapters``, one external boundary each; a module at the adapters
# level itself is a shared helper, not a sibling.
_ADAPTER_SUBPACKAGES = frozenset(
    entry.name
    for entry in (SRC / "adapters").iterdir()
    if entry.is_dir() and (entry / "__init__.py").exists()
)
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
# Composition roots, as exact paths under ``src/leaveimpact``: the only modules that may
# read the wall clock, converting it into an explicit context at once. A job runner or a
# CLI joins the set by path when it exists. Monotonic timing for retries is
# infrastructure and is not matched here.
_CLOCK_ROOTS = frozenset({Path("__main__.py")})
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

    An ``ImportFrom`` contributes one path per alias, module plus name, so a package
    imported as a name (``from leaveimpact import world``) ranks exactly like the same
    package imported by its dotted path. A name that is a symbol rather than a module
    (``from leaveimpact.core.ids import EmployeeId``) only lengthens the path past the
    segments the law reads. Relative imports carry no dotted prefix and are unrankable
    here; they are banned wholesale by ``test_no_relative_imports``.

    >>> import tempfile
    >>> src = "from leaveimpact import world\\nimport leaveimpact.core.ids as ids\\n"
    >>> with tempfile.TemporaryDirectory() as d:
    ...     probe = Path(d) / "probe.py"
    ...     _ = probe.write_text(src, encoding="utf-8")
    ...     _imports(probe)
    [['leaveimpact', 'world'], ['leaveimpact', 'core', 'ids']]
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[list[str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.extend([*node.module.split("."), alias.name] for alias in node.names)
        elif isinstance(node, ast.Import):
            found.extend(alias.name.split(".") for alias in node.names)
    return found


def _intra_imports(path: Path) -> list[list[str]]:
    """The subset of ``_imports`` that stays inside this package."""
    return [parts for parts in _imports(path) if parts[0] == PKG]


def _module_scope_intra_imports(path: Path) -> list[list[str]]:
    """Like ``_intra_imports`` but only the imports in the module's own body, not nested ones.

    >>> import tempfile
    >>> src = "import leaveimpact.core\\ndef f():\\n    import leaveimpact.world\\n"
    >>> with tempfile.TemporaryDirectory() as d:
    ...     probe = Path(d) / "probe.py"
    ...     _ = probe.write_text(src, encoding="utf-8")
    ...     _module_scope_intra_imports(probe)
    [['leaveimpact', 'core']]
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[list[str]] = []
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.extend([*node.module.split("."), alias.name] for alias in node.names)
        elif isinstance(node, ast.Import):
            found.extend(alias.name.split(".") for alias in node.names)
    return [parts for parts in found if parts[0] == PKG]


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


def test_top_level_holds_only_the_composition_root() -> None:
    """The top level is unranked by design, so it may hold nothing the law would need to rank.

    ``_package`` returns None for a top-level module and every edge test skips None. A
    ``leaveimpact/helpers.py`` importing ``world`` would therefore be invisible, and so
    would the investigator importing ``helpers`` — one unranked hop launders the edge.
    Two rules close it: the top level holds only the package docstring and the
    composition root, and the docstring module imports nothing from inside the package,
    so it cannot re-export a ranked package under an unranked name. ``__main__`` composes
    the shells and may import anything; nothing imports ``__main__``.
    """
    stray = sorted(
        entry.name
        for entry in SRC.iterdir()
        if entry.is_file() and entry.suffix == ".py" and entry.name not in _TOP_LEVEL_MODULES
    )
    assert not stray, (
        f"unranked top-level modules: {stray} — the top level holds only the package "
        f"docstring and the composition root; a new module belongs inside a ranked package"
    )
    reexports = [".".join(parts) for parts in _intra_imports(SRC / "__init__.py")]
    assert not reexports, f"the package __init__ imports from inside the package: {reexports}"
    importers = [
        ".".join(parts)
        for path, parts in _modules()
        if any(imported[1:2] == ["__main__"] for imported in _intra_imports(path))
    ]
    assert not importers, f"modules importing the composition root: {importers}"


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


def test_write_capabilities_are_imported_only_by_the_packages_that_realize_a_world() -> None:
    """Read-only is a property of the module graph: a writer is reachable by one module path.

    The readers are re-exported from ``leaveimpact.core`` and from
    ``leaveimpact.adapters.object_store`` like every domain name; the writers are not,
    and this test is why — a re-export would put a writer behind an import the law
    reads as the package. So the rule is an allowlist over every module that names a
    gated module: the adapters that implement it and the generator that projects
    through it, nothing else — and never a package ``__init__``, the gated module's
    own package included.
    """
    violations: list[str] = []
    for path, parts in _modules():
        src_pkg = _package(parts)
        for imported in _intra_imports(path):
            gated = tuple(imported[1:4])
            if gated not in _GATED_WRITE_MODULES:
                continue
            if src_pkg not in _GATED_WRITE_MODULES[gated] or parts[-1] == "__init__":
                violations.append(f"{'.'.join(parts)} imports {'.'.join(gated)}")
    assert not violations, "write capabilities imported outside their allowlist:\n" + "\n".join(
        violations
    )


def test_an_object_store_writer_is_a_module_attribute_of_gated_modules_only() -> None:
    """Within ``adapters``, a writer's name lives at module scope in gated modules alone.

    The allowlist above says who may import a writer; this says how a non-gated module
    of ``adapters`` may: inside a function, so the class never becomes an attribute a
    validator can reach through ``from leaveimpact.adapters.wiring import …``.
    """
    violations: list[str] = []
    for path, parts in _modules():
        if _package(parts) != "adapters" or tuple(parts[1:4]) in _GATED_WRITE_MODULES:
            continue
        for imported in _module_scope_intra_imports(path):
            if tuple(imported[1:4]) in _OBJECT_STORE_WRITERS:
                violations.append(
                    f"{'.'.join(parts)} names {'.'.join(imported[1:4])} at module scope"
                )
    assert not violations, "object-store writers exposed as module attributes:\n" + "\n".join(
        violations
    )


def _operator_programs() -> Iterator[tuple[Path, list[str]]]:
    """Every Python file under ``scripts`` and ``probes``, as (path, dotted parts from its root).

    The programs an operator runs from the repository: outside the package and so outside
    the rank law, inside the one gate whose capability they could exercise.
    """
    for root in _OPERATOR_ROOTS:
        for path in sorted((REPOSITORY / root).rglob("*.py")):
            yield path, [root, *path.relative_to(REPOSITORY / root).with_suffix("").parts]


def _truth_decoder_violations(parts: list[str], imports: list[list[str]]) -> list[str]:
    """The imports of the truth decoder that the module ``parts`` makes without being a reader.

    Pure over a module's dotted parts and its imports, so the gate is shown red on planted
    importers without planting a file. A reader is named by its full dotted path; a package
    ``__init__`` is never one, so one that names the decoder is a violation like any other.

    >>> decoder = ["leaveimpact", "world", "truth_decoder", "decode_truth_manifest"]
    >>> _truth_decoder_violations(["leaveimpact", "validator", "checks"], [decoder])
    ['leaveimpact.validator.checks imports world.truth_decoder']
    >>> _truth_decoder_violations(["scripts", "another_sheet"], [decoder])
    ['scripts.another_sheet imports world.truth_decoder']
    >>> _truth_decoder_violations(["leaveimpact", "generator", "resume"], [decoder])
    []
    """
    if tuple(parts) in _TRUTH_DECODER_READERS:
        return []
    return [
        f"{'.'.join(parts)} imports {'.'.join(imported[1:3])}"
        for imported in imports
        if tuple(imported[1:3]) == _TRUTH_DECODER
    ]


def test_the_truth_decoder_is_imported_only_by_its_named_readers() -> None:
    """Reading the answer key is one module path, importable by the modules named for it.

    The validator's role cannot read the truth object and the investigator cannot import
    ``world`` at all; this is the source-level half for everything else, the validator's
    own code and ``world``'s import surface included, and the operator's programs under
    ``scripts`` and ``probes`` beside the package. The scan reads nested imports too, so
    an import inside a function is no way around it.
    """
    violations = [
        violation
        for path, parts in (*_modules(), *_operator_programs())
        for violation in _truth_decoder_violations(parts, _intra_imports(path))
    ]
    assert not violations, "the truth decoder imported outside its readers:\n" + "\n".join(
        violations
    )


def test_every_named_reader_of_the_truth_decoder_that_exists_does_read_it() -> None:
    """A reader named ahead of its module is fine; one that exists and no longer imports the
    decoder is a stale grant, and the list is the claim of who reads the key."""
    scanned = {tuple(parts): path for path, parts in (*_modules(), *_operator_programs())}
    stale = sorted(
        ".".join(reader)
        for reader in _TRUTH_DECODER_READERS
        if reader in scanned
        and not any(
            tuple(imported[1:3]) == _TRUTH_DECODER for imported in _intra_imports(scanned[reader])
        )
    )
    assert not stale, f"named readers that do not import the truth decoder: {stale}"


def test_the_truth_decoder_gate_is_red_on_a_planted_importer() -> None:
    """The gate is trusted because it fails: every other importer, in either spelling."""
    by_symbol = [PKG, "world", "truth_decoder", "decode_truth_manifest"]
    by_module = [PKG, "world", "truth_decoder"]
    planted = (
        [PKG, "validator", "checks"],
        [PKG, "validator", "__init__"],
        [PKG, "adapters", "wiring"],
        [PKG, "world", "__init__"],
        [PKG, "world", "decoders"],
        [PKG, "generator", "fresh"],
        [PKG, "evaluator", "grading"],
        [PKG, "evaluator", "__init__"],
        ["scripts", "regen_docs"],
        ["probes", "golden-chain", "probe"],
        # A reader's name is its whole path: the same stem elsewhere is not the reader.
        ["probes", "audit_sheet"],
        [PKG, "scripts", "audit_sheet"],
    )
    for module in planted:
        for spelling in (by_symbol, by_module):
            assert _truth_decoder_violations(module, [spelling]), module
    for reader in _TRUTH_DECODER_READERS:
        assert not _truth_decoder_violations(list(reader), [by_symbol, by_module])


def test_sibling_adapters_do_not_import_one_another() -> None:
    """Each adapter translates one external boundary; orchestration across systems lives above them.

    A module inside ``adapters/<x>/`` may import ``adapters`` itself (a shared retry
    policy, say) and anything lower, never ``adapters/<y>/``. The third path segment is
    compared against the adapter subpackages that exist, so ``from leaveimpact.adapters
    import retry_policy`` reads as the shared helper it is and ``from leaveimpact.adapters
    import frappe`` reads as the sibling it is.
    """
    violations: list[str] = []
    for path, parts in _modules():
        if _package(parts) != "adapters" or len(parts) < 4:
            continue  # modules at the adapters level are the shared helpers, not a sibling
        own = parts[2]
        for imported in _intra_imports(path):
            if (
                len(imported) >= 3
                and imported[1] == "adapters"
                and imported[2] in _ADAPTER_SUBPACKAGES
                and imported[2] != own
            ):
                violations.append(f"{'.'.join(parts)} imports sibling adapter '{imported[2]}'")
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
        if path.relative_to(SRC) in _CLOCK_ROOTS:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if _CLOCK_READ.search(line):
                violations.append(f"{'.'.join(parts)}:{lineno}: {line.strip()}")
    assert not violations, "wall-clock reads outside a composition root:\n" + "\n".join(violations)
