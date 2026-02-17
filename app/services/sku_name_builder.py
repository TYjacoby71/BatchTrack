class SKUNameBuilder:
    @staticmethod
    def render(template: str, context: dict) -> str:
        if not template:
            template = "{variant} {product} ({size_label})"

        # Normalize and allow extended placeholders
        def s(val):
            return (str(val) if val is not None else "").strip()

        values = {
            "product": s(context.get("product")),
            "variant": s(context.get("variant")),
            "container": s(context.get("container")),
            "size_label": s(context.get("size_label")),
            # Extended attributes from recipe/batch/container/portioning
            "yield_value": s(context.get("yield_value")),
            "yield_unit": s(context.get("yield_unit")),
            "portion_name": s(context.get("portion_name")),
            "portion_count": s(context.get("portion_count")),
            "portion_size_value": s(context.get("portion_size_value")),
            "portion_size_unit": s(context.get("portion_size_unit")),
        }
        out = template
        for key, val in values.items():
            out = out.replace("{%s}" % key, val)
        # Normalize whitespace and dangling parens
        out = " ".join(out.split())
        # Remove empty parentheticals
        if "()" in out:
            out = out.replace("()", "").strip()
        # Remove double spaces before/after parens
        out = out.replace("( ", "(").replace(" )", ")")
        return out.strip()
