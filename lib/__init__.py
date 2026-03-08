"""Lightweight compatibility lib for reginchecker.
This package is intentionally minimal: it provides parse_object and a
no-op (safe) log_search_if_configured used by the Flask app so the module
can run standalone in the repo.
"""

__all__ = ["util", "db"]
