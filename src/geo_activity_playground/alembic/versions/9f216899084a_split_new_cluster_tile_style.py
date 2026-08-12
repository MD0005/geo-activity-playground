from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9f216899084a"
down_revision: str | None = "0ca5ca87a12f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _rename_tile_style("new_cluster", "visited_new_cluster")


def downgrade() -> None:
    _rename_tile_style("visited_new_cluster", "new_cluster")


def _rename_tile_style(old_name: str, new_name: str) -> None:
    """Point an existing row at its new name, keeping any user customization.

    The activity highlight layer used to compose ``new_cluster`` on top of
    another style; it is now one of five standalone styles, so the row that
    carried the old customization becomes ``visited_new_cluster``. Skipped if
    the target name already has a row, so this only ever runs once.
    """
    connection = op.get_bind()
    exists = connection.execute(
        sa.text("select 1 from tile_styles where name = :name"), {"name": new_name}
    ).first()
    if exists:
        return
    connection.execute(
        sa.text("update tile_styles set name = :new_name where name = :old_name"),
        {"new_name": new_name, "old_name": old_name},
    )


# ### end Alembic commands ###
