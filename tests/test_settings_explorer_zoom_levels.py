from flask import Flask

from geo_activity_playground.core.config import ConfigAccessor
from geo_activity_playground.core.datamodel import DB
from geo_activity_playground.features.explorer.model import ExplorerSquare


def test_default_zoom_levels_are_checked(client) -> None:
    response = client.get("/settings/explorer-zoom-levels")
    assert response.status_code == 200
    assert b'value="14" checked' in response.data
    assert b'value="17" checked' in response.data
    assert b'value="15" checked' not in response.data


def test_selection_is_persisted_and_evolution_updated(seeded_app: Flask) -> None:
    client = seeded_app.test_client()
    response = client.post(
        "/settings/explorer-zoom-levels", data={"zoom": ["14", "15"]}
    )
    assert response.status_code == 200

    with seeded_app.app_context():
        assert ConfigAccessor().ui().explorer_zoom_levels == [14, 15]
        squares = DB.session.query(ExplorerSquare)
        assert squares.filter(ExplorerSquare.zoom == 15).count() == 1
        assert squares.filter(ExplorerSquare.zoom == 17).count() == 0

    navigation = client.get("/").data.decode()
    assert "/explorer/15/server-side" in navigation
    assert "/square-planner/15" in navigation
    assert "/explorer/17/server-side" not in navigation


def test_empty_selection_is_rejected(app: Flask) -> None:
    client = app.test_client()
    response = client.post("/settings/explorer-zoom-levels", data={})
    assert response.status_code == 200
    with app.app_context():
        assert ConfigAccessor().ui().explorer_zoom_levels == [14, 17]
