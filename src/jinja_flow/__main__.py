"""CLI entry point for jinja-flow."""

from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import UndefinedError

from jinja_flow.config import ConfigError, load_config
from jinja_flow.render import render_config
from jinja_flow.sources import FileSource, TabularSource, build_source


def main() -> None:
    args = sys.argv[1:]
    debug = "--debug" in args
    if debug:
        args.remove("--debug")

    if not args:
        print("Usage: jinja-flow [--debug] <config.yaml>", file=sys.stderr)
        sys.exit(1)

    config_path = Path(args[0])

    if not config_path.is_file():
        print(f"Error: file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    try:
        config = load_config(config_path)
    except ConfigError as e:
        print(f"Config error: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        sources = {}
        for name, sdef in config.sources.items():
            sources[name] = build_source(sdef)
            if debug:
                _debug_source(name, sdef.type, sources[name])
    except Exception as e:
        print(f"Error loading source: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        render_config(config, sources)
    except UndefinedError as e:
        print(f"Template error: {e}", file=sys.stderr)
        sys.exit(1)


def _debug_source(name: str, stype: str, source: TabularSource | FileSource) -> None:
    if isinstance(source, TabularSource):
        cols = ", ".join(source.headers)
        if stype == "csv":
            print(f'  "{name}" (csv) columns: {cols}', file=sys.stderr)
        else:
            print(
                f'  "{name}" (excel) {len(source)} rows, '
                f"columns: {cols}",
                file=sys.stderr,
            )
    elif isinstance(source, FileSource):
        print(f'  "{name}" (files) {source._base}', file=sys.stderr)


if __name__ == "__main__":
    main()
