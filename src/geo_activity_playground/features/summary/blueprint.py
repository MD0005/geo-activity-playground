import datetime

import altair as alt
import pandas as pd
import sqlalchemy
from flask import Blueprint, render_template
from flask_babel import gettext as _

from ...core.config import ConfigAccessor
from ...core.datamodel import DB, query_activity_meta
from ...core.meta_search import apply_search_filter
from ...features.plot_builder.analysis import make_parametric_plot
from ...features.plot_builder.model import PlotSpec
from ...webui.authenticator import Authenticator
from ...webui.columns import META_COLUMNS, ColumnDescription
from ...webui.search_context import search_context


def plot_per_year_per_kind(df: pd.DataFrame, column: ColumnDescription) -> str:
    return (
        alt.Chart(
            df,
            title=_("%(display_name)s per Year")
            % {"display_name": column.display_name},
        )
        .mark_bar()
        .encode(
            alt.X("year:O", title=_("Year")),
            alt.Y(
                f"sum({column.name})",
                title=f"{column.display_name} / {column.unit}",
            ),
            alt.Color("kind", title=_("Kind")),
            [
                alt.Tooltip("year", title=_("Year")),
                alt.Tooltip("kind", title=_("Kind")),
                alt.Tooltip(
                    f"sum({column.name})",
                    title=f"{column.display_name} / {column.unit}",
                ),
            ],
        )
        .interactive()
        .to_json(format="vega")
    )


def plot_year_cumulative(df: pd.DataFrame, column: ColumnDescription) -> str:
    year_cumulative = (
        df[["iso_year", "week", column.name]]
        .groupby("iso_year")
        .apply(
            lambda group: pd.DataFrame(
                {
                    "week": group["week"],
                    column.name: group[column.name].cumsum(),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )

    return (
        alt.Chart(
            year_cumulative,
            title=_("Cumulative %(display_name)s per Year")
            % {"display_name": column.display_name},
        )
        .mark_line()
        .encode(
            alt.X("week", title=_("Week")),
            alt.Y(column.name, title=f"{column.display_name} / {column.unit}"),
            alt.Color("iso_year:N", title=_("Year")),
            [
                alt.Tooltip("week", title=_("Week")),
                alt.Tooltip("iso_year:N", title=_("Year")),
                alt.Tooltip(
                    column.name,
                    title=f"{column.display_name} / {column.unit}",
                    format=column.format,
                ),
            ],
        )
        .interactive()
        .to_json(format="vega")
    )


def plot_per_iso_week(df: pd.DataFrame, column: ColumnDescription) -> str:
    return (
        alt.Chart(
            df,
            title=_("%(display_name)s per Week")
            % {"display_name": column.display_name},
        )
        .mark_circle()
        .encode(
            alt.X("week:O", title=_("ISO Week")),
            alt.Y("iso_year:O", title=_("ISO Year")),
            alt.Size(
                f"sum({column.name})", title=f"{column.display_name} / {column.unit}"
            ),
            [
                alt.Tooltip("iso_year", title=_("ISO Year")),
                alt.Tooltip("week", title=_("ISO Week")),
                alt.Tooltip(
                    f"sum({column.name})",
                    title=f"{column.display_name} / {column.unit}",
                    format=column.format,
                ),
            ],
        )
        .interactive()
        .to_json(format="vega")
    )


def heatmap_per_day(df: pd.DataFrame, column: ColumnDescription) -> str:
    return (
        alt.Chart(
            _filter_past_year(df),
            title=_("%(display_name)s per day") % {"display_name": column.display_name},
        )
        .mark_rect()
        .encode(
            alt.X("iso_year_week:O", title=_("ISO Year and Week")),
            alt.Y(
                "iso_day:O",
                # scale=alt.Scale(
                #     domain=list(range(1, 8)),
                #     range=[
                #         "Monday",
                #         "Tuesday",
                #         "Wednesday",
                #         "Thursday",
                #         "Friday",
                #         "Saturday",
                #         "Sunday",
                #     ],
                # ),
                title=_("ISO Weekday"),
            ),
            alt.Color(
                f"sum({column.name})",
                scale=alt.Scale(scheme="viridis"),
                title=f"{column.display_name} / {column.unit}",
            ),
            [
                alt.Tooltip("iso_year_week", title=_("ISO Year and Week")),
                alt.Tooltip("iso_day", title=_("ISO Day")),
                alt.Tooltip(
                    f"sum({column.name})",
                    title=f"{column.display_name} / {column.unit}",
                    format=column.format,
                ),
            ],
        )
        .interactive()
        .to_json(format="vega")
    )


def _filter_past_year(df: pd.DataFrame) -> pd.DataFrame:
    now = datetime.datetime.combine(datetime.date.today(), datetime.time.min)
    start = now - datetime.timedelta(days=365)
    return df.loc[df["start_local"] >= start]


def make_summary_blueprint(
    config_accessor: ConfigAccessor,
    authenticator: Authenticator,
) -> Blueprint:
    blueprint = Blueprint("summary", __name__, template_folder="templates")

    @blueprint.route("/")
    def index():
        primitives, search_vars = search_context(authenticator)

        df = apply_search_filter(primitives)

        df_without_nan = df.loc[~pd.isna(df["start_local"])]

        return render_template(
            "summary/index.html.j2",
            **search_vars,
            custom_plots=[
                (spec, make_parametric_plot(query_activity_meta(), spec))
                for spec in DB.session.scalars(sqlalchemy.select(PlotSpec)).all()
            ],
            plot_per_year_per_kind={
                column.display_name: plot_per_year_per_kind(df_without_nan, column)
                for column in META_COLUMNS
            },
            plot_per_year_cumulative={
                column.display_name: plot_year_cumulative(df_without_nan, column)
                for column in META_COLUMNS
            },
            plot_per_iso_week={
                column.display_name: plot_per_iso_week(df_without_nan, column)
                for column in META_COLUMNS
            },
            heatmap_per_day={
                column.display_name: heatmap_per_day(df_without_nan, column)
                for column in META_COLUMNS
            },
        )

    return blueprint
