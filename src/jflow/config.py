"""YAML config loading and validation for jflow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


class ConfigError(Exception):
    """Raised for invalid configuration."""


@dataclass
class SourceDef:
    name: str
    type: str  # "excel", "csv", "files"
    # excel / csv
    file: Path | None = None
    sheet: str | None = None
    delimiter: str = ","
    # files
    path: Path | None = None
    recursive: bool = False
    # shared
    encoding: str = "utf-8"


@dataclass
class ForClause:
    source: str
    var: str
    join: str | None = None


@dataclass
class RenderDef:
    template: str  # file path or inline string
    template_is_inline: bool = False
    output: str | None = None
    for_clause: ForClause | None = None


@dataclass
class Config:
    sources: dict[str, SourceDef] = field(default_factory=dict)
    renders: list[RenderDef] = field(default_factory=list)
    base_dir: Path = field(default_factory=lambda: Path("."))


_JINJA_EXPR = re.compile(r"\{\{.*?\}\}")


def _parse_for(raw: dict[str, Any]) -> ForClause:
    """Parse a for: flow mapping like {products: item, join: "\\n"}."""
    join = raw.pop("join", None)
    if len(raw) != 1:
        raise ConfigError(
            f"for: must have exactly one source: variable pair, got {raw}"
        )
    source, var = next(iter(raw.items()))
    return ForClause(source=source, var=str(var), join=join)


def load_config(path: str | Path) -> Config:
    """Load and validate a jflow config file."""
    path = Path(path)
    base_dir = path.parent

    with open(path) as f:
        raw = yaml.safe_load(f)

    if not isinstance(raw, dict):
        raise ConfigError("Config must be a YAML mapping")

    # -- sources --
    sources: dict[str, SourceDef] = {}
    for name, sdef in (raw.get("sources") or {}).items():
        stype = sdef.get("type")
        if stype not in ("excel", "csv", "files"):
            raise ConfigError(f"Source '{name}': unknown type '{stype}'")

        sd = SourceDef(name=name, type=stype)

        if stype in ("excel", "csv"):
            file_val = sdef.get("file")
            if not file_val:
                raise ConfigError(f"Source '{name}': 'file' is required")
            sd.file = base_dir / file_val
            if stype == "excel":
                sd.sheet = sdef.get("sheet")
            if stype == "csv":
                sd.delimiter = sdef.get("delimiter", ",")
                sd.encoding = sdef.get("encoding", "utf-8")
        elif stype == "files":
            path_val = sdef.get("path")
            if not path_val:
                raise ConfigError(f"Source '{name}': 'path' is required")
            sd.path = base_dir / path_val
            sd.recursive = sdef.get("recursive", False)
            sd.encoding = sdef.get("encoding", "utf-8")

        sources[name] = sd

    # -- renders --
    renders: list[RenderDef] = []
    for i, rdef in enumerate(raw.get("renders") or []):
        template_raw = rdef.get("template")
        if template_raw is None:
            raise ConfigError(f"Render entry {i}: 'template' is required")

        # Detect inline vs file path: if it contains newlines or doesn't
        # end with a template extension, treat as inline
        is_inline = "\n" in str(template_raw) or not str(template_raw).endswith(
            (".j2", ".jinja", ".jinja2", ".txt", ".html")
        )

        if is_inline:
            template = str(template_raw)
        else:
            template = str(base_dir / template_raw)

        output = rdef.get("output")
        for_clause = None

        if "for" in rdef:
            for_raw = dict(rdef["for"])
            for_clause = _parse_for(for_raw)

        rd = RenderDef(
            template=template,
            template_is_inline=is_inline,
            output=str(output) if output is not None else None,
            for_clause=for_clause,
        )
        renders.append(rd)

    config = Config(sources=sources, renders=renders, base_dir=base_dir)
    _validate(config)
    return config


def _validate(config: Config) -> None:
    """Validate config constraints. Raises ConfigError."""
    for i, r in enumerate(config.renders):
        # join without for
        if r.for_clause is None:
            if r.output and _JINJA_EXPR.search(r.output):
                raise ConfigError(
                    f"Render entry {i}: Jinja expression in 'output' requires 'for'"
                )
        else:
            # for referencing undeclared source
            if r.for_clause.source not in config.sources:
                raise ConfigError(
                    f"Render entry {i}: for references undeclared source "
                    f"'{r.for_clause.source}'"
                )
            # for pointing to files source
            if config.sources[r.for_clause.source].type == "files":
                raise ConfigError(
                    f"Render entry {i}: cannot iterate over 'files' source "
                    f"'{r.for_clause.source}'"
                )

        # join without for (check on for_clause)
        # This is checked via the for_clause parsing — join is only in for:
        # But if someone puts join at render level, we should catch it
