from pydantic import BaseModel

SIMILARITY_DISCLAIMER = (
    "Prototype similarity ranking over public analogue data (SODIR + Volve). "
    "Not a validated probability, prediction, or field-tested risk model — "
    "a decision-support aid for finding historically comparable wells."
)


class FactorScore(BaseModel):
    key: str
    label: str
    weight: float  # the configured weight for this factor
    score: float | None  # None when not available for this pair — never fabricated
    available: bool
    detail: str  # human-readable explanation, e.g. "12.4 km apart"


class SimilarWellResult(BaseModel):
    well_id: str
    name: str
    field: str | None
    distance_km: float
    overall_score: float
    factors: list[FactorScore]


class SimilarWellsResponse(BaseModel):
    reference_well_id: str
    top_k: int
    weights: dict[str, float]
    results: list[SimilarWellResult]
    disclaimer: str = SIMILARITY_DISCLAIMER
