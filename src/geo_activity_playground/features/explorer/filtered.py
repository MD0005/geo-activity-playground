"""Explorer tile state for an arbitrary activity filter.

The stored tile visits, cluster membership and square all describe one fixed
set of activities: the one selected by the explorer filter in the settings. To
honor a search filter on the map pages, the same quantities have to be derived
from ``ActivityTile``, which records every activity unconditionally.

The viewport-limited parts are queried directly because they are small. The
cluster is a global property, so it is computed once per filter and cached.
"""

import functools
import logging

import pandas as pd
import sqlalchemy as sa

from ...core.coordinates import Bounds
from ...core.datamodel import DB, Activity, ActivityTile
from ...core.tile_visits import TileInfo
from .clustering import (
    ClusterReplayState,
    _find_root,
    compute_current_cluster_state,
    compute_max_square,
    get_counted_inaccessible_tiles,
)

logger = logging.getLogger(__name__)


def _activity_tile_generation() -> int:
    """Cheap fingerprint that changes whenever activity tiles are appended."""
    return int(DB.session.scalar(sa.select(sa.func.max(ActivityTile.id))) or 0)


def get_filtered_tile_visits_in_bounds(
    zoom: int, bounds: Bounds, activity_ids: frozenset[int]
) -> dict[tuple[int, int], TileInfo]:
    """Visit info for a viewport, restricted to the given activities."""
    rows = DB.session.execute(
        sa.select(
            ActivityTile.tile_x,
            ActivityTile.tile_y,
            ActivityTile.activity_id,
            ActivityTile.time,
            Activity.start,
        )
        .join(Activity, Activity.id == ActivityTile.activity_id)
        .where(
            ActivityTile.zoom == zoom,
            ActivityTile.tile_x >= bounds.x_min,
            ActivityTile.tile_x <= bounds.x_max,
            ActivityTile.tile_y >= bounds.y_min,
            ActivityTile.tile_y <= bounds.y_max,
        )
    ).all()

    visits: dict[tuple[int, int], TileInfo] = {}
    for row in rows:
        if row.activity_id not in activity_ids:
            continue
        moment = (
            pd.Timestamp(row.time or row.start) if (row.time or row.start) else None
        )
        tile = (row.tile_x, row.tile_y)
        info = visits.get(tile)
        if info is None:
            visits[tile] = {
                "visit_count": 1,
                "first_time": moment,
                "first_id": row.activity_id,
                "last_time": moment,
                "last_id": row.activity_id,
            }
            continue
        info["visit_count"] += 1
        if moment is not None:
            if info["first_time"] is None or moment < info["first_time"]:
                info["first_time"] = moment
                info["first_id"] = row.activity_id
            if info["last_time"] is None or moment > info["last_time"]:
                info["last_time"] = moment
                info["last_id"] = row.activity_id
    return visits


def get_filtered_visited_tiles(
    zoom: int, activity_ids: frozenset[int]
) -> set[tuple[int, int]]:
    """Every tile the given activities touched at a zoom level."""
    return {
        (row.tile_x, row.tile_y)
        for row in DB.session.execute(
            sa.select(
                ActivityTile.tile_x, ActivityTile.tile_y, ActivityTile.activity_id
            ).where(ActivityTile.zoom == zoom)
        )
        if row.activity_id in activity_ids
    }


class FilteredClusterState:
    """Cluster membership and biggest square of one filtered tile set."""

    def __init__(self, state: ClusterReplayState, tiles: set[tuple[int, int]]) -> None:
        self.membership = {
            tile: _find_root(state.parents, tile) for tile in state.cluster_tiles
        }
        self.square_x, self.square_y, self.max_square_size = compute_max_square(tiles)

        sizes: dict[tuple[int, int], int] = {}
        for root in self.membership.values():
            sizes[root] = sizes.get(root, 0) + 1
        self.max_cluster_id = max(sizes, key=sizes.get, default=None)
        self.max_cluster_size = sizes.get(self.max_cluster_id, 0)
        self.num_cluster_tiles = len(self.membership)


@functools.lru_cache(maxsize=8)
def _filtered_cluster_state(
    zoom: int, activity_ids: frozenset[int], _generation: int
) -> FilteredClusterState:
    logger.info(f"Computing filtered cluster state for {zoom=}.")
    tiles = get_filtered_visited_tiles(
        zoom, activity_ids
    ) | get_counted_inaccessible_tiles(zoom)
    return FilteredClusterState(compute_current_cluster_state(tiles), tiles)


def get_filtered_cluster_state(
    zoom: int, activity_ids: frozenset[int]
) -> FilteredClusterState:
    """Cluster state of a filtered tile set, cached per filter.

    A map view issues many tile image requests under the same filter, so the
    cache turns the global computation into a once-per-view cost.
    """
    return _filtered_cluster_state(zoom, activity_ids, _activity_tile_generation())
