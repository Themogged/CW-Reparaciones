#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


MINIMUM_PYTHON = (3, 12)


def main():
    """Run administrative tasks."""
    if sys.version_info < MINIMUM_PYTHON:
        required = ".".join(str(part) for part in MINIMUM_PYTHON)
        current = ".".join(str(part) for part in sys.version_info[:3])
        raise SystemExit(
            f"CW Reparaciones requiere Python {required} o superior; "
            f"se detectó Python {current}. Activa .venv antes de continuar."
        )
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cvww_proyect.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()
