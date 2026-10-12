"""WSGI entry point loaded by Gunicorn or the Flask development CLI."""

from app import create_app

# Gunicorn loads this object with the import target `wsgi:app`.
app = create_app()
