from pathlib import Path

from app.template_context import static_asset_url


def _write_asset(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_static_asset_prefers_minified_variant(app):
    static_root = Path(app.static_folder)
    source_path = static_root / "tests" / "assets" / "seo_helper_demo.js"
    minified_path = static_root / "tests" / "assets" / "seo_helper_demo.min.js"

    try:
        _write_asset(source_path, "function add(a, b) {\n  return a + b;\n}\n")
        _write_asset(minified_path, "function add(a,b){return a+b;}\n")

        with app.test_request_context("/"):
            resolved = static_asset_url("tests/assets/seo_helper_demo.js")

        assert "/static/tests/assets/seo_helper_demo.min.js" in resolved
        assert "v=" in resolved
    finally:
        if source_path.exists():
            source_path.unlink()
        if minified_path.exists():
            minified_path.unlink()


def test_static_asset_falls_back_to_source_when_minified_missing(app):
    static_root = Path(app.static_folder)
    source_path = static_root / "tests" / "assets" / "seo_helper_fallback.css"
    minified_path = static_root / "tests" / "assets" / "seo_helper_fallback.min.css"

    try:
        _write_asset(source_path, "body {\n  color: #111;\n}\n")
        if minified_path.exists():
            minified_path.unlink()

        with app.test_request_context("/"):
            resolved = static_asset_url("tests/assets/seo_helper_fallback.css")

        assert "/static/tests/assets/seo_helper_fallback.css" in resolved
        assert ".min.css" not in resolved
    finally:
        if source_path.exists():
            source_path.unlink()
        if minified_path.exists():
            minified_path.unlink()


def test_static_asset_does_not_rewrite_non_css_or_js_files(app):
    static_root = Path(app.static_folder)
    source_path = static_root / "tests" / "assets" / "seo_helper_logo.svg"

    try:
        _write_asset(source_path, "<svg xmlns='http://www.w3.org/2000/svg'></svg>\n")

        with app.test_request_context("/"):
            resolved = static_asset_url("tests/assets/seo_helper_logo.svg")

        assert "/static/tests/assets/seo_helper_logo.svg" in resolved
        assert ".min.svg" not in resolved
    finally:
        if source_path.exists():
            source_path.unlink()
