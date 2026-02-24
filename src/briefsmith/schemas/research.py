"""Research findings schema."""

from pydantic import BaseModel


class ResearchFindings(BaseModel):
    """Market summary, competitors, positioning, proof points, risks."""

    market_summary: str
    competitor_notes: list[str] = []
    positioning_angles: list[str] = []
    proof_points: list[str] = []
    risks: list[str] = []
