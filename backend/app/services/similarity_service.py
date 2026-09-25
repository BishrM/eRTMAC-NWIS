"""Explainable multi-factor well-similarity engine (Milestone 4).

Given a reference well, ranks other wells by a weighted combination of
independently-normalized factors, each computed from real fields already
in the DB (SODIR metadata + Volve trajectories). No factor is fabricated:
a factor unavailable for a given pair (missing MD/TVD/location/trajectory
on either side) is dropped from that pair's weighted average, and the
per-factor breakdown always reports whether it was available.

Geographic proximity is deliberately treated as a *candidate filter*
(requirement: distance is not the sole similarity criterion) — a well
must be within `max_distance_km` of the reference to be considered a
candidate at all, and must additionally have at least
`min_factors_for_ranking` computable factors (proximity plus >=1 more)
to actually be ranked. This keeps a merely-nearby well with no other
comparable data out of the results, rather than ranking it on distance
alone.

Extensibility: every factor is one entry in `FACTORS`, each a `(key,
label, weight-getter, compute-function)` tuple sharing the same
`(reference_ctx, candidate_ctx, config) -> (score, detail)` signature.
Adding formation or drilling-context similarity later means adding one
more `_Factor` entry (and a weight field on `SimilarityWeights`) — the
ranking loop itself does not need to change.

Not a validated probability or field-tested prediction — see
app.schemas.similarity.SIMILARITY_DISCLAIMER, included in every response.
"""

from dataclasses import dataclass, field
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.well import Well
from app.models.wellbore import Wellbore
from app.schemas.similarity import FactorScore, SimilarWellResult, SimilarWellsResponse
from app.services.geo import geodesic_distance_km, linestring_endpoints, point_to_lonlat


@dataclass(frozen=True)
class SimilarityWeights:
    """Relative importance of each factor. Not required to sum to 1 —
    the engine renormalizes over whichever factors are available for a
    given pair (see module docstring)."""

    geographic_proximity: float = 0.25
    total_depth_md: float = 0.35
    tvd: float = 0.25
    trajectory_deviation: float = 0.15


@dataclass(frozen=True)
class SimilarityConfig:
    """Every magic number the engine uses, in one place — never
    hardcoded inline in the scoring logic itself."""

    weights: SimilarityWeights = field(default_factory=SimilarityWeights)

    # Candidate filter: a well beyond this distance is not considered at
    # all (see module docstring). Also the normalization scale for the
    # geographic_proximity factor itself.
    max_distance_km: float = 50.0

    # Difference (in the stated unit) at which a factor's score reaches
    # exactly 0 — a linear falloff from 1.0 at zero difference.
    md_scale_m: float = 2000.0
    tvd_scale_m: float = 2000.0
    deviation_scale: float = 0.5  # difference in departure/MD ratio, a unitless [0,1] measure

    # A candidate must have at least this many computable factors
    # (geographic proximity + at least one more) to be ranked at all —
    # operationalizes "distance is not the sole similarity criterion".
    min_factors_for_ranking: int = 2


DEFAULT_CONFIG = SimilarityConfig()


@dataclass(frozen=True)
class _WellContext:
    well_id: str
    name: str
    field: str | None
    lonlat: tuple[float, float] | None
    md_m: float | None
    tvd_m: float | None
    deviation_ratio: float | None  # horizontal departure / MD of the deepest surveyed leg, if any


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _load_best_trajectory_wellbore(db: Session, well: Well) -> Wellbore | None:
    """The wellbore under this well with real trajectory data, preferring
    the deepest one if more than one qualifies (none of the wells in the
    current dataset have more than one, but a well can have several
    wellbores/sidetracks in general)."""
    return (
        db.execute(
            select(Wellbore)
            .where(
                Wellbore.well_id == well.id,
                Wellbore.trajectory.is_not(None),
                Wellbore.md_bottom_m.is_not(None),
            )
            .order_by(Wellbore.md_bottom_m.desc())
        )
        .scalars()
        .first()
    )


def _load_well_context(db: Session, well: Well) -> _WellContext:
    deviation_ratio: float | None = None
    wellbore = _load_best_trajectory_wellbore(db, well)
    if wellbore is not None and wellbore.md_bottom_m and wellbore.md_bottom_m > 0:
        endpoints = linestring_endpoints(wellbore.trajectory)
        if endpoints is not None:
            departure_m = geodesic_distance_km(*endpoints) * 1000.0
            deviation_ratio = _clamp(departure_m / wellbore.md_bottom_m)

    return _WellContext(
        well_id=well.well_id,
        name=well.name,
        field=well.field,
        lonlat=point_to_lonlat(well.location),
        md_m=well.total_depth_md_m,
        tvd_m=well.total_depth_tvd_m,
        deviation_ratio=deviation_ratio,
    )


def _geo_factor(
    ref: _WellContext, cand: _WellContext, config: SimilarityConfig
) -> tuple[float | None, str]:
    if ref.lonlat is None or cand.lonlat is None:
        return None, "surface location unavailable for one or both wells"
    distance_km = geodesic_distance_km(ref.lonlat, cand.lonlat)
    score = _clamp(1.0 - distance_km / config.max_distance_km)
    return score, f"{distance_km:.2f} km apart (candidate radius {config.max_distance_km:.0f} km)"


