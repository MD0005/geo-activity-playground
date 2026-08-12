import datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...core.datamodel import DB, Activity


class ExplorerTileBookmark(DB.Model):
    __tablename__ = "explorer_tile_bookmarks"
    id: Mapped[int] = mapped_column(primary_key=True)

    name: Mapped[str] = mapped_column(sa.String, nullable=False)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    def __str__(self) -> str:
        return f"{self.name} ({self.tile_x}, {self.tile_y}) @ {self.zoom}"


class ClusterHistoryEvent(DB.Model):
    __tablename__ = "cluster_history_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    event_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    activity_id: Mapped[int] = mapped_column(
        ForeignKey("activities.id", name="cluster_history_event_activity_id"),
        nullable=False,
        index=True,
    )
    activity: Mapped["Activity"] = relationship(foreign_keys=[activity_id])
    time: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime, nullable=True)
    tile_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.Index("idx_cluster_history_events_zoom_index", "zoom", "event_index"),
        sa.Index("idx_cluster_history_events_zoom_time", "zoom", "time"),
        sa.UniqueConstraint("zoom", "event_index", name="uq_cluster_history_events"),
    )


class ClusterTileActivation(DB.Model):
    """When each tile became a cluster tile, one row per cluster tile.

    Cluster membership only ever grows, so the set of cluster tiles at any
    point in the history is simply the rows up to that ``event_index``. This
    answers "what did this activity add to my cluster" and the calendar
    activation counts without replaying the history.
    """

    __tablename__ = "cluster_tile_activations"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    event_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    activity_id: Mapped[int | None] = mapped_column(
        ForeignKey("activities.id", name="cluster_tile_activation_activity_id"),
        nullable=True,
        index=True,
    )
    "``None`` for tiles that clustered at the origin of time, without a ride."
    time: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime, nullable=True)

    __table_args__ = (
        sa.Index("idx_cluster_tile_activations_zoom_event", "zoom", "event_index"),
        sa.Index("idx_cluster_tile_activations_zoom_activity", "zoom", "activity_id"),
        sa.UniqueConstraint(
            "zoom", "tile_x", "tile_y", name="uq_cluster_tile_activation_per_zoom"
        ),
    )


class ClusterHistoryStatus(DB.Model):
    """Whether the stored history of a zoom level still matches the inputs.

    The history is expensive to replay, so changes that invalidate it only set
    this flag; the replay happens when a page actually needs the history.
    """

    __tablename__ = "cluster_history_status"

    zoom: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    stale: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True)
    computed_at: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime, nullable=True
    )
    rebuilding_since: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime, nullable=True
    )
    "Set while a worker process is replaying, so the others do not join in."


class FilteredClusterCache(DB.Model):
    """Cluster state of one activity filter, shared between worker processes.

    Deriving the cluster for a filter means scanning every activity tile of a
    zoom level, which is far too much to repeat for each tile image. The server
    runs several worker processes, so an in-process cache would recompute this
    once per worker; the table is what makes it a single computation.
    """

    __tablename__ = "filtered_cluster_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(sa.String, nullable=False)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    generation: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    "Highest activity tile id the payload was computed from."
    payload: Mapped[bytes] = mapped_column(sa.LargeBinary, nullable=False)
    last_used: Mapped[datetime.datetime | None] = mapped_column(
        sa.DateTime, nullable=True
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "query_hash", "zoom", name="uq_filtered_cluster_cache_query_zoom"
        ),
    )


class ExplorerSquare(DB.Model):
    """Current biggest explorer square per zoom level."""

    __tablename__ = "explorer_square"

    zoom: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    square_x: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    square_y: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    max_square_size: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)


class SquareHistory(DB.Model):
    """Time series of the biggest explorer square, for the evolution plot."""

    __tablename__ = "square_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    time: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime, nullable=True)
    max_square_size: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    square_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    square_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)


class ClusterSizeHistory(DB.Model):
    """Time series of the biggest cluster size, for the evolution plot."""

    __tablename__ = "cluster_size_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False, index=True)
    time: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime, nullable=True)
    max_cluster_size: Mapped[int] = mapped_column(sa.Integer, nullable=False)


class ClusterMembership(DB.Model):
    """Materialized current cluster membership per tile.

    Holds, for every cluster tile at a zoom level, the representative tile of
    its cluster (``cluster_x``/``cluster_y``). This is the source of truth for
    the live explorer cluster coloring and counters, queried by viewport so no
    per-process in-memory state is needed.
    """

    __tablename__ = "cluster_membership"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cluster_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    cluster_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.Index("idx_cluster_membership_zoom_tile", "zoom", "tile_x", "tile_y"),
        sa.Index(
            "idx_cluster_membership_zoom_cluster", "zoom", "cluster_x", "cluster_y"
        ),
        sa.UniqueConstraint(
            "zoom", "tile_x", "tile_y", name="uq_cluster_membership_per_zoom"
        ),
    )


