"""Compatibility import for existing scripts and the Render entry point.

Implementation: backend.staging_security
"""
from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("backend.staging_security")
