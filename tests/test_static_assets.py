import pathlib
import re

import pytest

from geo_activity_playground.webui import static_assets
from geo_activity_playground.webui.static_assets import (
    MissingFrontendAssetsError,
    assert_frontend_assets_present,
)


def test_installed_frontend_assets_are_present() -> None:
    assert_frontend_assets_present()


def test_startup_fails_without_frontend_assets(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    monkeypatch.setattr(static_assets, "STATIC_DIST_DIR", tmp_path)
    with pytest.raises(MissingFrontendAssetsError):
        assert_frontend_assets_present()


def test_templates_only_reference_required_assets() -> None:
    src = pathlib.Path(__file__).parent.parent / "src"
    referenced = {
        match
        for template in src.rglob("*.j2")
        for match in re.findall(
            r"/static/dist/([\w.-]+)", template.read_text(encoding="utf-8")
        )
    }
    assert referenced <= set(static_assets.REQUIRED_ASSETS)
