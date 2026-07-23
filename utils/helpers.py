import os


def required_env(name):
    """Return the value of a required environment variable, or raise RuntimeError."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
