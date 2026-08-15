from flask import request

from ..core.meta_search import (
    get_stored_queries,
    parse_search_params,
    primitives_to_jinja,
    primitives_to_url_str,
    register_search_query,
)
from .authenticator import Authenticator


def search_context(authenticator: Authenticator) -> tuple[dict, dict]:
    """Parse the filter from the request, record it, and build the template variables.

    Returns the search primitives and the variables that ``search_form.html.j2``
    needs; the latter are meant to be splatted into ``render_template``.
    """
    primitives = parse_search_params(request.args)

    if authenticator.is_authenticated():
        register_search_query(primitives)

    stored_queries = get_stored_queries()

    return primitives, {
        "query": primitives_to_jinja(primitives),
        "base_query_str": primitives_to_url_str(primitives),
        "search_query_favorites": [
            (str(q), q.to_url_str()) for q in stored_queries if q.is_favorite
        ],
        "search_query_last": [
            (str(q), q.to_url_str()) for q in stored_queries if not q.is_favorite
        ],
    }
