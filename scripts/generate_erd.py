"""
generate_erd.py
================

Generate an Entity-Relationship Diagram (ERD) from the project's SQLAlchemy
declarative models.

This script is project-structure agnostic. It supports two import strategies
for the SQLAlchemy ``Base`` / ``metadata`` object:

1. **Direct import** (preferred): import the ``Base`` defined in your project
   (typically ``app/db/base.py``). Adjust the import block below (look for the
   ``TODO: project-specific Base import`` marker).
2. **Discovery fallback**: scan common locations such as ``app.db.base``,
   ``app.models.base`` or ``app.core.db`` for a declarative ``Base`` or a
   ``MetaData`` instance. This keeps the script working on slight variations
   of the project layout.

The script produces two artifacts:

* ``docs/er-diagram.png`` – a rendered PNG image of the schema
  (generated via eralchemy2 + graphviz).
* ``docs/er-diagram.md``   – a Markdown file containing a Mermaid ``erDiagram``
  code block that can be embedded directly into a README on GitHub.

If eralchemy2 cannot produce a Mermaid ``erDiagram`` (e.g. because of
unsupported types or a stale install) the script falls back to a self-written
Mermaid emitter that walks ``Base.metadata.tables`` directly. This guarantees
a Markdown embed even on minimal installs.

Usage
-----
::

    uv run python scripts/generate_erd.py
    # or
    python scripts/generate_erd.py --png docs/er-diagram.png \\
            --md docs/er-diagram.md

Dependencies
------------
* Python >= 3.10
* ``eralchemy2`` (and the system ``graphviz`` package providing the ``dot``
  binary for PNG output)
* ``SQLAlchemy`` >= 2.0

Example ``pyproject.toml`` snippet::

    [project.optional-dependencies]
    erd = ["eralchemy2>=1.4"]

    [tool.uv]
    # uv handles graphviz at OS level: `brew install graphviz` / `apt install graphviz`
"""

from __future__ import annotations

import argparse
import importlib
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Third-party imports
# ---------------------------------------------------------------------------
try:
    from sqlalchemy import MetaData
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "SQLAlchemy is required for generate_erd.py. "
        "Install it with `uv add sqlalchemy` or `pip install sqlalchemy`."
    ) from exc


# ---------------------------------------------------------------------------
# Project-specific Base import
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.models.base import Base

BASE_OR_METADATA: Any = Base  # SQLAlchemy DeclarativeBase


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_CANDIDATE_MODULES = (
    "app.db.base",
    "app.models.base",
    "app.core.db",
    "db.base",
    "models.base",
    "core.db",
)


def discover_base_metadata() -> MetaData:
    """Try to find a SQLAlchemy ``MetaData``/``Base`` in the installed project.

    This is a convenience for environments where the project layout isn't
    known up-front. If the direct import above (``BASE_OR_METADATA``) is set
    we use that; otherwise we walk a list of common module names.
    """
    if BASE_OR_METADATA is not None:
        return _coerce_metadata(BASE_OR_METADATA)

    last_err: Exception | None = None
    for module_name in _CANDIDATE_MODULES:
        try:
            module = importlib.import_module(module_name)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
        for attr in ("Base", "base", "metadata", "metadata_obj"):
            candidate = getattr(module, attr, None)
            if candidate is None:
                continue
            try:
                return _coerce_metadata(candidate)
            except TypeError as exc:
                last_err = exc
                continue

    raise SystemExit(
        "Could not locate a SQLAlchemy Base/metadata automatically.\n"
        "Set BASE_OR_METADATA in scripts/generate_erd.py to the project's "
        "Base class (e.g. `BASE_OR_METADATA = Base`) or update the "
        "_CANDIDATE_MODULES list to match your layout.\n"
        f"Last error: {last_err!r}"
    )


def _coerce_metadata(obj: Any) -> MetaData:
    """Return a ``MetaData`` instance regardless of whether ``obj`` is a
    declarative ``Base`` or already a ``MetaData`` object."""
    if isinstance(obj, MetaData):
        return obj
    # Declarative Base instances expose ``.metadata``
    metadata = getattr(obj, "metadata", None)
    if isinstance(metadata, MetaData):
        return metadata
    raise TypeError(f"Object of type {type(obj).__name__} is not a MetaData/Base")


