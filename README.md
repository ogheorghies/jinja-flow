# jflow

Renders Jinja2 templates from a declarative YAML config. Data sources — Excel, CSV, and file directories —
are declared once in config and injected into templates as named variables. Adding a new data source never requires touching code.

## Installation

```bash
pip install jinja-flow
# or run directly without installing:
uvx jinja-flow config.yaml
```

## Config file

A config file declares sources and a list of render jobs.

```yaml
sources:
  products:  { type: excel, file: data/products.xlsx, sheet: Sheet1 }
  specs:     { type: csv, file: data/specs.csv }
  docs:      { type: files, path: ./docs, recursive: true }
  contracts: { type: files, path: ./contracts }

renders:
  - output: "outputs/by-item/{{ item.name }}.txt"
    for: { products: item }
    template: prompts/analyze.j2

  - output: outputs/joined/everything.txt
    for: { products: item, join: "\n---\n" }
    template: prompts/all_prompts.j2

  # any iteration (if needed) done inside the template
  # if no output:, stdout is used
  - template: prompts/internal-for.j2

  # or inline:
  - template: |-
      {% for item in products %}
      {{ item.name }}: {{ item.category }}
      ---
      {% endfor %}
```

### `sources`

Each key under `sources` becomes a named variable injected into every
template. Three source types are supported.

#### `type: excel`

Loads a worksheet from an Excel file as an iterable of row dicts.

| Key | Required | Description |
|-----|----------|-------------|
| `file` | yes | Path to the `.xlsx` file |
| `sheet` | no | Sheet name. Defaults to the first sheet |

#### `type: csv`

Loads a CSV file as an iterable of row dicts. Behaves identically to
`type: excel` in templates — same iteration, same `.lookup()` method.

| Key | Required | Description |
|-----|----------|-------------|
| `file` | yes | Path to the `.csv` file |
| `delimiter` | no | Field delimiter. Default `,` |
| `encoding` | no | File encoding. Default `utf-8` |

#### `type: files`

Wraps a directory for file lookup. Files are read as plain text.

| Key | Required | Description |
|-----|----------|-------------|
| `path` | yes | Directory path |
| `recursive` | no | Search subdirectories. Default `false` |
| `encoding` | no | File encoding. Default `utf-8` |

### `renders`

A list of render jobs.

Each render entry has the following keys:

| Key | Required | Description |
|-----|----------|-------------|
| `template` | yes | Path to a `.j2` file, or an inline block scalar (`\|-`) |
| `output` | no | Output path. Omit to write to stdout |
| `for` | no | Driver iteration config (see below). Omit for template iteration |

### Inline templates

`template` accepts either a file path or an inline block scalar. Use
`|-` to strip the trailing newline, which is almost always what you want
for prompt content.

```yaml
renders:
  - output: "outputs/{{ item.name }}.txt"
    for: { products: item }
    template: |-
      You are analyzing: {{ item.name }}
      Category: {{ item.category }}

      {% set spec = docs.find(item.name ~ "_spec.md") %}
      {% if spec %}{{ spec.content }}{% endif %}
```

Inline templates can use `{% include %}` to pull in partials:

```yaml
  - for: { products: item }
    template: |-
      {% include "prompts/header.j2" %}
      {{ item.name }}: {{ item.description }}
```

### `for:`

When present, the driver iterates a source and renders the template once
per row. All keys are inline in a flow mapping.

| Key | Required | Description |
|-----|----------|-------------|
| `{source}: {var}` | yes | Source name and the variable exposed per row |
| `join` | no | String used to join per-row outputs. Invalid without `for:` |

### Iteration modes

**Driver iteration** (`for:` present) — the driver loops over the source
and renders the template once per row. Use when you need per-row output
files, or to join rows into a single file with a separator.

```yaml
renders:
  - output: "outputs/{{ item.name }}.txt"
    for: { products: item }
    template: prompts/item.j2

  - output: outputs/all.txt
    for: { products: item, join: "\n---\n" }
    template: prompts/all.j2
```

