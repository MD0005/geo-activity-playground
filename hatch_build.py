"""Hatchling build hook: compile translations and build the webui JS bundle.

Neither the `.mo` translation files nor the Vite-built JS/CSS bundle are
committed to git; both are generated here so that every build (`uv sync` for
development, `uv build` for a release) produces them fresh from the pinned
dependency versions in `uv.lock` and `package-lock.json`.
"""

import shutil
import subprocess
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

REPO_ROOT = Path(__file__).parent
TRANSLATIONS_DIR = REPO_ROOT / "src/geo_activity_playground/webui/translations"
STATIC_DIST_DIR = REPO_ROOT / "src/geo_activity_playground/webui/static/dist"


class WebuiAssetsBuildHook(BuildHookInterface):
    PLUGIN_NAME = "webui-assets"

    def initialize(self, _version: str, build_data: dict) -> None:
        self._compile_translations()
        self._build_js_bundle()

        for mo_file in TRANSLATIONS_DIR.glob("*/LC_MESSAGES/messages.mo"):
            relative = mo_file.relative_to(REPO_ROOT / "src")
            build_data["force_include"][str(mo_file)] = str(relative)

        if STATIC_DIST_DIR.is_dir():
            for asset in STATIC_DIST_DIR.rglob("*"):
                if asset.is_file():
                    relative = asset.relative_to(REPO_ROOT / "src")
                    build_data["force_include"][str(asset)] = str(relative)

    def _compile_translations(self) -> None:
        from babel.messages.mofile import write_mo
        from babel.messages.pofile import read_po

        for po_file in TRANSLATIONS_DIR.glob("*/LC_MESSAGES/messages.po"):
            with po_file.open("rb") as f:
                catalog = read_po(f)
            mo_file = po_file.with_suffix(".mo")
            with mo_file.open("wb") as f:
                write_mo(f, catalog)

    def _build_js_bundle(self) -> None:
        if STATIC_DIST_DIR.is_dir():
            shutil.rmtree(STATIC_DIST_DIR)

        npm = shutil.which("npm")
        if npm is None:
            raise RuntimeError(
                "npm is required to build the webui JS bundle "
                f"(expected output at {STATIC_DIST_DIR}) but was not found "
                "on PATH. Install Node.js, or see "
                "docs/set-up-a-development-environment.md."
            )

        subprocess.run([npm, "ci"], cwd=REPO_ROOT, check=True)
        subprocess.run([npm, "run", "webui:build"], cwd=REPO_ROOT, check=True)