def _md_factor(
    ref: _WellContext, cand: _WellContext, config: SimilarityConfig
) -> tuple[float | None, str]:
    if ref.md_m is None or cand.md_m is None:
        return None, "total depth (MD) missing for one or both wells"
    diff = abs(ref.md_m - cand.md_m)
    score = _clamp(1.0 - diff / config.md_scale_m)
    return score, f"MD difference {diff:.0f} m ({ref.md_m:.0f} m vs {cand.md_m:.0f} m)"


def _tvd_factor(
    ref: _WellContext, cand: _WellContext, config: SimilarityConfig
) -> tuple[float | None, str]:
    if ref.tvd_m is None or cand.tvd_m is None:
        return None, "TVD missing for one or both wells"
    diff = abs(ref.tvd_m - cand.tvd_m)
    score = _clamp(1.0 - diff / config.tvd_scale_m)
    return score, f"TVD difference {diff:.0f} m ({ref.tvd_m:.0f} m vs {cand.tvd_m:.0f} m)"


def _trajectory_factor(
    ref: _WellContext, cand: _WellContext, config: SimilarityConfig
) -> tuple[float | None, str]:
    if ref.deviation_ratio is None or cand.deviation_ratio is None:
        return None, "insufficient real trajectory data for one or both wells"
    diff = abs(ref.deviation_ratio - cand.deviation_ratio)
    score = _clamp(1.0 - diff / config.deviation_scale)
    return score, (
        f"deviation-ratio difference {diff:.2f} (departure/MD of the deepest surveyed leg: "
        f"{ref.deviation_ratio:.2f} vs {cand.deviation_ratio:.2f})"
    )


@dataclass(frozen=True)
class _Factor:
    key: str
    label: str
    weight_of: Callable[[SimilarityConfig], float]
    compute: Callable[[_WellContext, _WellContext, SimilarityConfig], tuple[float | None, str]]


# The only place new similarity factors need to be registered (e.g.
# formation match, drilling-context similarity — see module docstring).
FACTORS: list[_Factor] = [
    _Factor("geographic_proximity", "Geographic proximity", lambda c: c.weights.geographic_proximity, _geo_factor),
    _Factor("total_depth_md", "Total depth (MD)", lambda c: c.weights.total_depth_md, _md_factor),
    _Factor("tvd", "True vertical depth", lambda c: c.weights.tvd, _tvd_factor),
    _Factor(
        "trajectory_deviation", "Trajectory deviation", lambda c: c.weights.trajectory_deviation, _trajectory_factor
    ),
]


def find_similar_wells(
    db: Session,
    well_id: str,
    top_k: int = 10,
    config: SimilarityConfig = DEFAULT_CONFIG,
) -> SimilarWellsResponse | None:
    """Returns None only if `well_id` itself doesn't exist (route maps
    that to 404) — an existing reference well with no viable candidates
    (e.g. it has no surface location, so the geographic candidate filter
    can't be applied to anything) still returns a response, with an
    empty `results` list."""
    reference = db.execute(select(Well).where(Well.well_id == well_id)).scalar_one_or_none()
    if reference is None:
        return None

    ref_ctx = _load_well_context(db, reference)
    candidates = db.execute(select(Well).where(Well.well_id != well_id)).scalars().all()

    scored: list[tuple[float, float, Well, list[FactorScore]]] = []
    for well in candidates:
        cand_ctx = _load_well_context(db, well)

        # Candidate filter (requirement: distance is a filter, not the
        # sole criterion) — geographic proximity must be computable and
        # within range for a well to be considered at all.
        if ref_ctx.lonlat is None or cand_ctx.lonlat is None:
            continue
        distance_km = geodesic_distance_km(ref_ctx.lonlat, cand_ctx.lonlat)
        if distance_km > config.max_distance_km:
            continue

        factor_scores: list[FactorScore] = []
        weighted_sum = 0.0
        weight_total = 0.0
        available_count = 0
        for factor in FACTORS:
            score, detail = factor.compute(ref_ctx, cand_ctx, config)
            weight = factor.weight_of(config)
            available = score is not None
            if available:
                weighted_sum += weight * score
                weight_total += weight
                available_count += 1
            factor_scores.append(
                FactorScore(key=factor.key, label=factor.label, weight=weight, score=score, available=available, detail=detail)
            )

        if available_count < config.min_factors_for_ranking:
            continue  # insufficient data for a meaningful comparison

        overall = weighted_sum / weight_total if weight_total > 0 else 0.0
        scored.append((overall, distance_km, well, factor_scores))

    # Deterministic order: score desc, then well_id asc to break ties.
    scored.sort(key=lambda row: (-row[0], row[2].well_id))

    results = [
        SimilarWellResult(
            well_id=well.well_id,
            name=well.name,
            field=well.field,
            distance_km=round(distance_km, 3),
            overall_score=round(overall, 4),
            factors=factor_scores,
        )
        for overall, distance_km, well, factor_scores in scored[:top_k]
    ]

    return SimilarWellsResponse(
        reference_well_id=well_id,
        top_k=top_k,
        weights={f.key: f.weight_of(config) for f in FACTORS},
        results=results,
    )
