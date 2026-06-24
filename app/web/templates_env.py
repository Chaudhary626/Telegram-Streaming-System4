"""Shared Jinja2 templates instance."""
from __future__ import annotations

import os

from fastapi.templating import Jinja2Templates

from app.config import get_settings

settings = get_settings()

_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
templates = Jinja2Templates(directory=_TEMPLATE_DIR)

# Expose a few globals to all templates.
templates.env.globals["BASE_URL"] = settings.BASE_URL
templates.env.globals["ADMIN_PATH"] = settings.ADMIN_SECRET_PATH
