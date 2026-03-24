"""Developer routes for add-on catalog management.

Synopsis:
Create and maintain add-ons with permission and function-key bindings.

Glossary:
- Permission add-on: Grants RBAC permission when included or purchased.
- Function-key add-on: Feature toggle enforced in service logic.
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.services.developer.addon_service import AddonService
from app.utils.permissions import require_permission

addons_bp = Blueprint("addons", __name__, url_prefix="/addons")


# =========================================================
# ADD-ON CATALOG
# =========================================================
# --- List add-ons ---
# Purpose: Show all add-ons for entitlement configuration.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@addons_bp.route("/")
@login_required
@require_permission("dev.manage_tiers")
def list_addons():
    addons = AddonService.list_addons()
    return render_template("developer/addons/list.html", addons=addons)


# --- Create add-on ---
# Purpose: Create a new add-on record.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@addons_bp.route("/create", methods=["GET", "POST"])
@login_required
@require_permission("dev.manage_tiers")
def create_addon():
    if request.method == "POST":
        payload = AddonService.parse_payload_from_form(request.form, require_key=True)
        validation_error = AddonService.validate_create_payload(payload)
        if validation_error:
            flash(validation_error, "error")
            return redirect(url_for("developer.addons.create_addon"))

        AddonService.create_addon(payload)
        flash("Add-on created", "success")
        return redirect(url_for("developer.addons.list_addons"))

    return render_template("developer/addons/create.html")


# --- Edit add-on ---
# Purpose: Update add-on metadata and entitlements.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@addons_bp.route("/edit/<int:addon_id>", methods=["GET", "POST"])
@login_required
@require_permission("dev.manage_tiers")
def edit_addon(addon_id):
    addon = AddonService.get_addon(addon_id)
    if not addon:
        flash("Add-on not found", "error")
        return redirect(url_for("developer.addons.list_addons"))

    if request.method == "POST":
        payload = AddonService.parse_payload_from_form(request.form, require_key=False)
        AddonService.update_addon(addon, payload)
        flash("Add-on updated", "success")
        return redirect(url_for("developer.addons.list_addons"))

    return render_template("developer/addons/edit.html", addon=addon)


# --- Delete add-on ---
# Purpose: Remove an add-on from the catalog.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@addons_bp.route("/delete/<int:addon_id>", methods=["POST"])
@login_required
@require_permission("dev.manage_tiers")
def delete_addon(addon_id):
    addon = AddonService.get_addon(addon_id)
    if not addon:
        flash("Add-on not found", "error")
        return redirect(url_for("developer.addons.list_addons"))

    AddonService.delete_addon(addon)
    flash("Add-on deleted", "success")
    return redirect(url_for("developer.addons.list_addons"))
