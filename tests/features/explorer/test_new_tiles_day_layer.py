"""The "New Tiles & Cluster Growth" layer defaults to a whole local day.

Selecting only the last activity hid the earlier discoveries of anyone who
records a day in several files, which is common with multiple devices.
"""

import datetime as dt
import io
import uuid

import numpy as np
import pandas as pd
from PIL import Image

from geo_activity_playground.core.datamodel import DB, Activity, ActivityTile, TileVisit
from geo_activity_playground.core.tile_visits import (
    get_latest_new_tiles_day,
    get_new_tiles_activity_ids_on_day,
)

ZOOM = 14


def _add_activity(activity_id: int, iana_timezone: str | None = None) -> Activity:
    activity = Activity(
        id=activity_id,
        name=f"Activity {activity_id}",
        iana_timezone=iana_timezone,
        time_series_uuid=str(uuid.uuid4()),
    )
    DB.session.add(activity)
    DB.session.flush()
    return activity


def _add_visit(
    activity_id: int, tile_x: int, tile_y: int, first_time: dt.datetime
) -> None:
    DB.session.add(
        TileVisit(
            zoom=ZOOM,
            tile_x=tile_x,
            tile_y=tile_y,
            first_activity_id=activity_id,
            first_time=first_time,
            last_activity_id=activity_id,
            last_time=first_time,
            visit_count=1,
        )
    )


def _add_track(activity: Activity, tile_x: int, tile_y: int) -> None:
    """A short track through the middle of one tile, plus its tile index row."""
    center_x = (tile_x + 0.5) / 2**ZOOM
    center_y = (tile_y + 0.5) / 2**ZOOM
    activity.replace_time_series(
        pd.DataFrame(
            {
                "x": [center_x - 1e-5, center_x + 1e-5],
                "y": [center_y, center_y],
                "segment_id": [0, 0],
            }
        )
    )
    DB.session.add(
        ActivityTile(zoom=ZOOM, tile_x=tile_x, tile_y=tile_y, activity_id=activity.id)
    )


def _highlight_pixel(client, tile_x: int, tile_y: int, query: str = "") -> tuple:
    response = client.get(
        f"/explorer/{ZOOM}/tile/{ZOOM}/{tile_x}/{tile_y}.png"
        f"?color_strategy=latest_new{query}"
    )
    assert response.status_code == 200
    pixels = np.asarray(Image.open(io.BytesIO(response.data)).convert("RGBA"))
    return tuple(pixels[128, 128])


def _track_alpha(client, tile_x: int, tile_y: int) -> int:
    response = client.get(
        f"/explorer/{ZOOM}/latest-new-tiles-activity/{ZOOM}/{tile_x}/{tile_y}.png"
    )
    assert response.status_code == 200
    pixels = np.asarray(Image.open(io.BytesIO(response.data)).convert("RGBA"))
    return int(pixels[:, :, 3].max())


def test_every_activity_of_the_last_day_is_highlighted(client, app) -> None:
    with app.app_context():
        _add_activity(1)
        _add_activity(2)
        _add_activity(3)
        _add_visit(1, 100, 200, dt.datetime(2026, 7, 1, 9, 0))
        _add_visit(2, 101, 200, dt.datetime(2026, 8, 1, 9, 0))
        _add_visit(3, 102, 200, dt.datetime(2026, 8, 1, 17, 0))
        DB.session.commit()

        assert get_latest_new_tiles_day(ZOOM) == dt.date(2026, 8, 1)
        assert get_new_tiles_activity_ids_on_day(ZOOM, dt.date(2026, 8, 1)) == {2, 3}

    morning = _highlight_pixel(client, 101, 200)
    afternoon = _highlight_pixel(client, 102, 200)
    earlier_day = _highlight_pixel(client, 100, 200)

    # Both of the day's rides read as new; only the older day falls back to the
    # plain "visited" fill.
    assert morning == afternoon
    assert morning != earlier_day
    assert earlier_day[3] > 0


def test_local_day_groups_activities_across_utc_midnight(client, app) -> None:
    with app.app_context():
        _add_activity(1, iana_timezone="Europe/Berlin")
        _add_activity(2, iana_timezone="Europe/Berlin")
        # 00:30 and 07:00 Berlin time on August 2, recorded on either side of
        # midnight UTC.
        _add_visit(1, 101, 200, dt.datetime(2026, 8, 1, 22, 30))
        _add_visit(2, 102, 200, dt.datetime(2026, 8, 2, 5, 0))
        DB.session.commit()

        assert get_latest_new_tiles_day(ZOOM) == dt.date(2026, 8, 2)
        assert get_new_tiles_activity_ids_on_day(ZOOM, dt.date(2026, 8, 2)) == {1, 2}

    assert _highlight_pixel(client, 101, 200) == _highlight_pixel(client, 102, 200)


def test_explicit_activity_id_still_selects_one_activity(client, app) -> None:
    with app.app_context():
        _add_activity(1)
        _add_activity(2)
        _add_visit(1, 101, 200, dt.datetime(2026, 8, 1, 9, 0))
        _add_visit(2, 102, 200, dt.datetime(2026, 8, 1, 17, 0))
        DB.session.commit()

    selected = _highlight_pixel(client, 101, 200, "&activity_id=1")
    not_selected = _highlight_pixel(client, 102, 200, "&activity_id=1")
    assert selected != not_selected


def test_track_layer_draws_every_activity_of_the_day(client, app) -> None:
    with app.app_context():
        first = _add_activity(1)
        second = _add_activity(2)
        _add_track(first, 101, 200)
        _add_track(second, 102, 200)
        _add_visit(1, 101, 200, dt.datetime(2026, 8, 1, 9, 0))
        _add_visit(2, 102, 200, dt.datetime(2026, 8, 1, 17, 0))
        DB.session.commit()

    assert _track_alpha(client, 101, 200) > 0
    assert _track_alpha(client, 102, 200) > 0
    assert _track_alpha(client, 150, 200) == 0
