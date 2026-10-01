from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl


class ResearchBrief(BaseModel):
    topic: str = Field(min_length=10)
    geography: str
    target_customer: str
    questions: list[str] = Field(min_length=1)


class Evidence(BaseModel):
    evidence_id: str
    question: str
    finding: str
    source_title: str
    source_url: HttpUrl
    source_type: Literal["primary", "reputable_secondary", "other"]
    accessed_at: datetime

class SourceCandidate(BaseModel):
    title: str
    url: str = Field(pattern=r"^https?://")
    snippet_or_note: str
    relevance: Literal["direct", "context", "irrelevant"]

class QuestionResearch(BaseModel):
    question: str
    sources: list[SourceCandidate] = Field(default_factory=list)
    unanswered: bool = True
    gap_reason: str = ""
    search_status: Literal["ok", "search_failed"] = "ok"

class SearchPlan(BaseModel):
    queries: list[str] = Field(min_length=8, max_length=8)


class ResearchOutput(BaseModel):
    brief: ResearchBrief
    evidence: list[Evidence]
    unanswered_questions: list[str] = Field(default_factory=list)


class RunMetrics(BaseModel):
    implementation: Literal["CrewAI", "n8n"]
    elapsed_seconds: float
    estimated_cost_usd: float
    questions_answered: int
    total_questions: int
    working_source_urls: int
    total_source_urls: int