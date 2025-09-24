class SKUNameBuilder:
    @staticmethod
    def render(template: str, context: dict) -> str:
        if not template:
            template = '{variant} {product} ({size_label})'
        values = {
            'product': (context.get('product') or '').strip(),
            'variant': (context.get('variant') or '').strip(),
            'container': (context.get('container') or '').strip() if context.get('container') else '',
            'size_label': (context.get('size_label') or '').strip() if context.get('size_label') else '',
        }
        out = template
        for key, val in values.items():
            out = out.replace('{%s}' % key, val)
        # Normalize whitespace and dangling parens
        out = ' '.join(out.split())
        # Remove empty parentheticals
        if '()' in out:
            out = out.replace('()', '').strip()
        # Remove double spaces before/after parens
        out = out.replace('( ', '(').replace(' )', ')')
        return out.strip()

