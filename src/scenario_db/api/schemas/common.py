from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PagedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    has_next: bool

    @classmethod
    def from_query(
        cls,
        query,
        limit: int = 50,
        offset: int = 0,
        max_limit: int = 1000,
    ) -> "PagedResponse[T]":
        limit = min(max(limit, 1), max_limit)
        total: int = query.count()
        items = query.offset(offset).limit(limit).all()
        return cls(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
            has_next=(offset + limit) < total,
        )


class ErrorResponse(BaseModel):
    error: str
    detail: str | list
