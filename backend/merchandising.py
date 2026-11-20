"""Catalog-driven homepage selections and suggestions."""
import re


def build_home_merchandising(products):
    """Feature only published, priced catalog items; never invent product offers."""
    available = [p for p in products if p['stock'] > 0]
    highlighted = sorted(available, key=lambda p: (not p['featured'], p['id']))
    spotlight = highlighted[0] if highlighted else None

    # Only the owner's featured, available listings qualify for these groups.
    promoted = [p for p in products if p.get('featured') is True
                and p.get('active', True) and p.get('stock', 0) > 0
                and p.get('price_cents', 0) > 0]
    featured_picks = {
        key: [p for p in promoted if re.search(pattern, str(p.get('badge') or ''), re.I)]
        for key, pattern in (
            ('best', r'\bBEST\s*SELLERS?\b'),
            ('new', r'\bNEW\b'),
        )
    }

    # Show the first five eligible products already in storefront order.
    # Uploaded products appear automatically after the owner publishes them;
    # no separate Featured checkbox is required. Never promote drafts,
    # out-of-stock products, bundles, or entries lacking a real product photo.
    def valid_hero_photo(url):
        url = (url or '').strip()
        # Supplier photos should be real images, not our built-in SVG
        # sample illustrations or the generic missing-photo placeholders.
        return bool(url) and not url.lower().split('?', 1)[0].endswith('.svg') and not any(
            token in url.lower() for token in
            ('default.svg', 'placeholder.svg', 'odj-bundle-placeholder.svg')
        )

    hero_products = [
        p for p in available
        if p.get('active', True)
        and not p.get('is_bundle', False)
        and p['id'] > 0
        and p.get('price_cents', 0) > 0
        and valid_hero_photo(p.get('image_url'))
    ][:5]
    themes = (
        ('Mop systems', 'Start with the essentials for your floors.', ('mop', 'bucket', 'spin'), ('head', 'refill', 'replacement', 'handle')),
        ('Parts & refills', 'Keep the right replacement items close by.', ('head', 'refill', 'replacement', 'handle'), ()),
        ('Cleaning extras', 'The finishing touches for everyday upkeep.', ('cloth', 'brush', 'scrub', 'microfiber', 'wipes', 'cleaner'), ()),
    )
    guides = []
    for title, subtitle, terms, excluded in themes:
        matches = [p for p in products if any(w in (p['name'] + ' ' + p['category']).lower() for w in terms)
                   and not any(w in p['name'].lower() for w in excluded)]
        if matches:
            guides.append({'title': title, 'subtitle': subtitle,
                           'image_url': matches[0]['image_url'] or '/static/images/default.svg',
                           'ids': [p['id'] for p in matches], 'count': len(matches)})
    # Cross-sell adjacent catalog products as suggestions, not a promised compatible kit
    # or a discount. Restrict to listed, currently in-stock items.
    companion = [p for p in highlighted if spotlight and p['id'] != spotlight['id']]
    return {'spotlight': spotlight, 'guides': guides, 'companions': companion[:3],
            'hero_products': hero_products, 'featured_picks': featured_picks}