**Template iteration** (no `for:`) — the driver renders once, the
template loops internally using `{% for %}` and `{% include %}`. Natural
when per-row output files are not needed.

```yaml
renders:
  - template: prompts/internal-for.j2
```

```jinja
{# prompts/internal-for.j2 #}
{% for item in products %}
{% include "prompts/item.j2" %}
---
{% endfor %}
```

### `output`

A plain path or Jinja2 expression. Always top-level. Omit to write to stdout.

**Per-row files** — Jinja2 expression evaluated against the current row.
Only meaningful with `for:`.

```yaml
- output: "outputs/{{ item.name }}.txt"
  for: { products: item }
  template: prompts/item.j2
```

**Single file** — plain path. Use `join` inside `for:` to concatenate
per-row outputs. `join` without `for:` is a configuration error.

```yaml
- output: outputs/all.txt
  for: { products: item, join: "\n---\n" }
  template: prompts/item.j2
```

**Stdout** — omit `output` entirely. Stdout is the default when no
output path is specified:

```yaml
- for: { products: item, join: "\n---\n" }
  template: prompts/item.j2

- template: prompts/internal-for.j2
```

## Templates

Templates are standard Jinja2 (`.j2` by convention). The following
variables are always available:

- Every source declared in `sources` — as its source object (see below)
- The iteration variable named in `for` (e.g. `item`), if driver
  iteration is used — a dict of the current row's column values

### Accessing row data

In driver iteration, the current row is accessed via the named variable:

```jinja
{{ item.name }}
{{ item.category }}
```

In template iteration, the source is accessed directly:

```jinja
{% for item in products %}
{{ item.name }}
{{ item.category }}
{% endfor %}
```

Column names come directly from the first row of the Excel or CSV file.

### `FileSource` — `type: files`

File sources expose two methods.

**`.find(pattern)`** — search for a single file by glob pattern. Returns
a `FileResult` (see below). `pattern` accepts standard glob syntax:
`*` matches any sequence of characters, `?` matches a single character,
`[seq]` matches any character in `seq`. Use `*` around a variable to
match regardless of surrounding text in the filename.

```jinja
{# exact variable substitution #}
{% set spec = docs.find(item.name ~ "_spec.md") %}

{# variable is part of a longer filename #}
{% set brief = docs.find("brief " ~ item.name ~ " final.txt") %}

{# variable somewhere in the name — wildcards either side #}
{% set f = docs.find("*" ~ item.code ~ "*.txt") %}

{# variable in the middle, fixed prefix and suffix #}
{% set f = docs.find("report_" ~ item.year ~ "_summary.md") %}
```

Returns the first match if multiple files match the pattern.

**`.list(pattern)`** — return all matching files as a list of
`FileResult` objects. Pattern defaults to `*`. Accepts the same glob
syntax as `.find()`.

```jinja
{% for f in docs.list("*.md") %}
  {{ f.name }}: {{ f.content }}
{% endfor %}
```

### `FileResult`

Returned by `.find()` and `.list()`. Always safe to use — a missing file
does not raise an exception.

| Attribute | Type | Description |
|-----------|------|-------------|
| `.exists` | `bool` | `True` if the file was found |
| `.content` | `str` | File contents. Empty string if not found |
| `.data` | `object\|None` | Parsed object for `.json` and `.yaml`/`.yml` files. `None` for all other types. Raises on malformed content |
| `.name` | `str` | Filename with extension (e.g. `spec.md`) |
| `.stem` | `str` | Filename without extension (e.g. `spec`) |
| `.path` | `Path\|None` | Absolute `Path` object, or `None` |

`FileResult` is falsy when the file does not exist, so the idiomatic
pattern is:

```jinja
{% set spec = docs.find(item.name ~ "_spec.md") %}
{% if spec %}
{{ spec.content }}
{% endif %}
```

