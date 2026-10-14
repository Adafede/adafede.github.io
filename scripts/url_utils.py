"""Helpers for safely matching URL schemes and hostnames."""

from urllib.parse import urlsplit


def url_hostname(value: object) -> str | None:
    """Return an HTTP(S) URL hostname, or None for other or invalid URLs."""
    if not isinstance(value, str):
        return None

    try:
        parsed = urlsplit(value.strip())
        hostname = parsed.hostname
    except ValueError:
        return None

    if parsed.scheme.lower() not in {"", "http", "https"} or not parsed.netloc:
        return None
    return hostname.rstrip(".").lower() if hostname else None


def url_scheme(value: object) -> str:
    """Return the normalized URL scheme, or an empty string if it is invalid."""
    if not isinstance(value, str):
        return ""
    try:
        return urlsplit(value.strip()).scheme.lower()
    except ValueError:
        return ""


def url_has_host(value: object, *domains: str) -> bool:
    """Match an exact hostname or its subdomain, never a path or suffix."""
    hostname = url_hostname(value)
    if not hostname:
        return False
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in (name.lower().rstrip(".") for name in domains)
    )
