"""Jinja2 rendering pipeline for jflow."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from jflow.config import Config, RenderDef


def render_config(
    config: Config,
    sources: dict[str, Any],
    stdout: Any = None,
) -> None:
    """Execute all render jobs in a config."""
    stdout = stdout or sys.stdout

    env = Environment(
        loader=FileSystemLoader(str(config.base_dir)),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )

    for rdef in config.renders:
        _render_entry(env, rdef, sources, config.base_dir, stdout)


def _render_entry(
    env: Environment,
    rdef: RenderDef,
    sources: dict[str, Any],
    base_dir: Path,
    stdout: Any,
) -> None:
    """Render a single render entry."""
    context = dict(sources)

    if rdef.template_is_inline:
        template = env.from_string(rdef.template)
    else:
        # Make path relative to base_dir for the FileSystemLoader
        rel = str(Path(rdef.template).relative_to(base_dir))
        template = env.get_template(rel)

    if rdef.for_clause is not None:
        source = sources[rdef.for_clause.source]
        var_name = rdef.for_clause.var
        outputs: list[str] = []

        for row in source:
            ctx = {**context, var_name: row}
            rendered = template.render(ctx)
            outputs.append(rendered)

        if rdef.for_clause.join is not None:
            # Join all outputs and write once
            combined = rdef.for_clause.join.join(outputs)
            _write_output(combined, rdef.output, context, env, stdout)
        else:
            # Write per-row outputs
            for row, rendered in zip(source, outputs):
                ctx = {**context, var_name: row}
                _write_output(rendered, rdef.output, ctx, env, stdout)
    else:
        rendered = template.render(context)
        _write_output(rendered, rdef.output, context, env, stdout)


def _write_output(
    content: str,
    output_spec: str | None,
    context: dict[str, Any],
    env: Environment,
    stdout: Any,
) -> None:
    """Write rendered content to file or stdout."""
    if output_spec is None:
        stdout.write(content)
        return

    # Evaluate output path as Jinja2 if it contains expressions
    if "{{" in output_spec:
        path_str = env.from_string(output_spec).render(context)
    else:
        path_str = output_spec

    path = Path(path_str)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
