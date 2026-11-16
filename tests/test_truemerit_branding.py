"""Brand assets stay separate from business logic and keep their public paths."""
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "frontend" / "templates"
ASSETS = ROOT / "frontend" / "static"


def test_brand_assets_are_valid_svg():
    for name in ("favicon.svg", "odj-bundle-placeholder.svg"):
        path = ASSETS / "images" / name
        assert path.is_file()
        doc = ElementTree.parse(path)
        assert doc.getroot().tag.endswith("svg")
    logo = ASSETS / "images" / "truemerit-logo.svg"
    assert logo.is_file()
    root = ElementTree.parse(logo).getroot()
    assert root.tag.endswith("svg")
    assert root.attrib.get("viewBox") == "0 0 610 225"


def test_original_page_structure_has_brand_layer():
    required = ("index.html", "product.html", "account.html", "admin.html", "checkout.html",
                "success.html", "order_detail.html", "store_info.html", "reset_password.html", "demo_order.html")
    for name in required:
        page = (TEMPLATES / name).read_text()
        assert 'href="/static/truemerit-theme.css?v=8"' in page
        assert "TrueMerit" in page
        assert "/static/images/truemerit-logo.svg" in page
    home = (TEMPLATES / "index.html").read_text()
    for landmark in ("id=\"shop\"", 'class="hero"', 'class="main-nav"', 'class="footer"'):
        assert landmark in home
    assert 'class="hero-art hero-abstract-art"' in home
    assert 'class="hero-abstract-layer hero-abstract-layer-front"' in home
    assert 'class="editorial-image editorial-promise-panel"' in home
    assert 'class="hero-logo"' not in home
    assert 'class="hero-product-image"' not in home



def test_homepage_has_clean_compact_abstract_hero_and_centered_about():
    home = (TEMPLATES / "index.html").read_text()
    css = (ASSETS / "truemerit-theme.css").read_text()
    hero = home.split('<section class="hero">', 1)[1].split('</section>', 1)[0]
    assert 'RETAIL &amp; WHOLESALE CLEANING SUPPLIES' in hero
    for removed in ('/ 001', 'MOP SYSTEMS', 'REFILLS &amp; ACCESSORIES',
                    '01 — 03', 'SCROLL TO EXPLORE', 'hero-product-image',
                    'THE TRUEMERIT COLLECTION'):
        assert removed not in hero
    assert 'hero-abstract-layer-front' in hero
    assert 'CLEANING SUPPLIES FROM INDEPENDENT BRANDS' in home
    assert 'flex-direction:column' in css
    assert 'text-align:center' in css
    assert '.hero-inner' in css and 'min-height:460px' in css


def test_existing_technical_names_are_stable():
    import main
    from backend.security import COOKIE_NAME
    assert COOKIE_NAME == "odj_admin"
    assert str(main.app.url_path_for("home")) == "/"
    css = (ASSETS / "truemerit-theme.css").read_text()
    assert "--tm-navy:" in css and "--tm-orange:" in css


def test_approved_storefront_header_and_legacy_announcement_guard():
    home = (TEMPLATES / "index.html").read_text()
    css = (ASSETS / "truemerit-theme.css").read_text()
    assert 'Welcome to ODJ Cleaning Essentials' in home
    assert "settings.announcement|trim not in" in home
    assert ".header-search{display:none" in css
    assert ".header-search.open{display:block" in css
    assert ".nav-actions .search-trigger{display:flex" in css
    admin = (TEMPLATES / "admin.html").read_text()
    assert 'class="admin-welcome"' in admin
    assert 'truemerit-logo.svg' in admin
