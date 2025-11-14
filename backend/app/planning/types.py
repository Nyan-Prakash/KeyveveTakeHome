"""Types for planning module."""

from collections.abc import Sequence

from pydantic import BaseModel, Field

from backend.app.models.plan import ChoiceFeatures, PlanV1


class BranchFeatures(BaseModel):
    """A plan branch with extracted features."""

    plan: PlanV1 = Field(description="The plan for this branch")
    features: Sequence[ChoiceFeatures] = Field(description="Features extracted from all choices in the plan")


class ScoredPlan(BaseModel):
    """A plan with a computed score."""

    plan: PlanV1 = Field(description="The plan")
    score: float = Field(description="Computed score for this plan")
    feature_vector: dict[str, float] = Field(description="Feature vector used for scoring")


class FeatureStats(BaseModel):
    """Statistics for normalizing features."""

    mean: float = Field(description="Mean value for this feature")
    std: float = Field(description="Standard deviation for this feature")
