import datetime

import sqlalchemy

from geo_activity_playground.core.config import ConfigAccessor
from geo_activity_playground.core.datamodel import (
    DB,
    Activity,
    DuplicateCandidate,
    get_or_make_equipment,
    get_or_make_kind,
    get_or_make_tag,
)
from geo_activity_playground.core.duplicate_matching import (
    check_for_duplicate,
    find_duplicate_candidate,
    merge_duplicate,
    pick_winner,
)
from geo_activity_playground.core.import_exclusion import ImportExclusion

START = datetime.datetime(2026, 1, 1, 10, 0, 0)


def _activity(**kwargs) -> Activity:
    defaults = {
        "name": "Ride",
        "start": START,
        "distance_km": 20.0,
        "elapsed_time": datetime.timedelta(hours=1),
    }
    defaults.update(kwargs)
    activity = Activity(**defaults)
    DB.session.add(activity)
    DB.session.commit()
    return activity


def test_find_duplicate_candidate_matches_within_tolerance(app_context) -> None:
    config = ConfigAccessor().activity_import()
    a = _activity(source="directory", upstream_id="hash-a")
    b = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=2),
    )

    assert find_duplicate_candidate(a, config) is b


def test_find_duplicate_candidate_ignores_far_apart_activities(app_context) -> None:
    config = ConfigAccessor().activity_import()
    a = _activity(source="directory", upstream_id="hash-a")
    _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=30),
    )

    assert find_duplicate_candidate(a, config) is None


def test_find_duplicate_candidate_ignores_dissimilar_distance(app_context) -> None:
    config = ConfigAccessor().activity_import()
    a = _activity(source="directory", upstream_id="hash-a", distance_km=20.0)
    _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
        distance_km=40.0,
    )

    assert find_duplicate_candidate(a, config) is None


def test_find_duplicate_candidate_ignores_same_source(app_context) -> None:
    config = ConfigAccessor().activity_import()
    a = _activity(source="directory", upstream_id="hash-a")
    _activity(
        source="directory",
        upstream_id="hash-b",
        start=START + datetime.timedelta(minutes=1),
    )

    assert find_duplicate_candidate(a, config) is None


def test_pick_winner_uses_priority(app_context) -> None:
    config = ConfigAccessor().activity_import()
    directory_activity = _activity(source="directory", upstream_id="hash-a")
    strava_activity = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
    )

    # Default priorities: directory=10, strava=20 -> directory wins.
    assert (
        pick_winner(directory_activity, strava_activity, config) is directory_activity
    )

    config.duplicate_source_priorities["strava"] = 5
    assert pick_winner(directory_activity, strava_activity, config) is strava_activity


def test_pick_winner_returns_none_on_tie(app_context) -> None:
    config = ConfigAccessor().activity_import()
    config.duplicate_source_priorities["strava"] = config.duplicate_source_priorities[
        "directory"
    ]
    a = _activity(source="directory", upstream_id="hash-a")
    b = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
    )

    assert pick_winner(a, b, config) is None


def test_merge_duplicate_transfers_associations_and_deletes_loser(app_context) -> None:
    loser = _activity(source="directory", upstream_id="hash-a")
    loser.equipment = get_or_make_equipment("Bike")
    loser.kind = get_or_make_kind("Cycling")
    loser.tags = [get_or_make_tag("commute")]
    DB.session.commit()

    winner = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
        name="Enriched name",
    )

    loser_id = loser.id
    merge_duplicate(winner, loser)

    assert DB.session.get(Activity, loser_id) is None
    assert winner.equipment is not None and winner.equipment.name == "Bike"
    assert winner.kind is not None and winner.kind.name == "Cycling"
    assert [tag.tag for tag in winner.tags] == ["commute"]

    exclusion = DB.session.scalar(sqlalchemy.select(ImportExclusion))
    assert exclusion is not None
    assert exclusion.source == "directory"
    assert exclusion.upstream_id == "hash-a"
    assert exclusion.reason == "merged_duplicate"


def test_check_for_duplicate_flags_candidate_by_default(app_context) -> None:
    config = ConfigAccessor().activity_import()
    config.duplicate_matching_enabled = True
    # `a` stands in for an activity imported in an earlier scan; the hook only
    # ever runs once per activity, right after it is freshly imported.
    a = _activity(source="directory", upstream_id="hash-a")
    b = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
    )

    check_for_duplicate(b, config)

    candidates = DB.session.scalars(sqlalchemy.select(DuplicateCandidate)).all()
    assert len(candidates) == 1
    assert DB.session.get(Activity, a.id) is not None
    assert DB.session.get(Activity, b.id) is not None


def test_check_for_duplicate_auto_resolves_when_enabled(app_context) -> None:
    config = ConfigAccessor().activity_import()
    config.duplicate_matching_enabled = True
    config.duplicate_matching_auto_resolve = True
    a = _activity(source="directory", upstream_id="hash-a")
    b = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
    )
    a_id, b_id = a.id, b.id

    check_for_duplicate(b, config)

    assert DB.session.scalars(sqlalchemy.select(DuplicateCandidate)).all() == []
    # directory outranks strava by default, so it survives.
    assert DB.session.get(Activity, a_id) is not None
    assert DB.session.get(Activity, b_id) is None


def test_check_for_duplicate_does_nothing_when_disabled(app_context) -> None:
    config = ConfigAccessor().activity_import()
    a = _activity(source="directory", upstream_id="hash-a")
    b = _activity(
        source="strava",
        upstream_id="123",
        start=START + datetime.timedelta(minutes=1),
    )

    check_for_duplicate(b, config)

    assert DB.session.scalars(sqlalchemy.select(DuplicateCandidate)).all() == []
    assert DB.session.get(Activity, a.id) is not None
    assert DB.session.get(Activity, b.id) is not None
