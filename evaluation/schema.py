from pydantic import BaseModel, Field


class PartialJudgment(BaseModel):
    score: int = Field(..., ge=1, le=3)
    reasoning: str


class Judgment(BaseModel):
    context_relevance_score: int = Field(..., ge=1, le=3)
    context_relevance_reasoning: str
    groundedness_score: int = Field(..., ge=1, le=3)
    groundedness_reasoning: str
    answer_relevance_score: int = Field(..., ge=1, le=3)
    answer_relevance_reasoning: str


# JSON_schema = {
#     "type": "object",
#     "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
#     "required": ["name", "age"],
# }
