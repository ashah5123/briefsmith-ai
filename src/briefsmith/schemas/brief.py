"""Brief sections: positioning, messages, objections, launch, SEO, content ideas."""

from pydantic import BaseModel


class ObjectionResponse(BaseModel):
    objection: str
    response: str


class BriefSections(BaseModel):
    """Positioning, key messages, objections, launch plan, SEO, content ideas."""

    positioning_statement: str
    key_messages: list[str]
    objections_and_responses: list[ObjectionResponse]
    launch_plan: list[str]
    seo_keywords: list[str]
    content_ideas: list[str]