class InaccessibleTile(DB.Model):
    """A tile that the user has marked as inaccessible for a given zoom level."""

    __tablename__ = "inaccessible_tiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_x: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    tile_y: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    __table_args__ = (
        sa.UniqueConstraint(
            "zoom", "tile_x", "tile_y", name="uq_inaccessible_tile_per_zoom"
        ),
    )


class TileStyleName(StrEnum):
    """The tile roles that the rendering code can ask for."""

    VISITED = "visited"
    MISSING = "missing"
    NEW_TILE = "new_tile"
    NEW_TILE_NEW_CLUSTER = "new_tile_new_cluster"
    VISITED_NEW_CLUSTER = "visited_new_cluster"
    MAX_CLUSTER = "max_cluster"
    OTHER_CLUSTER = "other_cluster"
    OLD_CLUSTER = "old_cluster"
    INACCESSIBLE = "inaccessible"


class BorderStroke(StrEnum):
    SOLID = "solid"
    DASHED = "dashed"


TRANSPARENT = "#00000000"


class TileStyle(DB.Model):
    """How one named tile role is drawn: fill, nesting border, and stripes.

    Colors are ``#rrggbbaa`` strings; an alpha of zero switches the respective
    element off. The border width is given in pixels of a full-size tile and
    scaled down when several explorer tiles share one map tile.
    """

    __tablename__ = "tile_styles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String, nullable=False, unique=True)
    fill_color: Mapped[str] = mapped_column(
        sa.String, nullable=False, default=TRANSPARENT
    )
    border_color: Mapped[str] = mapped_column(
        sa.String, nullable=False, default=TRANSPARENT
    )
    border_width: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=6)
    border_stroke: Mapped[str] = mapped_column(
        sa.String, nullable=False, default=BorderStroke.SOLID
    )
    stripe_color: Mapped[str] = mapped_column(
        sa.String, nullable=False, default=TRANSPARENT
    )

    def __str__(self) -> str:
        return self.name


def _defaults(
    fill_color: str = TRANSPARENT,
    border_color: str = TRANSPARENT,
    border_width: int = 6,
    border_stroke: BorderStroke = BorderStroke.SOLID,
    stripe_color: str = TRANSPARENT,
) -> dict[str, str | int]:
    return {
        "fill_color": fill_color,
        "border_color": border_color,
        "border_width": border_width,
        "border_stroke": border_stroke,
        "stripe_color": stripe_color,
    }


TILE_STYLE_DEFAULTS: dict[TileStyleName, dict[str, str | int]] = {
    TileStyleName.VISITED: _defaults(fill_color="#5e5c6480"),
    TileStyleName.MISSING: _defaults(fill_color="#0000004d"),
    TileStyleName.NEW_TILE: _defaults(fill_color="#e01b2480", border_color="#ff770000"),
    TileStyleName.NEW_TILE_NEW_CLUSTER: _defaults(
        fill_color="#e01b2480", border_color="#0066ff00", stripe_color="#3584e480"
    ),
    TileStyleName.VISITED_NEW_CLUSTER: _defaults(
        fill_color="#3d384680", border_color="#0066ff00", stripe_color="#3584e480"
    ),
    TileStyleName.MAX_CLUSTER: _defaults(fill_color="#377eb84d"),
    TileStyleName.OTHER_CLUSTER: _defaults(fill_color="#4daf4a4d"),
    TileStyleName.OLD_CLUSTER: _defaults(fill_color="#3584e480"),
    TileStyleName.INACCESSIBLE: _defaults(stripe_color="#ed333b80"),
}


def get_tile_styles() -> dict[TileStyleName, TileStyle]:
    """All tile styles, creating rows with their defaults where missing."""
    rows = {row.name: row for row in DB.session.scalars(sa.select(TileStyle)).all()}
    missing = [name for name in TileStyleName if name not in rows]
    for name in missing:
        rows[name] = TileStyle(name=name, **TILE_STYLE_DEFAULTS[name])
        DB.session.add(rows[name])
    if missing:
        try:
            DB.session.commit()
        except sa.exc.IntegrityError:
            # A concurrent request may have inserted the same rows first.
            DB.session.rollback()
            rows = {
                row.name: row for row in DB.session.scalars(sa.select(TileStyle)).all()
            }
    return {name: rows[name] for name in TileStyleName}
