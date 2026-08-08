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


class ClusterHistoryCheckpoint(DB.Model):
    __tablename__ = "cluster_history_checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True)
    zoom: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    event_index: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    time: Mapped[datetime.datetime | None] = mapped_column(sa.DateTime, nullable=True)
    max_cluster_size: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    payload_json: Mapped[str] = mapped_column(sa.Text, nullable=False, default="{}")

    __table_args__ = (
        sa.Index("idx_cluster_history_checkpoints_zoom_index", "zoom", "event_index"),
        sa.UniqueConstraint(
            "zoom", "event_index", name="uq_cluster_history_checkpoints"
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
    NEW_CLUSTER = "new_cluster"
    MAX_CLUSTER = "max_cluster"
    OTHER_CLUSTER = "other_cluster"
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
    TileStyleName.VISITED: _defaults(fill_color="#0000004d"),
    TileStyleName.MISSING: _defaults(fill_color="#0000004d"),
    TileStyleName.NEW_TILE: _defaults(border_color="#ff7700ff"),
    TileStyleName.NEW_CLUSTER: _defaults(border_color="#0066ffff"),
    TileStyleName.MAX_CLUSTER: _defaults(fill_color="#377eb84d"),
    TileStyleName.OTHER_CLUSTER: _defaults(fill_color="#4daf4a4d"),
    TileStyleName.INACCESSIBLE: _defaults(stripe_color="#80808099"),
}


def get_tile_styles() -> dict[TileStyleName, TileStyle]:
    """All tile styles, creating rows with their defaults where missing."""
    rows = {row.name: row for row in DB.session.scalars(sa.select(TileStyle)).all()}
    missing = [name for name in TileStyleName if name not in rows]
    for name in missing:
        rows[name] = TileStyle(name=name, **TILE_STYLE_DEFAULTS[name])
        DB.session.add(rows[name])
    if missing:
        DB.session.commit()
    return {name: rows[name] for name in TileStyleName}
