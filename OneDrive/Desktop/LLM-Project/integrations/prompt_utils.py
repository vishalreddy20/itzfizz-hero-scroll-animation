from __future__ import annotations


def render_prompt(template: str, **kwargs: str) -> str:
    rendered = template
    for key, value in kwargs.items():
        rendered = rendered.replace("{" + key + "}", str(value))
    return rendered
