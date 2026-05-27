from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

LLMDecisionClass = Literal["exact_match", "possible_match", "no_match", "human_review"]


class LLMDecision(BaseModel):
    decision: LLMDecisionClass
    confidence: float = Field(ge=0.0, le=1.0)
    candidate_product_ids: list[str] = Field(default_factory=list)
    reason: str


class LLMReason(StrEnum):
    LLM_POSSIBLE_MATCH = "llm_possible_match"
    LLM_NO_MATCH = "llm_no_match"
    LLM_HUMAN_REVIEW = "llm_human_review"
    LLM_UNAVAILABLE = "llm_unavailable"


@dataclass
class MatchResult:
    decision: LLMDecision
    prompt_version: str
    output_text: str
