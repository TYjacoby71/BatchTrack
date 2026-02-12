from app.routes.tools_routes import _normalize_soap_bulk_sort_key, _page_soap_bulk_catalog


def _sample_records():
    return [
        {
            "name": "Olive Oil",
            "aliases": ["Olea Europaea"],
            "ingredient_category_name": "Oils (Carrier & Fixed)",
            "fatty_profile": {"oleic": 72.0, "lauric": 0.0},
        },
        {
            "name": "Coconut Oil",
            "aliases": ["Cocos Nucifera"],
            "ingredient_category_name": "Oils (Carrier & Fixed)",
            "fatty_profile": {"oleic": 8.0, "lauric": 45.0},
        },
        {
            "name": "Palm Oil",
            "aliases": [],
            "ingredient_category_name": "Butters & Solid Fats",
            "fatty_profile": {"oleic": 39.0, "lauric": 0.2},
        },
    ]


def test_normalize_soap_bulk_sort_key_defaults_for_invalid_values():
    assert _normalize_soap_bulk_sort_key("name") == "name"
    assert _normalize_soap_bulk_sort_key("lauric") == "lauric"
    assert _normalize_soap_bulk_sort_key("unknown-field") == "name"
    assert _normalize_soap_bulk_sort_key(None) == "name"


def test_page_soap_bulk_catalog_applies_query_terms_and_total_count():
    page_rows, total_count = _page_soap_bulk_catalog(
        records=_sample_records(),
        query="olive carrier",
        sort_key="name",
        sort_dir="asc",
        offset=0,
        limit=25,
    )

    assert total_count == 1
    assert len(page_rows) == 1
    assert page_rows[0]["name"] == "Olive Oil"


def test_page_soap_bulk_catalog_sorts_and_clamps_page_limit():
    page_rows, total_count = _page_soap_bulk_catalog(
        records=_sample_records(),
        query="",
        sort_key="lauric",
        sort_dir="desc",
        offset=0,
        limit=999,  # Should clamp to backend page max.
    )

    assert total_count == 3
    assert len(page_rows) == 3
    assert page_rows[0]["name"] == "Coconut Oil"
