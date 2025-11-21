import logging

from flask import current_app

from app.extensions import db

logger = logging.getLogger(__name__)

def register_blueprints(app):
    """Register all blueprints with the Flask app."""

    # Track successful registrations
    successful_registrations = []
    failed_registrations = []

    def safe_register_blueprint(import_path, blueprint_name, url_prefix=None, description=None):
        """Safely register a blueprint with error handling"""
        try:
            module_path, bp_name = import_path.rsplit('.', 1)
            module = __import__(module_path, fromlist=[bp_name])
            blueprint = getattr(module, bp_name)

            if url_prefix:
                app.register_blueprint(blueprint, url_prefix=url_prefix)
            else:
                app.register_blueprint(blueprint)

            successful_registrations.append(description or blueprint_name)
            return True
        except Exception as e:
            failed_registrations.append(f"{description or blueprint_name}: {e}")
            return False

    # Core blueprints - these should always work
    safe_register_blueprint('app.blueprints.auth.auth_bp', 'auth_bp', '/auth', 'Authentication')
    safe_register_blueprint('app.blueprints.admin.admin_bp', 'admin_bp', '/admin', 'Admin')
    safe_register_blueprint('app.blueprints.developer.developer_bp', 'developer_bp', '/developer', 'Developer')
    safe_register_blueprint('app.blueprints.inventory.inventory_bp', 'inventory_bp', '/inventory', 'Inventory')
    safe_register_blueprint('app.blueprints.recipes.recipes_bp', 'recipes_bp', '/recipes', 'Recipes')
    safe_register_blueprint('app.blueprints.batches.batches_bp', 'batches_bp', '/batches', 'Batches')
    safe_register_blueprint('app.blueprints.organization.routes.organization_bp', 'organization_bp', '/organization', 'Organization')
    safe_register_blueprint('app.blueprints.billing.billing_bp', 'billing_bp', '/billing', 'Billing')
    safe_register_blueprint('app.blueprints.onboarding.routes.onboarding_bp', 'onboarding_bp', '/onboarding', 'Onboarding')
    safe_register_blueprint('app.blueprints.settings.settings_bp', 'settings_bp', '/settings', 'Settings')
    safe_register_blueprint('app.blueprints.timers.timers_bp', 'timers_bp', '/timers', 'Timers')
    safe_register_blueprint('app.blueprints.expiration.expiration_bp', 'expiration_bp', '/expiration', 'Expiration')
    safe_register_blueprint('app.blueprints.conversion.conversion_bp', 'conversion_bp', '/conversion', 'Conversion')

    # Product blueprints - use the register function
    try:
        from app.blueprints.products import register_product_blueprints
        register_product_blueprints(app)
        successful_registrations.append("Products Main")
    except Exception as e:
        failed_registrations.append(f"Products Main: {e}")
        # Fallback - try to register just the main products blueprint
        try:
            from app.blueprints.products.products import products_bp
            app.register_blueprint(products_bp)
            successful_registrations.append("Products Fallback")
        except Exception as e2:
            failed_registrations.append(f"Products Fallback: {e2}")

    # Product blueprints are now registered via register_product_blueprints() above
    # Remove individual registrations to avoid conflicts

    # API blueprints - these are often problematic
    safe_register_blueprint('app.blueprints.api.public.public_api_bp', 'public_api_bp', '/api/public', 'Public API')
    safe_register_blueprint('app.blueprints.api.routes.api_bp', 'api_bp', '/api', 'Main API')
    safe_register_blueprint('app.blueprints.api.drawers.drawers_bp', 'drawers_bp', None, 'Drawer API')
    from app.blueprints.api.dashboard_routes import dashboard_api_bp
    app.register_blueprint(dashboard_api_bp)

    # Note: FIFO blueprint removed - functionality moved to inventory_adjustment service

    # Register standalone route modules
    route_modules = [
        ('app.routes.app_routes.app_routes_bp', 'app_routes_bp', None, 'App Routes'),
        ('app.routes.legal_routes.legal_bp', 'legal_bp', '/legal', 'Legal Routes'),
        ('app.routes.bulk_stock_routes.bulk_stock_bp', 'bulk_stock_bp', '/bulk-stock', 'Bulk Stock'),
        ('app.routes.fault_log_routes.faults_bp', 'faults_bp', '/faults', 'Fault Log'),
        ('app.routes.tag_manager_routes.tag_manager_bp', 'tag_manager_bp', '/tag-manager', 'Tag Manager'),
        ('app.routes.global_library_routes.global_library_bp', 'global_library_bp', None, 'Global Library Public'),
        ('app.routes.waitlist_routes.waitlist_bp', 'waitlist_bp', None, 'Waitlist'),
          ('app.routes.help_routes.help_bp', 'help_bp', None, 'Help & Instructions'),
        # Public tools mounted at /tools
        ('app.routes.tools_routes.tools_bp', 'tools_bp', '/tools', 'Public Tools')
    ]

    for import_path, bp_name, url_prefix, description in route_modules:
        safe_register_blueprint(import_path, bp_name, url_prefix, description)

    # Register production planning blueprint
    safe_register_blueprint('app.blueprints.production_planning.production_planning_bp', 'production_planning_bp', '/production-planning', 'Production Planning')

    # Exports blueprint (category-specific exports)
    try:
        from flask import Blueprint
        from flask_login import login_required, current_user
        # Create a lightweight exports blueprint inline to avoid import churn
        from app.models import Recipe
        exports_bp = Blueprint('exports', __name__, url_prefix='/exports')

        @exports_bp.route('/recipe/<int:recipe_id>/soap-inci')
        @login_required
        def soap_inci_recipe(recipe_id: int):
            from flask import render_template, abort
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            # Organization scoping
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            return render_template('exports/soap_inci.html', recipe=rec, source='recipe')

        @exports_bp.route('/recipe/<int:recipe_id>/candle-label')
        @login_required
        def candle_label_recipe(recipe_id: int):
            from flask import render_template, abort
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            return render_template('exports/candle_label.html', recipe=rec, source='recipe')

        @exports_bp.route('/recipe/<int:recipe_id>/baker-sheet')
        @login_required
        def baker_sheet_recipe(recipe_id: int):
            from flask import render_template, abort
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            return render_template('exports/baker_sheet.html', recipe=rec, source='recipe')

        @exports_bp.route('/recipe/<int:recipe_id>/lotion-inci')
        @login_required
        def lotion_inci_recipe(recipe_id: int):
            from flask import render_template, abort
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            return render_template('exports/lotion_inci.html', recipe=rec, source='recipe')

        @exports_bp.route('/tool/soaps/inci')
        def soap_inci_tool():
            from flask import render_template, session
            draft = session.get('tool_draft') or {}
            return render_template('exports/soap_inci.html', tool_draft=draft, source='tool')

        @exports_bp.route('/tool/candles/label')
        def candle_label_tool():
            from flask import render_template, session
            draft = session.get('tool_draft') or {}
            return render_template('exports/candle_label.html', tool_draft=draft, source='tool')

        @exports_bp.route('/tool/baker/sheet')
        def baker_sheet_tool():
            from flask import render_template, session
            draft = session.get('tool_draft') or {}
            return render_template('exports/baker_sheet.html', tool_draft=draft, source='tool')

        @exports_bp.route('/tool/lotions/inci')
        def lotion_inci_tool():
            from flask import render_template, session
            draft = session.get('tool_draft') or {}
            return render_template('exports/lotion_inci.html', tool_draft=draft, source='tool')

        # CSV/PDF export routes (recipe-scoped; require login)
        @exports_bp.route('/recipe/<int:recipe_id>/soap-inci.csv')
        @login_required
        def soap_inci_recipe_csv(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            # Delegate to export service
            from app.services.exports import ExportService
            csv_text = ExportService.soap_inci_csv(recipe=rec)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/recipe/<int:recipe_id>/soap-inci.pdf')
        @login_required
        def soap_inci_recipe_pdf(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            pdf_bytes = ExportService.soap_inci_pdf(recipe=rec)
            return Response(pdf_bytes, mimetype='application/pdf')

        @exports_bp.route('/recipe/<int:recipe_id>/candle-label.csv')
        @login_required
        def candle_label_recipe_csv(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            csv_text = ExportService.candle_label_csv(recipe=rec)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/recipe/<int:recipe_id>/candle-label.pdf')
        @login_required
        def candle_label_recipe_pdf(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            pdf_bytes = ExportService.candle_label_pdf(recipe=rec)
            return Response(pdf_bytes, mimetype='application/pdf')

        @exports_bp.route('/recipe/<int:recipe_id>/baker-sheet.csv')
        @login_required
        def baker_sheet_recipe_csv(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            csv_text = ExportService.baker_sheet_csv(recipe=rec)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/recipe/<int:recipe_id>/baker-sheet.pdf')
        @login_required
        def baker_sheet_recipe_pdf(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            pdf_bytes = ExportService.baker_sheet_pdf(recipe=rec)
            return Response(pdf_bytes, mimetype='application/pdf')

        @exports_bp.route('/recipe/<int:recipe_id>/lotion-inci.csv')
        @login_required
        def lotion_inci_recipe_csv(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            csv_text = ExportService.lotion_inci_csv(recipe=rec)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/recipe/<int:recipe_id>/lotion-inci.pdf')
        @login_required
        def lotion_inci_recipe_pdf(recipe_id: int):
            from flask import abort, Response
            rec = db.session.get(Recipe, recipe_id)
            if not rec:
                abort(404)
            if getattr(current_user, 'organization_id', None) and rec.organization_id != current_user.organization_id:
                abort(403)
            from app.services.exports import ExportService
            pdf_bytes = ExportService.lotion_inci_pdf(recipe=rec)
            return Response(pdf_bytes, mimetype='application/pdf')

        # Public tool preview CSV/PDF using session draft
        @exports_bp.route('/tool/soaps/inci.csv')
        def soap_inci_tool_csv():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            csv_text = ExportService.soap_inci_csv(tool_draft=draft)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/tool/soaps/inci.pdf')
        def soap_inci_tool_pdf():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            pdf_bytes = ExportService.soap_inci_pdf(tool_draft=draft)
            return Response(pdf_bytes, mimetype='application/pdf')

        @exports_bp.route('/tool/candles/label.csv')
        def candle_label_tool_csv():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            csv_text = ExportService.candle_label_csv(tool_draft=draft)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/tool/candles/label.pdf')
        def candle_label_tool_pdf():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            pdf_bytes = ExportService.candle_label_pdf(tool_draft=draft)
            return Response(pdf_bytes, mimetype='application/pdf')

        @exports_bp.route('/tool/baker/sheet.csv')
        def baker_sheet_tool_csv():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            csv_text = ExportService.baker_sheet_csv(tool_draft=draft)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/tool/baker/sheet.pdf')
        def baker_sheet_tool_pdf():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            pdf_bytes = ExportService.baker_sheet_pdf(tool_draft=draft)
            return Response(pdf_bytes, mimetype='application/pdf')

        @exports_bp.route('/tool/lotions/inci.csv')
        def lotion_inci_tool_csv():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            csv_text = ExportService.lotion_inci_csv(tool_draft=draft)
            return Response(csv_text, mimetype='text/csv')

        @exports_bp.route('/tool/lotions/inci.pdf')
        def lotion_inci_tool_pdf():
            from flask import session, Response
            draft = session.get('tool_draft') or {}
            from app.services.exports import ExportService
            pdf_bytes = ExportService.lotion_inci_pdf(tool_draft=draft)
            return Response(pdf_bytes, mimetype='application/pdf')

        app.register_blueprint(exports_bp)
        successful_registrations.append('Exports')
    except Exception as e:
        failed_registrations.append(f"Exports: {e}")
        # Don't let exports failure break the app
        pass


    # Log summary (avoid noisy stdout in production)
    app_logger = getattr(app, 'logger', logger)

    # Only log in debug mode or if there are failures
    if app.debug or failed_registrations:
        app_logger.info("=== Blueprint Registration Summary ===")
        app_logger.info(f"Successful: {len(successful_registrations)}")
        if app.debug:
            for name in successful_registrations:
                app_logger.info(f"   - {name}")
        if failed_registrations:
            app_logger.error(f"Failed: {len(failed_registrations)}")
            for error in failed_registrations:
                app_logger.error(f"   - {error}")
        else:
            app_logger.info("All blueprints registered successfully!")


    # CSRF exemptions
    try:
        from .extensions import csrf
        csrf.exempt(app.view_functions["inventory.adjust_inventory"])
        if "waitlist.join_waitlist" in app.view_functions:
            csrf.exempt(app.view_functions["waitlist.join_waitlist"])
        # Exempt public tools draft endpoint for anonymous users saving drafts
        if "tools_bp.tools_draft" in app.view_functions:
            csrf.exempt(app.view_functions["tools_bp.tools_draft"])
    except Exception:
        pass