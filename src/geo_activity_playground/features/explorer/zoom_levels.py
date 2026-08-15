from flask_babel import gettext
from flask_babel import lazy_gettext as _

SELECTABLE_EXPLORER_ZOOM_LEVELS = range(8, 20)

EXPLORER_ZOOM_LEVEL_NAMES = {
    14: _("Explorer Tiles"),
    17: _("Squadratinhos"),
}


def explorer_zoom_level_label(zoom: int) -> str:
    name = EXPLORER_ZOOM_LEVEL_NAMES.get(zoom)
    if name:
        return gettext("%(name)s (Zoom %(zoom)d)") % {"name": name, "zoom": zoom}
    return gettext("Zoom %(zoom)d") % {"zoom": zoom}
