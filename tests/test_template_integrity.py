"""Compile every Jinja template before it reaches a live deployment."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "templates"


def test_all_templates_compile():
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)),
                      autoescape=True, undefined=StrictUndefined)
    names = sorted(p.name for p in TEMPLATE_DIR.glob("*.html"))
    assert names, "Expected storefront and admin templates"
    for name in names:
        env.get_template(name)
