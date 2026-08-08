import io

import numpy as np
from flask import Flask
from PIL import Image

from geo_activity_playground.core.tile_visits import (
    get_first_visits_for_activity,
    get_latest_new_tiles_activity_id,
)

RED = (228, 26, 28)


def _tile_pixels(client, zoom: int, z: int, x: int, y: int) -> np.ndarray:
    response = client.get(f"/explorer/{zoom}/latest-new-tiles-activity/{z}/{x}/{y}.png")
    assert response.status_code == 200
    return np.array(Image.open(io.BytesIO(response.data)).convert("RGBA"))


def test_latest_activity_track_is_drawn_in_red(
    seeded_app: Flask, seeded_client
) -> None:
    with seeded_app.app_context():
        activity_id = get_latest_new_tiles_activity_id(14)
        assert activity_id is not None
        visits = get_first_visits_for_activity(activity_id, zoom=14)
        assert visits

    tile = visits[0]
    pixels = _tile_pixels(seeded_client, 14, 14, tile.tile_x, tile.tile_y)
    drawn = pixels[pixels[:, :, 3] > 0]
    assert len(drawn) > 0
    assert set(map(tuple, np.unique(drawn[:, :3], axis=0))) == {RED}


def test_tile_without_the_activity_is_transparent(
    seeded_app: Flask, seeded_client
) -> None:
    with seeded_app.app_context():
        activity_id = get_latest_new_tiles_activity_id(14)
        assert activity_id is not None
        visits = get_first_visits_for_activity(activity_id, zoom=14)

    tile = visits[0]
    pixels = _tile_pixels(seeded_client, 14, 14, tile.tile_x + 100, tile.tile_y + 100)
    assert not pixels[:, :, 3].any()
