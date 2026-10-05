"""
Pagination utility helpers.
"""

from __future__ import annotations

import math


def paginate(
    total: int,
    page: int,
    page_size: int,
) -> dict:
    """Compute pagination metadata.

    Args:
        total: Total number of records matching the query.
        page: Requested page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        A dict with ``total``, ``page``, ``page_size``, and ``total_pages``.
    """
    total_pages = math.ceil(total / page_size) if page_size > 0 else 1
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, total_pages),
    }


def get_offset(page: int, page_size: int) -> int:
    """Compute the SQL OFFSET value for the given page.

    Args:
        page: Current page number (1-indexed).
        page_size: Number of items per page.

    Returns:
        The integer OFFSET to use in a SQL LIMIT/OFFSET clause.
    """
    return (max(1, page) - 1) * page_size
