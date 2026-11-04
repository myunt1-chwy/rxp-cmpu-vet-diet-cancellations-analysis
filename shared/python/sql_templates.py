"""Read and render file-based SQL with strict Jinja parameters."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined


def render_sql(path, **parameters):
    path = Path(path)
    environment = Environment(
        loader=FileSystemLoader(path.parent),
        undefined=StrictUndefined,
        keep_trailing_newline=True,
    )
    return environment.get_template(path.name).render(**parameters)


def module_sql(module_file, filename, **parameters):
    return render_sql(
        Path(module_file).parent.parent / "sql" / filename, **parameters
    )