# ---------------------------------------------------------------------------
# Mermaid erDiagram emitter (fallback / always used for the Markdown output)
# ---------------------------------------------------------------------------
# Mermaid erDiagram syntax reference:
#   https://mermaid.js.org/syntax/entityRelationshipDiagram.html
# Cardinality symbols (left -> right):
#   ||  exactly one
#   o|  zero or one
#   }|  one or more
#   }o  zero or more
# ---------------------------------------------------------------------------

# Maps SQLAlchemy types / Python types -> short Mermaid type names.
_TYPE_MAP: dict[str, str] = {
    "INTEGER": "int",
    "BIGINTEGER": "bigint",
    "SMALLINTEGER": "smallint",
    "FLOAT": "float",
    "NUMERIC": "numeric",
    "DECIMAL": "numeric",
    "BOOLEAN": "boolean",
    "DATE": "date",
    "DATETIME": "datetime",
    "TIMESTAMP": "timestamp",
    "TIME": "time",
    "STRING": "string",
    "TEXT": "text",
    "VARCHAR": "string",
    "UUID": "uuid",
    "JSON": "json",
    "JSONB": "json",
    "BLOB": "blob",
    "BYTES": "blob",
    "ENUM": "enum",
    "ARRAY": "array",
}


def _short_type(sql_type: Any) -> str:
    """Render a SQLAlchemy type as a short, Mermaid-friendly string.

    We collapse parameterized types (``VARCHAR(255)``, ``NUMERIC(10, 5)``)
    to a single short token (``string``, ``numeric``) so Mermaid doesn't
    have to deal with parentheses/commas inside its label grammar.
    """
    cls_name = type(sql_type).__name__.upper()
    # SQLAlchemy exposes the underlying DB type name on ``.impl`` for some
    # wrappers; fall back to the class name.
    impl_obj = getattr(sql_type, "impl", sql_type)
    impl_name = type(impl_obj).__name__.upper()
    name = cls_name if cls_name in _TYPE_MAP else impl_name
    return _TYPE_MAP.get(name, cls_name.lower())


def _mermaid_type(sql_type: Any) -> str:
    """Public alias used in column rendering."""
    return _short_type(sql_type)


def _escape(value: str) -> str:
    """Escape characters that Mermaid treats specially inside labels."""
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("|", "\\|")
        .replace("\n", " ")
    )


def _format_column(col: Any) -> str:
    """Format a single SQLAlchemy ``Column`` for a Mermaid entity block."""
    name = _escape(col.name)
    type_name = _mermaid_type(col.type)
    parts: list[str] = [type_name, name]

    # Primary key?
    if col.primary_key:
        parts.append("PK")
    elif col.foreign_keys:
        # Only mark FK if not already a PK (composite keys handled below).
        parts.append("FK")

    # Composite PK components get an extra comment marker.
    if col.primary_key and col.foreign_keys:
        parts.append("FK")  # PK + FK (e.g. association table ids)

    # Not-null flag.
    if not col.nullable and not col.primary_key:
        parts.append("\"NOT NULL\"")

    return " ".join(parts)


def _cardinality_for_column(child_col: Any) -> tuple[str, bool]:
    """Return (right_glyph, is_identifying) for a child-side FK column.

    - ``right_glyph``: the Mermaid glyph used on the *right* side of the
      relationship arrow.  Per Mermaid's syntax the right side uses the
      *opening* brace (``o{`` for many, ``o|`` for one-or-zero).
        * ``o|`` if the FK column is ``unique=True`` *and* not part of the
          primary key – a one-to-one relation.
        * ``o{`` otherwise – a one-to-many or many-to-many via an
          association table (each parent can appear in many rows).
    - ``is_identifying``: True when the FK column is part of the child's
      primary key.  Mermaid renders such relationships with a solid line
      instead of a dashed one.
    """
    if child_col is None:
        return "o{", False
    if child_col.unique and not child_col.primary_key:
        right = "o|"  # one-to-one
    else:
        right = "o{"  # one-to-many / association
    identifying = bool(child_col.primary_key)
    return right, identifying


