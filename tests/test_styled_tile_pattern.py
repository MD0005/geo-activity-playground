import numpy as np

from geo_activity_playground.features.explorer.tile_rendering import (
    DASHES_PER_TILE_EDGE,
    STRIPES_PER_TILE,
    StyledTilePattern,
    TileStyleSpec,
)

TRANSPARENT = (0.0, 0.0, 0.0, 0.0)
ORANGE = (1.0, 0.5, 0.0, 1.0)
BLUE = (0.0, 0.4, 1.0, 1.0)
GRAY = (0.5, 0.5, 0.5, 1.0)


def border(color, width=6, dashed=False) -> TileStyleSpec:
    return TileStyleSpec(TRANSPARENT, color, width, dashed, TRANSPARENT)


def fill(color) -> TileStyleSpec:
    return TileStyleSpec(color, TRANSPARENT, 0, False, TRANSPARENT)


def stripes(color) -> TileStyleSpec:
    return TileStyleSpec(TRANSPARENT, TRANSPARENT, 0, False, color)


def test_two_borders_are_nested_and_leave_the_core_transparent():
    rgba = StyledTilePattern([border(ORANGE), border(BLUE)]).rasterize((256, 256))

    assert np.allclose(rgba[0, 128], ORANGE)
    assert np.allclose(rgba[6, 128], BLUE)
    assert rgba[128, 128, 3] == 0.0


def test_single_border_leaves_the_core_transparent():
    rgba = StyledTilePattern([border(ORANGE)]).rasterize((256, 256))

    assert np.allclose(rgba[0, 128], ORANGE)
    assert rgba[128, 128, 3] == 0.0


def test_borders_stay_one_pixel_wide_on_small_tiles():
    rgba = StyledTilePattern([border(ORANGE), border(BLUE)]).rasterize((8, 8))

    assert np.allclose(rgba[0, 4], ORANGE)
    assert np.allclose(rgba[1, 4], BLUE)
    assert rgba[4, 4, 3] == 0.0


def test_inner_border_is_dropped_when_there_is_no_room():
    rgba = StyledTilePattern([border(ORANGE), border(BLUE)]).rasterize((1, 1))

    assert np.allclose(rgba[0, 0], ORANGE)


def test_borders_never_reach_outside_the_tile():
    """Adjacent tiles cannot overlap because every border stays within its array."""
    rgba = StyledTilePattern([border(ORANGE), border(BLUE)]).rasterize((64, 64))

    assert rgba.shape == (64, 64, 4)
    assert np.all(rgba[..., 3] <= 1.0)


def test_transparent_border_does_not_consume_nesting_space():
    rgba = StyledTilePattern([border(TRANSPARENT), border(BLUE)]).rasterize((256, 256))

    assert np.allclose(rgba[0, 128], BLUE)


def test_border_width_scales_with_the_tile_size():
    rgba = StyledTilePattern([border(ORANGE, width=32)]).rasterize((128, 128))

    assert np.allclose(rgba[15, 64], ORANGE)
    assert rgba[16, 64, 3] == 0.0


def test_dashed_border_alternates_along_the_edge():
    rgba = StyledTilePattern([border(ORANGE, dashed=True)]).rasterize((256, 256))
    top_alpha = rgba[0, :, 3]

    assert top_alpha[0] == 1.0
    assert top_alpha[16] == 0.0
    assert top_alpha[32] == 1.0
    interior = top_alpha[6:250] > 0
    dash_starts = np.count_nonzero(interior[1:] & ~interior[:-1])
    assert dash_starts == DASHES_PER_TILE_EDGE - 1


def test_stripe_count_is_independent_of_the_tile_size():
    def stripe_runs(width: int) -> int:
        alpha = StyledTilePattern([stripes(GRAY)]).rasterize((width, width))[0, :, 3]
        return int(np.count_nonzero(np.diff(alpha > 0)))

    assert stripe_runs(256) == stripe_runs(64)
    assert stripe_runs(256) == STRIPES_PER_TILE - 1


def test_fills_are_alpha_composited_with_the_first_style_on_top():
    top = (1.0, 0.0, 0.0, 0.5)
    rgba = StyledTilePattern([fill(top), fill(BLUE)]).rasterize((16, 16))

    assert np.allclose(rgba[8, 8], (0.5, 0.2, 0.5, 1.0), atol=1e-6)
