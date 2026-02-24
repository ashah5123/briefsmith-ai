"""Input schema for the brief workflow."""

from pydantic import BaseModel, field_validator


class BriefInput(BaseModel):
    """Structured input for generating a product/marketing brief."""

    product_name: str
    product_description: str
    target_audience: str
    competitors: list[str] = []
    tone: str = "clear"
    region: str = "US"
    channels: list[str] = []
    constraints: list[str] = []

    @field_validator("product_name")
    @classmethod
    def product_name_min_length(cls, v: str) -> str:
        """Ensure product_name has at least 2 characters."""
        if len(v.strip()) < 2:
            raise ValueError("product_name must have at least 2 characters")
        return v

    @field_validator("product_description")
    @classmethod
    def product_description_min_length(cls, v: str) -> str:
        """Ensure product_description has at least 20 characters."""
        if len(v.strip()) < 20:
            raise ValueError("product_description must have at least 20 characters")
        return v

    @field_validator("target_audience")
    @classmethod
    def target_audience_min_length(cls, v: str) -> str:
        """Ensure target_audience has at least 5 characters."""
        if len(v.strip()) < 5:
            raise ValueError("target_audience must have at least 5 characters")
        return v
