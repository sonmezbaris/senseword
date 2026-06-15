"""Routers package.

A shared Jinja2Templates instance lives here so every router renders from the
same ``app/templates`` directory without re-creating it.
"""

from pathlib import Path

from fastapi.templating import Jinja2Templates

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
