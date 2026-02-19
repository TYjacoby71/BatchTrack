from flask import Blueprint

# Create the blueprint with explicit template folder
recipes_bp = Blueprint(
    "recipes",
    __name__,
    template_folder="templates",
    static_folder="static",
    url_prefix="/recipes",
)


# Import routes after blueprint creation to avoid circular imports
def register_routes():
    from .views import ajax_routes  # noqa: F401
    from .views import create_routes  # noqa: F401
    from .views import lineage_routes  # noqa: F401
    from .views import manage_routes  # noqa: F401


# Register routes when blueprint is created
register_routes()
