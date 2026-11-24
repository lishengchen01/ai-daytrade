"""Bind private push server to localhost ONLY; use trusted HTTPS tunnel in front."""
from waitress import serve
from .push_service import create_app

if __name__ == "__main__":
    serve(create_app(), host="127.0.0.1", port=8787, threads=4)
