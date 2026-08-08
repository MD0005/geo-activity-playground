"""Explorer tile state for an arbitrary activity filter.

The stored tile visits, cluster membership and square all describe one fixed
set of activities: the one selected by the explorer filter in the settings. To
honor a search filter on the map pages, the same quantities have to be derived
from ``ActivityTile``, which records every activity unconditionally.

The viewport-limited parts are queried directly because they are small. The
cluster is a global property, so it is computed once per filter and cached.
"""

import datetime
import hashlib
import json
import logging
import threading
import zlib

import pandas as pd
import sqlalchemy as sa

from ...core.coordinates import Bounds
from ...core.datamodel import DB, Activity, ActivityTile
from ...core.tile_visits import TileInfo
from .clustering import (
    _find_root,
    compute_current_cluster_state,
    compute_max_square,
    get_counted_inaccessible_tiles,
)
from .model import FilteredClusterCache

logger = logging.getLogger(__name__)

# Deduplication happens on two levels, because the server runs several worker
# processes with several threads each. This lock only covers the threads of one
# worker; across workers the stored row is what prevents repeated work. That is
# a check rather than a mutex, so a cold cache can still be computed once per
# worker. Holding a database lock for the whole computation instead would block
# the other workers for seconds, which is the worse trade.
_compute_lock = threading.Lock()
_process_cache: dict[tuple[str, int], tuple[int, "FilteredClusterState"]] = {}
_PROCESS_CACHE_SIZE = 4


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

    def __init__(
        self,
        membership: dict[tuple[int, int], tuple[int, int]],
        square: tuple[int | None, int | None, int],
    ) -> None:
        self.membership = membership
        self.square_x, self.square_y, self.max_square_size = square

        sizes: dict[tuple[int, int], int] = {}
        for root in membership.values():
            sizes[root] = sizes.get(root, 0) + 1
        self.max_cluster_id = max(sizes, key=sizes.get, default=None)
        self.max_cluster_size = sizes.get(self.max_cluster_id, 0)
        self.num_cluster_tiles = len(membership)

    @classmethod
    def from_tiles(cls, tiles: set[tuple[int, int]]) -> "FilteredClusterState":
        state = compute_current_cluster_state(tiles)
        return cls(
            {tile: _find_root(state.parents, tile) for tile in state.cluster_tiles},
            compute_max_square(tiles),
        )

    def to_payload(self) -> bytes:
        return zlib.compress(
            json.dumps(
                {
                    "membership": [
                        [tile[0], tile[1], root[0], root[1]]
                        for tile, root in sorted(self.membership.items())
                    ],
                    "square": [self.square_x, self.square_y, self.max_square_size],
                },
                separators=(",", ":"),
            ).encode()
        )

    @classmethod
    def from_payload(cls, payload: bytes) -> "FilteredClusterState":
        raw = json.loads(zlib.decompress(payload))
        return cls(
            {(e[0], e[1]): (e[2], e[3]) for e in raw["membership"]},
            tuple(raw["square"]),  # type: ignore[arg-type]
        )


def _query_hash(activity_ids: frozenset[int]) -> str:
    return hashlib.sha256(",".join(map(str, sorted(activity_ids))).encode()).hexdigest()


def _compute_filtered_cluster_state(
    zoom: int, activity_ids: frozenset[int]
) -> FilteredClusterState:
    logger.info(f"Computing filtered cluster state for {zoom=}.")
    tiles = get_filtered_visited_tiles(
        zoom, activity_ids
    ) | get_counted_inaccessible_tiles(zoom)
    return FilteredClusterState.from_tiles(tiles)


def _store_filtered_cluster_state(
    query_hash: str, zoom: int, generation: int, state: FilteredClusterState
) -> None:
    """Write the cache row, tolerating a worker that got there first.

    Two workers can compute the same cold entry at the same time, in which case
    the second insert hits the unique constraint. Both computed the same thing,
    so losing the race is not an error.
    """
    payload = state.to_payload()
    now = datetime.datetime.now()
    try:
        row = DB.session.scalar(
            sa.select(FilteredClusterCache).where(
                FilteredClusterCache.query_hash == query_hash,
                FilteredClusterCache.zoom == zoom,
            )
        )
        if row is None:
            row = FilteredClusterCache(query_hash=query_hash, zoom=zoom)
            DB.session.add(row)
        row.generation = generation
        row.payload = payload
        row.last_used = now
        DB.session.commit()
    except sa.exc.IntegrityError:
        DB.session.rollback()
        logger.debug("Another worker stored the same filtered cluster state first.")
    except sa.exc.OperationalError:
        DB.session.rollback()
        logger.warning("Could not store the filtered cluster state, continuing.")


def get_filtered_cluster_state(
    zoom: int, activity_ids: frozenset[int]
) -> FilteredClusterState:
    """Cluster state of a filtered tile set, computed at most once per filter.

    A map view issues many tile image requests under the same filter, spread
    over several worker processes. The database row is what they share; the
    small per-process cache in front of it only avoids the repeated read.
    """
    generation = _activity_tile_generation()
    query_hash = _query_hash(activity_ids)

    cached = _process_cache.get((query_hash, zoom))
    if cached is not None and cached[0] == generation:
        return cached[1]

    with _compute_lock:
        # Another thread of this worker may have finished while we waited.
        cached = _process_cache.get((query_hash, zoom))
        if cached is not None and cached[0] == generation:
            return cached[1]

        row = DB.session.scalar(
            sa.select(FilteredClusterCache).where(
                FilteredClusterCache.query_hash == query_hash,
                FilteredClusterCache.zoom == zoom,
            )
        )
        if row is not None and row.generation == generation:
            state = FilteredClusterState.from_payload(row.payload)
            row.last_used = datetime.datetime.now()
            DB.session.commit()
        else:
            state = _compute_filtered_cluster_state(zoom, activity_ids)
            _store_filtered_cluster_state(query_hash, zoom, generation, state)

        _process_cache[(query_hash, zoom)] = (generation, state)
        while len(_process_cache) > _PROCESS_CACHE_SIZE:
            _process_cache.pop(next(iter(_process_cache)))
        return state


def delete_filtered_cluster_cache() -> int:
    """Drop every cached filtered cluster state."""
    _process_cache.clear()
    result = DB.session.execute(sa.delete(FilteredClusterCache))
    DB.session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def delete_stale_filtered_cluster_cache(older_than: datetime.datetime) -> int:
    """Drop cached states that have not been used since ``older_than``.

    Every distinct filter a user tries leaves a row behind, so without this the
    table grows with the searches rather than with the data.
    """
    _process_cache.clear()
    result = DB.session.execute(
        sa.delete(FilteredClusterCache).where(
            sa.or_(
                FilteredClusterCache.last_used.is_(None),
                FilteredClusterCache.last_used < older_than,
            )
        )
    )
    DB.session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def delete_outdated_filtered_cluster_cache() -> int:
    """Drop cached states that no longer match the stored activity tiles."""
    _process_cache.clear()
    result = DB.session.execute(
        sa.delete(FilteredClusterCache).where(
            FilteredClusterCache.generation != _activity_tile_generation()
        )
    )
    DB.session.commit()
    return int(getattr(result, "rowcount", 0) or 0)


def get_filtered_cluster_cache_stats() -> tuple[int, int]:
    """Number of cached states and their total compressed size in bytes."""
    row = DB.session.execute(
        sa.select(
            sa.func.count(FilteredClusterCache.id),
            sa.func.sum(sa.func.length(FilteredClusterCache.payload)),
        )
    ).one()
    return int(row[0] or 0), int(row[1] or 0)
