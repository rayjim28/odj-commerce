"""Compatibility import for existing scripts and the Render entry point.

Implementation: backend.app
"""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("backend.app")
