from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class Assessment(BaseModel):
    """Canonical SHL catalog record used by retrieval and citations."""

    model_config = ConfigDict(extra="allow")

    name: str
    description: str = ""
    skills_measured: list[str] = Field(default_factory=list)
    duration: int | None = Field(default=None, description="Duration in minutes when available")
    remote_testing: bool | None = None
    languages: list[str] = Field(default_factory=list)
    test_type: str = ""
    job_level: list[str] = Field(default_factory=list)
    assessment_family: str = ""
    catalog_url: HttpUrl
    structured_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("assessment name is required")
        return value

    @property
    def search_text(self) -> str:
        fields = [
            self.name,
            self.description,
            " ".join(self.skills_measured),
            self.test_type,
            " ".join(self.job_level),
            self.assessment_family,
            " ".join(self.languages),
        ]
        metadata_text = " ".join(str(v) for v in self.structured_metadata.values())
        return "\n".join(part for part in fields + [metadata_text] if part)


class RankedAssessment(BaseModel):
    assessment: Assessment
    score: float
    reasons: list[str] = Field(default_factory=list)
