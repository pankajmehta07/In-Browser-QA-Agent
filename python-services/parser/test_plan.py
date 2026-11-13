"""Versioned storage contract; execution is integrated separately."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    action: Literal["goto", "type", "click", "check_visible", "check_contains"]
    target: str = Field(min_length=1, max_length=2000)
    value: str | None = Field(default=None, max_length=10000)

    @field_validator("target")
    @classmethod
    def nonblank_target(cls, value):
        if not value.strip():
            raise ValueError("Target must not be blank")
        return value

    @model_validator(mode="after")
    def required_value(self):
        if self.action in {"type", "check_contains"} and self.value is None:
            raise ValueError("This action requires a value")
        return self


class TestPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1]
    setup: list[PlanStep] = Field(default_factory=list, max_length=100)
    steps: list[PlanStep] = Field(min_length=1, max_length=200)
    cleanup: list[PlanStep] = Field(default_factory=list, max_length=100)

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_version(cls, value):
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value
