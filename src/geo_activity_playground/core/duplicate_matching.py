import datetime
import logging

import sqlalchemy

from .datamodel import DB, Activity, ActivityImportConfig, DuplicateCandidate
from .import_exclusion import record_exclusion
from .tile_visits import remove_activity_from_tile_state

logger = logging.getLogger(__name__)


def find_duplicate_candidate(
    activity: Activity, config: ActivityImportConfig
) -> Activity | None:
    """Look for an existing activity from a different source that is likely the same ride."""
    if activity.start is None or activity.source is None:
        return None

    tolerance = datetime.timedelta(seconds=config.duplicate_time_tolerance_seconds)
    others = DB.session.scalars(
        sqlalchemy.select(Activity).filter(
            Activity.id != activity.id,
            Activity.source.is_not(None),
            Activity.source != activity.source,
            Activity.start.is_not(None),
            Activity.start >= activity.start - tolerance,
            Activity.start <= activity.start + tolerance,
        )
    ).all()
    for other in others:
        if _metrics_close(activity, other, config.duplicate_relative_tolerance):
            return other
    return None


def _metrics_close(a: Activity, b: Activity, relative_tolerance: float) -> bool:
    """Whether distance and elapsed time (where known on both sides) roughly agree."""
    checks = []
    if a.distance_km and b.distance_km:
        checks.append(
            abs(a.distance_km - b.distance_km)
            <= relative_tolerance * max(a.distance_km, b.distance_km)
        )
    if a.elapsed_time and b.elapsed_time:
        a_seconds = a.elapsed_time.total_seconds()
        b_seconds = b.elapsed_time.total_seconds()
        checks.append(
            abs(a_seconds - b_seconds) <= relative_tolerance * max(a_seconds, b_seconds)
        )
    if not checks:
        # Neither side has distance nor elapsed time to compare; fall back to
        # the start-time window alone, which the caller already applied.
        return True
    return all(checks)


def resolution_priority(source: str | None, config: ActivityImportConfig) -> int:
    """Lower wins. Sources absent from the mapping rank lowest so they never
    silently win over a source the user has actually configured."""
    if source is None:
        return 1_000_000
    return config.duplicate_source_priorities.get(source, 1_000_000)


def pick_winner(
    a: Activity, b: Activity, config: ActivityImportConfig
) -> Activity | None:
    """The higher-priority activity, or None if both sources rank equally."""
    priority_a = resolution_priority(a.source, config)
    priority_b = resolution_priority(b.source, config)
    if priority_a == priority_b:
        return None
    return a if priority_a < priority_b else b


def record_duplicate_candidate(a: Activity, b: Activity) -> DuplicateCandidate:
    activity_a_id, activity_b_id = sorted((a.id, b.id))
    existing = DB.session.scalar(
        sqlalchemy.select(DuplicateCandidate).filter(
            DuplicateCandidate.activity_a_id == activity_a_id,
            DuplicateCandidate.activity_b_id == activity_b_id,
        )
    )
    if existing is not None:
        return existing
    candidate = DuplicateCandidate(
        activity_a_id=activity_a_id,
        activity_b_id=activity_b_id,
        detected_at=datetime.datetime.now(datetime.UTC),
    )
    DB.session.add(candidate)
    DB.session.commit()
    return candidate


def merge_duplicate(winner: Activity, loser: Activity) -> None:
    """Keep `winner`, transfer the loser's user-set associations, and delete the loser."""
    if not winner.tags:
        winner.tags = list(loser.tags)
    if winner.equipment is None and loser.equipment is not None:
        winner.equipment = loser.equipment
    if winner.kind is None and loser.kind is not None:
        winner.kind = loser.kind
    for photo in list(loser.photos):
        photo.activity = winner

    for stale_candidate in DB.session.scalars(
        sqlalchemy.select(DuplicateCandidate).filter(
            sqlalchemy.or_(
                DuplicateCandidate.activity_a_id == loser.id,
                DuplicateCandidate.activity_b_id == loser.id,
                DuplicateCandidate.activity_a_id == winner.id,
                DuplicateCandidate.activity_b_id == winner.id,
            )
        )
    ).all():
        DB.session.delete(stale_candidate)

    if loser.source and loser.upstream_id:
        record_exclusion(
            loser.source,
            str(loser.upstream_id),
            "merged_duplicate",
            path=loser.path,
        )
    loser.delete_data()
    loser_id = loser.id
    DB.session.delete(loser)
    DB.session.commit()
    remove_activity_from_tile_state(loser_id)
    logger.info(
        "Merged duplicate activity %s (%s) into %s (%s).",
        loser_id,
        loser.source,
        winner.id,
        winner.source,
    )


def check_for_duplicate(activity: Activity, config: ActivityImportConfig) -> None:
    """Called right after an activity has been imported and committed."""
    if not config.duplicate_matching_enabled or activity.id is None:
        return

    candidate = find_duplicate_candidate(activity, config)
    if candidate is None:
        return

    if config.duplicate_matching_auto_resolve:
        winner = pick_winner(activity, candidate, config)
        if winner is not None:
            loser = candidate if winner is activity else activity
            merge_duplicate(winner, loser)
            return

    record_duplicate_candidate(activity, candidate)
