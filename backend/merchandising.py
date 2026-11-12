"""Catalog-driven homepage selections and suggestions."""


def build_home_merchandising(products):
    """Feature only published, priced catalog items; never invent product offers."""
    available = [p for p in products if p['stock'] > 0]
    highlighted = sorted(available, key=lambda p: (not p['featured'], p['id']))
    spotlight = highlighted[0] if highlighted else None
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
    return {'spotlight': spotlight, 'guides': guides, 'companions': companion[:3]}
