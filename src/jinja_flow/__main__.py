"""CLI entry point for jflow."""

from __future__ import annotations

import sys
from pathlib import Path

from jinja2 import UndefinedError

from jinja_flow.config import ConfigError, load_config
from jinja_flow.render import render_config
from jinja_flow.sources import build_source


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: jinja-flow <config.yaml>", file=sys.stderr)
        sys.exit(1)

    config_path = Path(sys.argv[1])

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
    except Exception as e:
        print(f"Error loading source: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        render_config(config, sources)
    except UndefinedError as e:
        print(f"Template error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
