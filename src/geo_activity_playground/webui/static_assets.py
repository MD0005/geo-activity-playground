"""Guard against a missing Vite bundle.

The JS/CSS bundle under `static/dist` is built by the Hatchling build hook
(`npm ci && npm run webui:build`) and deliberately not committed to git. When
it is absent, every page still renders but without styling or interactivity,
which is hard to diagnose from the browser. Therefore the application refuses
to start instead.
"""

import pathlib

STATIC_DIST_DIR = pathlib.Path(__file__).parent / "static" / "dist"

REQUIRED_ASSETS = [
    "activity-trim.js",
    "app.css",
    "app.js",
    "map-layers.js",
    "server-side-explorer.js",
]


class MissingFrontendAssetsError(RuntimeError):
    pass


def assert_frontend_assets_present() -> None:
    missing = [
        name for name in REQUIRED_ASSETS if not (STATIC_DIST_DIR / name).is_file()
    ]
    if not missing:
        return
    raise MissingFrontendAssetsError(
        f"The frontend assets {', '.join(missing)} are missing from "
        f"{STATIC_DIST_DIR}. They are built with npm during installation and are "
        "not part of the Git checkout. Install Node.js/npm, then re-install this "
        "package with `uv sync --reinstall-package geo-activity-playground` and "
        "start the server with `uv run geo-activity-playground serve`. See "
        "https://martin-ueding.github.io/geo-activity-playground/set-up-a-development-environment"
    )
