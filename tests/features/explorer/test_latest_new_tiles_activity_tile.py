import io

import numpy as np
from flask import Flask
from PIL import Image

from geo_activity_playground.core.tile_visits import (
    get_latest_new_tiles_day,
    get_new_tiles_on_day,
)

RED = (228, 26, 28)


def _tile_pixels(client, zoom: int, z: int, x: int, y: int) -> np.ndarray:
    response = client.get(f"/explorer/{zoom}/latest-new-tiles-activity/{z}/{x}/{y}.png")
    assert response.status_code == 200
    return np.array(Image.open(io.BytesIO(response.data)).convert("RGBA"))


def test_latest_day_tracks_are_drawn_in_red(seeded_app: Flask, seeded_client) -> None:
    with seeded_app.app_context():
        day = get_latest_new_tiles_day(14)
        assert day is not None
        tiles = get_new_tiles_on_day(14, day)
        assert tiles

    tile_x, tile_y = sorted(tiles)[0]
    pixels = _tile_pixels(seeded_client, 14, 14, tile_x, tile_y)
    drawn = pixels[pixels[:, :, 3] > 0]
    assert len(drawn) > 0
    assert set(map(tuple, np.unique(drawn[:, :3], axis=0))) == {RED}


def test_tile_without_the_activity_is_transparent(
    seeded_app: Flask, seeded_client
) -> None:
    with seeded_app.app_context():
        day = get_latest_new_tiles_day(14)
        assert day is not None
        tiles = get_new_tiles_on_day(14, day)

    tile_x, tile_y = sorted(tiles)[0]
    pixels = _tile_pixels(seeded_client, 14, 14, tile_x + 100, tile_y + 100)
    assert not pixels[:, :, 3].any()
