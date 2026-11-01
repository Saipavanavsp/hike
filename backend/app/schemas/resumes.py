from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParsedFields(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    years_experience: float | None = None
    skills: list[str] = []
    education: list[str] = []


class ResumeOut(BaseModel):
    """Owner's view of a resume (includes the phone number)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    original_filename: str
    mime_type: str
    size_bytes: int
    parsed: ParsedFields
    skills: list[str]
    years_experience: float | None
    is_current: bool
    confirmed_at: datetime | None
    created_at: datetime
    predicted_category: str | None = None
    category_confidence: float | None = None


class ResumeConfirm(BaseModel):
    skills: list[str] = Field(max_length=60)
    years_experience: float | None = Field(default=None, ge=0, le=50)