def render_mermaid_erdiagram(metadata: MetaData) -> str:
    """Build a Mermaid ``erDiagram`` block from ``metadata``.

    The output starts with the ``erDiagram`` keyword on its own line, then
    lists each table as an indented block and each relationship after that.
    """
    lines: list[str] = ["erDiagram"]

    # Sort tables for deterministic output.
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        lines.append(f"    {table.name} {{")
        for col in table.columns:
            lines.append(f"        {_format_column(col)}")
        lines.append("    }")
        lines.append("")  # blank line between entities for readability

    # Relationships.  In SQLAlchemy 2.0 ``Table.foreign_keys`` is a set of
    # ``ForeignKey`` objects whose ``.parent`` is the constrained column on
    # this table and ``.column`` is the referenced (parent-side) column.
    seen: set[tuple[str, str, str]] = set()
    for table in sorted(metadata.tables.values(), key=lambda t: t.name):
        for col in table.columns:
            for fk in col.foreign_keys:
                parent_col = fk.column
                parent_table = parent_col.table.name
                child_col = col
                right_glyph, is_identifying = _cardinality_for_column(child_col)
                key = (parent_table, table.name, parent_col.name)
                if key in seen:
                    continue
                seen.add(key)
                left_glyph = "||"  # parent side always has at least one row
                line_style = "--" if is_identifying else ".."
                label = _escape(fk.name or f"{parent_table}_{table.name}_fk")
                lines.append(
                    f"    {parent_table} {left_glyph}{line_style}{right_glyph} "
                    f"{table.name} : \"{label}\""
                )

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Primary generation pipeline
# ---------------------------------------------------------------------------

