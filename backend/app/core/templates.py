import os
import jinja2


def get_jinja_env() -> jinja2.Environment:
    """Initialize a global Jinja2 environment pointing to the app/templates directory."""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "templates")

    return jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=jinja2.select_autoescape(["html", "xml"]),
    )


# Singleton-ish pattern for the env
_jinja_env: jinja2.Environment | None = None


def render_template(template_name: str, **context) -> str:
    """Render a template from the app/templates directory."""
    global _jinja_env
    if _jinja_env is None:
        _jinja_env = get_jinja_env()
    template = _jinja_env.get_template(template_name)
    return template.render(**context)
