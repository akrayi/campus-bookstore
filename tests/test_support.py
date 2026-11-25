"""Never let a default or accidentally overridden test URL write to the demo."""
import os
from urllib.parse import urlsplit


def test_url(variable, port):
    value = os.getenv(variable, f"http://127.0.0.1:{port}").rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"} or parsed.port != port:
        raise RuntimeError(f"{variable} must target the isolated test stack on localhost:{port}.")
    return value