def render_png(metadata: MetaData, png_path: Path) -> bool:
    """Try to render a PNG via eralchemy2 + graphviz. Returns success flag."""
    try:
        from eralchemy2 import render_er  # type: ignore
    except ImportError:
        print(
            "[warn] eralchemy2 not installed; skipping PNG render. "
            "Install with `uv add eralchemy2`.",
            file=sys.stderr,
        )
        return False

    png_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        render_er(
            input=metadata,
            output=str(png_path),
            mode="graph",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[warn] eralchemy2 PNG render failed: {exc!r}", file=sys.stderr)
        return False
    return png_path.exists()


def render_mermaid(metadata: MetaData, md_path: Path) -> str:
    """Render the Mermaid ``erDiagram`` block.

    The Markdown output is produced by the hand-rolled emitter in this file
    because eralchemy2's ``mermaid_er`` mode emits an ``<img>`` tag pointing
    at ``mermaid.ink`` (a base64-encoded PNG) rather than a real Mermaid
    ``erDiagram`` block. That format works on GitHub, but it is not
    editable / searchable and it loses GitHub's native Mermaid rendering.

    eralchemy2's Mermaid output is therefore only used as a soft fallback
    if the local emitter raises (e.g. due to an exotic type we don't
    handle).
    """
    try:
        mermaid_text = render_mermaid_erdiagram(metadata)
    except Exception as exc:
        print(
            f"[warn] hand-rolled Mermaid emitter failed ({exc!r}); "
            "falling back to eralchemy2 mermaid_er output.",
            file=sys.stderr,
        )
        mermaid_text = ""
        try:
            from eralchemy2 import render_er  # type: ignore

            tmp_md = md_path.with_suffix(".eralchemy2.md")
            render_er(
                input=metadata,
                output=str(tmp_md),
                mode="mermaid_er",
            )
            if tmp_md.exists():
                mermaid_text = tmp_md.read_text(encoding="utf-8")
        except Exception as inner:  # noqa: BLE001
            print(f"[warn] eralchemy2 fallback also failed: {inner!r}", file=sys.stderr)
        finally:
            # Tidy up the eralchemy2 helper file if it differs from our target.
            helper = md_path.with_suffix(".eralchemy2.md")
            if helper.exists() and helper.resolve() != md_path.resolve():
                helper.unlink()
        if not mermaid_text:
            raise

    # Wrap in a fenced Markdown code block so it embeds cleanly in a README.
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(
        "<!-- Auto-generated by scripts/generate_erd.py. Do not edit by hand. -->\n\n"
        "```mermaid\n"
        + mermaid_text
        + "```\n",
        encoding="utf-8",
    )
    return md_path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# README integration stub
# ---------------------------------------------------------------------------

README_MARKER_START = "<!-- ERD:START -->"
README_MARKER_END = "<!-- ERD:END -->"


def update_readme_section(
    readme_path: Path,
    mermaid_md: str,
    start_marker: str = README_MARKER_START,
    end_marker: str = README_MARKER_END,
) -> bool:
    """Replace the section between ``start_marker`` and ``end_marker`` in
    ``readme_path`` with ``mermaid_md``.

    Returns ``True`` on success, ``False`` if the markers are missing or an
    error occurs.
    """
    if not readme_path.is_file():
        print(
            f"[error] README not found: {readme_path}",
            file=sys.stderr,
        )
        return False

    content = readme_path.read_text(encoding="utf-8")

    start_idx = content.find(start_marker)
    end_idx = content.find(end_marker)

    if start_idx == -1 and end_idx == -1:
        print(
            f"[error] Neither {start_marker!r} nor {end_marker!r} found in "
            f"{readme_path}. Add them manually around the section you want "
            "the ERD to replace.",
            file=sys.stderr,
        )
        return False
    if start_idx == -1:
        print(
            f"[error] {start_marker!r} not found in {readme_path}. "
            "Both markers are required.",
            file=sys.stderr,
        )
        return False
    if end_idx == -1:
        print(
            f"[error] {end_marker!r} not found in {readme_path}. "
            "Both markers are required.",
            file=sys.stderr,
        )
        return False
    if start_idx >= end_idx:
        print(
            f"[error] {start_marker!r} appears after {end_marker!r} in "
            f"{readme_path}. Check marker order.",
            file=sys.stderr,
        )
        return False

    before = content[: start_idx + len(start_marker)]
    after = content[end_idx:]

    new_content = (
        before
        + "\n\n<!-- This section is auto-generated by scripts/generate_erd.py. "
        "Do not edit by hand. -->\n\n"
        + mermaid_md.rstrip("\n")
        + "\n\n"
        + after
    )

    readme_path.write_text(new_content, encoding="utf-8")
    print(
        f"[ok] Updated ERD section in {readme_path} "
        f"({start_idx}..{end_idx})."
    )
    return True


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an ER diagram (PNG + Mermaid Markdown) from the project's "
            "SQLAlchemy models."
        ),
    )
    parser.add_argument(
        "--png",
        type=Path,
        default=Path("docs/er-diagram.png"),
        help="Output path for the rendered PNG (default: docs/er-diagram.png)",
    )
    parser.add_argument(
        "--md",
        type=Path,
        default=Path("docs/er-diagram.md"),
        help="Output path for the Mermaid Markdown (default: docs/er-diagram.md)",
    )
    parser.add_argument(
        "--update-readme",
        action="store_true",
        help="Replace the section between <!-- ERD:START --> and <!-- ERD:END --> "
        "in the project README with the generated Mermaid block",
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("README.md"),
        help="Path to the README to update when --update-readme is set",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = _parse_args(argv)

    metadata = discover_base_metadata()
    print(
        f"[info] Using SQLAlchemy MetaData with "
        f"{len(metadata.tables)} table(s): "
        f"{', '.join(sorted(metadata.tables)) or '(none)'}",
    )

    png_ok = render_png(metadata, args.png)
    md_text = render_mermaid(metadata, args.md)

    print(f"[info] PNG written to: {args.png} (ok={png_ok})")
    print(f"[info] Mermaid Markdown written to: {args.md}")

    # Lightweight syntax sanity check: must start with `erDiagram` and have
    # at least one entity block + one relationship line.
    has_kw = "erDiagram" in md_text
    has_brace = "{" in md_text and "}" in md_text
    has_relationship = "--" in md_text or ".." in md_text
    if has_kw and has_brace and (has_relationship or len(metadata.tables) < 2):
        print("[ok] Mermaid erDiagram basic syntax check passed.")
    else:
        print(
            "[fail] Mermaid erDiagram basic syntax check failed: "
            f"erDiagram={has_kw} blocks={has_brace} relationships={has_relationship}",
            file=sys.stderr,
        )
        return 1

    if args.update_readme:
        update_readme_section(args.readme, md_text)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
