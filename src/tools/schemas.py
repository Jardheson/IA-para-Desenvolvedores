from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KBItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    id: str
    title: str
    category: str = ""
    summary: str = ""
    similarity: float = Field(default=0.0, ge=0.0, le=1.0)


class KBQueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)

    @field_validator("query")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


class KBQueryResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    query: str
    items: list[KBItem]
    fallback: bool = False
    error_message: str | None = None
    retry_count: int = 0
    duration_ms: int = 0
    meta: dict[str, Any] = {}
