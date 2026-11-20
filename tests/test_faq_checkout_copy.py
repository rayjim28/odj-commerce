"""FAQ guidance follows storefront availability and guest-checkout settings."""
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader, select_autoescape

from backend.merchandising import build_home_merchandising

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "frontend/templates"),
                        autoescape=select_autoescape(["html"]))


def faq(preview=False, checkout=True, guest=False):
    html = TEMPLATES.get_template("index.html").render(
        products=[], categories=[], settings={"announcement": ""},
        merch=build_home_merchandising([]), bundles=[], canonical_url="",
        public_preview=preview, checkout_open=checkout, account_testing=False,
        customer=None, customer_json={"signedIn": False}, guest_checkout_enabled=guest,
    )
    return html.split('<section class="v71-faq"', 1)[1].split("</section>", 1)[0]


@pytest.mark.parametrize("preview,checkout,guest,account_answer,shipping_answer", [
    (True, True, True, "Online ordering is not available during the preview.",
     "Online ordering is currently unavailable."),
    (False, False, True, "Online ordering is currently unavailable.",
     "Online ordering is currently unavailable."),
    (False, True, True, "No. You can check out as a guest.", "before you pay"),
    (False, True, False, "Sign in or create an account before placing an order.",
     "before you pay"),
])
def test_checkout_answers_match_storefront_mode(preview, checkout, guest,
                                               account_answer, shipping_answer):
    html = faq(preview, checkout, guest)
    account = html.split("</summary>", 1)[1].split("</details>", 1)[0]
    shipping = html.split("Where do I see shipping costs?", 1)[1].split("</details>", 1)[0]
    assert account_answer in account
    assert shipping_answer in shipping
    if preview or not checkout:
        assert "You can check out as a guest" not in account
        assert "before you pay" not in shipping
    assert "when the store opens" not in html


def test_all_answers_use_native_disclosures_and_render_without_javascript():
    html = faq()
    assert html.count("<details>") == 4
    assert html.count("<summary>") == 4
    assert html.count('class="tm-faq-toggle" aria-hidden="true"') == 4
    assert "Check the product description and specifications for compatibility." in html
    assert 'aria-labelledby="v71-faq-heading"' in html
    assert '<script' not in html


@pytest.mark.parametrize("preview,checkout", [(False, True), (False, False), (True, False)])
def test_contact_and_policy_links_remain_available_in_every_mode(preview, checkout):
    html = faq(preview=preview, checkout=checkout)
    assert 'href="/information/contact"' in html
    assert 'href="/information/shipping"' in html
    assert 'href="/information/returns"' in html
