from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ExtractedMetadata(BaseModel):
    dato: date | None = None
    parter: list[str] | None = None
    belop: Decimal | None = None
    valuta: str | None = Field(default=None, min_length=3, max_length=3)
    nokkelvilkar: list[str] | None = None
