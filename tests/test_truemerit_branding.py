"""Brand assets stay separate from business logic and keep their public paths."""
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "frontend" / "templates"
ASSETS = ROOT / "frontend" / "static"


def test_brand_assets_are_valid_svg():
    for name in ("truemerit-cleaning-logo.svg", "favicon.svg", "odj-bundle-placeholder.svg"):
        path = ASSETS / "images" / name
        assert path.is_file()
        doc = ElementTree.parse(path)
        assert doc.getroot().tag.endswith("svg")
    assert "TrueMerit Cleaning Supplies" in (ASSETS / "images" / "truemerit-cleaning-logo.svg").read_text()


def test_original_page_structure_has_brand_layer():
    required = ("index.html", "product.html", "account.html", "admin.html", "checkout.html",
                "success.html", "order_detail.html", "store_info.html", "reset_password.html", "demo_order.html")
    for name in required:
        page = (TEMPLATES / name).read_text()
        assert 'href="/static/truemerit-theme.css?v=1"' in page
        assert "TrueMerit" in page
        assert "/static/images/truemerit-cleaning-logo.svg" in page
    home = (TEMPLATES / "index.html").read_text()
    for landmark in ("id=\"shop\"", 'class="hero"', 'class="main-nav"', 'class="footer"'):
        assert landmark in home


def test_existing_technical_names_are_stable():
    import main
    from backend.security import COOKIE_NAME
    assert COOKIE_NAME == "odj_admin"
    assert str(main.app.url_path_for("home")) == "/"
    css = (ASSETS / "truemerit-theme.css").read_text()
    assert "--tm-navy:" in css and "--tm-orange:" in css