`.data` gives parsed access to JSON and YAML files, with dot and bracket
notation:

```jinja
{% set meta = docs.find("meta_" ~ item.name ~ ".json") %}
{% if meta %}
{{ meta.data.description }}
{{ meta.data.author.name }}
{{ meta.data.tags[0] }}
{% endif %}

{% set cfg = docs.find(item.name ~ ".yaml") %}
{% if cfg %}
{{ cfg.data.version }}
{% endif %}
```

`str(result)` returns `.content`, so a `FileResult` can be interpolated
directly:

```jinja
{{ docs.find(item.name ~ "_spec.md") }}
```

### Tabular sources — `type: excel` / `type: csv`

Non-primary tabular sources (i.e. not the one named in `for`) are
available for cross-referencing via `.lookup()`.

**`.lookup(key, value)`** — return the first row where `row[key] == value`
as a dict. Returns an empty dict if not found.

```jinja
{% set meta = specs.lookup("product_id", item.product_id) %}
{% if meta %}
Version: {{ meta.version }}
{% endif %}
```

**`.rows`** — list of all rows as dicts.

**`.headers`** — list of column names.

## Example

### Directory layout

```
project/
├── config.yaml
├── render.py
├── sources.py
├── data/
│   ├── products.xlsx
│   └── specs.csv
├── docs/
│   ├── WidgetA_spec.md
│   └── WidgetB_spec.md
├── contracts/
│   └── WidgetA_contract.txt
├── prompts/
│   └── analyze.j2
└── outputs/          ← created automatically
```

### `config.yaml`

```yaml
sources:
  products:  { type: excel, file: data/products.xlsx }
  specs:     { type: csv, file: data/specs.csv }
  docs:      { type: files, path: ./docs, recursive: true }
  contracts: { type: files, path: ./contracts }

renders:
  - output: "outputs/{{ item.name }}.txt"
    for: { products: item }
    template: prompts/analyze.j2
```

### `prompts/analyze.j2`

```jinja
You are a product analyst. Analyze the following product.

## Product
Name:     {{ item.name }}
Category: {{ item.category }}
Region:   {{ item.region }}

{% set spec = docs.find(item.name ~ "_spec.md") %}
{% if spec %}
## Specification
{{ spec.content }}
{% else %}
## Specification
No specification document found for {{ item.name }}.
{% endif %}

{% set contract = contracts.find(item.name ~ "*.txt") %}
{% if contract %}
## Contract Notes
{{ contract.content }}
{% endif %}

{% set meta = specs.lookup("product_id", item.product_id) %}
{% if meta %}
## Supplementary Data
Description: {{ meta.description }}
Version:     {{ meta.version }}
{% endif %}

## Task
Summarize the product, highlight any risks, and suggest improvements.
```

### Running

```bash
# write one file per product to outputs/
uvx jinja-flow config.yaml

# preview without writing
```

## Error handling

The environment uses `StrictUndefined` — referencing a variable that does
not exist in the current context raises an `UndefinedError` immediately,
rather than silently rendering an empty string. This catches typos in
column names early.

A `FileResult` for a missing file is always safe to use — `.exists` is
`False`, `.content` is `""`, and the object is falsy. No exception is
raised for missing files unless you explicitly access `.content` on a
`None`-path result outside of the normal attribute interface.

Config validation errors are raised at load time, before any rendering
begins. The following are errors:

- `join` present in a render entry without `for` — `join` is only valid
  with driver iteration
- `output.file` using a Jinja expression (e.g. `{{ item.name }}`) without
  `for` — per-row filenames require driver iteration
- `for` referencing a source not declared in `sources`
- `iterate_over` (legacy) or `for` pointing to a `type: files` source —
  only `excel` and `csv` sources are iterable

Runtime errors raised during rendering:

- Accessing `.data` on a malformed `.json` or `.yaml` file raises
  immediately — malformed structured files are never silently ignored