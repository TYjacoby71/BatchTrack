
def register_template_helpers(app):
    """Register template context processors and filters"""
    from ..models import Unit, IngredientCategory

    @app.template_filter('attr_multiply')
    def attr_multiply_filter(item, attr1, attr2):
        """Multiply two attributes of a single item"""
        if item is None:
            return 0
        val1 = getattr(item, attr1, 0)
        val2 = getattr(item, attr2, 0)
        if val1 is None:
            val1 = 0
        if val2 is None:
            val2 = 0
        return float(val1) * float(val2)

    @app.context_processor
    def inject_units():
        units = Unit.query.order_by(Unit.type, Unit.name).all()
        categories = IngredientCategory.query.order_by(IngredientCategory.name).all()
        return dict(units=units, categories=categories)

    @app.context_processor
    def inject_permissions():
        from ..utils.permissions import has_permission, has_role
        return dict(has_permission=has_permission, has_role=has_role)
