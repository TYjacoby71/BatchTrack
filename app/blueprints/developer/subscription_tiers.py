"""Developer routes for subscription tiers and entitlement wiring.

Synopsis:
Manage tier limits, permissions, and add-on availability for billing.

Glossary:
- Allowed add-on: Purchasable entitlement for a tier.
- Included add-on: Entitlement granted to all orgs on the tier.
"""

import logging

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from app.models import SubscriptionTier
from app.models.addon import Addon
from app.services.ai import GoogleAIClientError
from app.services.developer.subscription_tier_route_service import (
    SubscriptionTierRouteService,
)
from app.services.signup_checkout_service import SignupCheckoutService
from app.services.signup_info_partial_service import (
    SignupInfoPartialService,
    SignupInfoPartialServiceError,
)
from app.utils.permissions import (  # Assuming this is the correct import
    require_permission,
)

logger = logging.getLogger(__name__)


# --- Load Tiers Config ---
# Purpose: Implement `load_tiers_config` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def load_tiers_config():
    raise RuntimeError(
        "Deprecated: load_tiers_config removed. Query SubscriptionTier directly."
    )


subscription_tiers_bp = Blueprint(
    "subscription_tiers", __name__, url_prefix="/subscription-tiers"
)


# ---  Addon Permission Map ---
# Purpose: Implement `_addon_permission_map` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _addon_permission_map(addons):
    addon_perm_names = [a.permission_name for a in addons if a and a.permission_name]
    if not addon_perm_names:
        return {}
    permissions = SubscriptionTierRouteService.list_active_permissions_for_names(
        names=addon_perm_names
    )
    perm_by_name = {p.name: p for p in permissions}
    return {
        addon.id: perm_by_name.get(addon.permission_name)
        for addon in addons
        if addon.permission_name and perm_by_name.get(addon.permission_name)
    }


# ---  Base Permissions ---
# Purpose: Implement `_base_permissions` behavior for this module.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
def _base_permissions(addons):
    addon_perm_names = [a.permission_name for a in addons if a and a.permission_name]
    return SubscriptionTierRouteService.list_base_permissions_excluding_names(
        excluded_names=addon_perm_names
    )


# =========================================================
# TIER MANAGEMENT
# =========================================================
# --- List tiers ---
# Purpose: Show tiers with permission and add-on snapshots.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/")
@login_required
@require_permission("dev.manage_tiers")
def manage_tiers():
    """Main page to view all tiers directly from the database."""
    all_tiers_db = SubscriptionTierRouteService.list_all_tiers_ordered()
    all_permissions = SubscriptionTierRouteService.list_active_permissions_ordered()

    # Convert to dictionary format expected by template
    tiers_dict = {}
    for tier in all_tiers_db:
        # Get live pricing from Stripe if available
        price_display = "N/A"
        live_pricing = None

        if tier.stripe_lookup_key:
            try:
                from ...services.billing_service import BillingService

                live_pricing = BillingService.get_live_pricing_for_tier(tier)
                if live_pricing:
                    price_display = live_pricing["formatted_price"]
            except Exception as e:
                logger.warning(f"Could not fetch live pricing for tier {tier.id}: {e}")

        if tier.billing_provider == "exempt":
            price_display = "Free"

        tiers_dict[tier.id] = {
            "id": tier.id,  # Include the tier ID
            "name": tier.name,
            "description": tier.description,
            "marketing_tagline": tier.marketing_tagline,
            "marketing_summary": tier.marketing_summary,
            "marketing_bullets": tier.marketing_bullets,
            "user_limit": tier.user_limit,
            "is_customer_facing": tier.is_customer_facing,
            "is_available": getattr(tier, "is_available", True),
            "billing_provider": tier.billing_provider,
            "commission_percentage": float(tier.commission_percentage or 0),
            "is_billing_exempt": tier.is_billing_exempt,
            "stripe_lookup_key": tier.stripe_lookup_key,
            "stripe_storage_lookup_key": getattr(
                tier, "stripe_storage_lookup_key", None
            ),
            "whop_product_key": tier.whop_product_key,
            "stripe_price": price_display,  # Now shows actual pricing
            "last_synced": live_pricing.get("last_synced") if live_pricing else None,
            "whop_last_synced": None,  # TODO: Add whop sync tracking
            "permissions": [p.name for p in tier.permissions],
            "pricing_category": "standard",  # Default value
            "billing_cycle": "monthly",  # Default value
            "requires_billing": not tier.is_billing_exempt,
            "requires_stripe_billing": tier.requires_stripe_billing,
            "supports_whop": bool(tier.whop_product_key),
            "max_users": tier.max_users,
            "max_recipes": tier.max_recipes,
            "max_batches": tier.max_batches,
            "max_products": tier.max_products,
            "max_batchbot_requests": tier.max_batchbot_requests,
            "max_monthly_batches": tier.max_monthly_batches,
            "data_retention_days": tier.data_retention_days,
            "retention_notice_days": tier.retention_notice_days,
            "retention_policy": getattr(tier, "retention_policy", "one_year"),
            "retention_label": tier.retention_label,
            "allowed_addon_ids": [a.id for a in getattr(tier, "allowed_addons", [])],
            "included_addon_ids": [a.id for a in getattr(tier, "included_addons", [])],
        }

    return render_template(
        "developer/subscription_tiers.html",
        tiers=tiers_dict,
        tiers_dict=tiers_dict,
        all_permissions=all_permissions,
    )


# =========================================================
# SIGNUP INFO PARTIALS
# =========================================================
# --- Manage signup info partials ---
# Purpose: Configure below-pricing signup content partials and tier assignments.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/signup-info-partials", methods=["GET"])
@login_required
@require_permission("dev.manage_tiers")
def manage_signup_info_partials():
    partials = SignupInfoPartialService.list_partials(include_archived=True)
    open_partial_id = str(request.args.get("open_partial_id") or "").strip()
    active_partial = None
    if open_partial_id:
        active_partial = next(
            (
                partial
                for partial in partials
                if str(partial.get("id") or "") == open_partial_id
            ),
            None,
        )
    if not active_partial and partials:
        active_partial = partials[0]
        open_partial_id = str(active_partial.get("id") or "")
    return render_template(
        "developer/signup_info_partials.html",
        partials=partials,
        open_partial_id=open_partial_id,
        active_partial=active_partial,
    )


# --- Create signup info partial ---
# Purpose: Create a new signup info partial.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/signup-info-partials/create", methods=["POST"])
@login_required
@require_permission("dev.manage_tiers")
def create_signup_info_partial():
    name = (request.form.get("name") or "").strip()
    html_content = request.form.get("html_content") or ""
    status = request.form.get("status") or "draft"
    created = None
    if not name:
        flash("Partial name is required.", "error")
        return redirect(url_for(".manage_signup_info_partials"))
    if not str(html_content or "").strip():
        html_content = (
            "<div class='signup-info-block'>"
            "<h3>Start your first tracked batch in under 20 minutes.</h3>"
            "<p>Use this draft as a base and tell BatchBot exactly what to change.</p>"
            "<ul><li>Outcome-first headline</li><li>Fast perceived value</li><li>Trust anchor</li></ul>"
            "</div>"
        )
    try:
        created = SignupInfoPartialService.create_partial(
            name=name,
            html_content=html_content,
            status=status,
        )
        flash(f'Created partial "{created.get("name")}".', "success")
    except SignupInfoPartialServiceError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        logger.error("Failed to create signup info partial: %s", exc)
        flash("Unable to create signup info partial.", "error")
    if created and str(request.form.get("open_after") or "") == "1":
        return redirect(
            url_for(
                ".manage_signup_info_partials",
                open_partial_id=str(created.get("id") or ""),
            )
        )
    return redirect(url_for(".manage_signup_info_partials"))


# --- Update signup info partial ---
# Purpose: Update an existing signup info partial.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route(
    "/signup-info-partials/<partial_id>/update", methods=["POST"]
)
@login_required
@require_permission("dev.manage_tiers")
def update_signup_info_partial(partial_id):
    name = request.form.get("name")
    html_content = request.form.get("html_content")
    status = request.form.get("status")
    try:
        updated = SignupInfoPartialService.update_partial(
            partial_id=str(partial_id),
            name=name,
            status=status,
            html_content=html_content,
        )
        flash(f'Updated partial "{updated.get("name")}".', "success")
    except SignupInfoPartialServiceError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        logger.error("Failed to update signup info partial %s: %s", partial_id, exc)
        flash("Unable to update signup info partial.", "error")
    return redirect(url_for(".manage_signup_info_partials", open_partial_id=partial_id))


# --- Clone signup info partial ---
# Purpose: Create a draft version from an existing signup info partial.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route(
    "/signup-info-partials/<partial_id>/clone", methods=["POST"]
)
@login_required
@require_permission("dev.manage_tiers")
def clone_signup_info_partial(partial_id):
    as_name = (request.form.get("as_name") or "").strip() or None
    cloned = None
    try:
        cloned = SignupInfoPartialService.clone_partial(
            partial_id=str(partial_id),
            as_name=as_name,
            status="draft",
        )
        flash(
            f'Created draft "{cloned.get("name")}" from {partial_id}.',
            "success",
        )
    except SignupInfoPartialServiceError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        logger.error("Failed to clone signup info partial %s: %s", partial_id, exc)
        flash("Unable to clone signup info partial.", "error")
    if cloned:
        return redirect(
            url_for(
                ".manage_signup_info_partials",
                open_partial_id=str(cloned.get("id") or ""),
            )
        )
    return redirect(url_for(".manage_signup_info_partials", open_partial_id=partial_id))


# --- Apply AI edits to existing signup info draft ---
# Purpose: Rewrite the currently open draft in-place from a prompt.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route(
    "/signup-info-partials/<partial_id>/ai-edit", methods=["POST"]
)
@login_required
@require_permission("dev.manage_tiers")
def apply_signup_info_ai_edit(partial_id):
    prompt = (request.form.get("prompt") or "").strip()
    if not prompt:
        flash("BatchBot prompt is required.", "error")
        return redirect(
            url_for(".manage_signup_info_partials", open_partial_id=partial_id)
        )
    signup_tiers = SubscriptionTierRouteService.list_signup_customer_facing_paid_tiers()
    tier_names = [str(tier.name or "").strip() for tier in signup_tiers if tier.name]
    allow_name_update = str(request.form.get("allow_name_update") or "") == "1"
    try:
        SignupInfoPartialService.apply_ai_edit(
            partial_id=str(partial_id),
            prompt=prompt,
            tier_names=tier_names,
            allow_name_update=allow_name_update,
        )
        flash("BatchBot updated this draft version.", "success")
    except SignupInfoPartialServiceError as exc:
        flash(str(exc), "error")
    except GoogleAIClientError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        logger.error(
            "Failed to apply AI edits to signup info draft %s: %s", partial_id, exc
        )
        flash("Unable to apply BatchBot draft edits.", "error")
    return redirect(url_for(".manage_signup_info_partials", open_partial_id=partial_id))


# --- Generate AI signup info draft ---
# Purpose: Generate a draft signup info partial from a developer prompt.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route(
    "/signup-info-partials/<partial_id>/ai-draft", methods=["POST"]
)
@login_required
@require_permission("dev.manage_tiers")
def generate_signup_info_ai_draft(partial_id):
    prompt = (request.form.get("prompt") or "").strip()
    drafted = None
    if not prompt:
        flash("AI prompt is required.", "error")
        return redirect(url_for(".manage_signup_info_partials"))
    signup_tiers = SubscriptionTierRouteService.list_signup_customer_facing_paid_tiers()
    tier_names = [str(tier.name or "").strip() for tier in signup_tiers if tier.name]
    try:
        drafted = SignupInfoPartialService.create_ai_draft(
            partial_id=str(partial_id),
            prompt=prompt,
            tier_names=tier_names,
        )
        flash(
            f'AI draft "{drafted.get("name")}" created successfully.',
            "success",
        )
    except SignupInfoPartialServiceError as exc:
        flash(str(exc), "error")
    except GoogleAIClientError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        logger.error(
            "Failed to generate AI signup info draft for %s: %s", partial_id, exc
        )
        flash("Unable to generate AI draft.", "error")
    if drafted:
        return redirect(
            url_for(
                ".manage_signup_info_partials",
                open_partial_id=str(drafted.get("id") or ""),
            )
        )
    return redirect(url_for(".manage_signup_info_partials", open_partial_id=partial_id))


# --- Save signup info assignments ---
# Purpose: Persist default and tier-specific partial assignment settings.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/signup-info-partials/assignments", methods=["POST"])
@login_required
@require_permission("dev.manage_tiers")
def save_signup_info_assignments():
    signup_tiers = SubscriptionTierRouteService.list_signup_customer_facing_paid_tiers()
    default_assignment = {
        "mode": request.form.get("default_mode", "manual"),
        "primary_partial_id": request.form.get("default_primary_partial_id", ""),
        "secondary_partial_id": request.form.get("default_secondary_partial_id", ""),
    }
    tier_assignments: dict[str, dict[str, str]] = {}
    for tier in signup_tiers:
        tier_id = str(tier.id)
        tier_assignments[tier_id] = {
            "mode": request.form.get(f"tier_{tier_id}_mode", "manual"),
            "primary_partial_id": request.form.get(
                f"tier_{tier_id}_primary_partial_id", ""
            ),
            "secondary_partial_id": request.form.get(
                f"tier_{tier_id}_secondary_partial_id", ""
            ),
        }
    try:
        SignupInfoPartialService.save_assignments(
            default_assignment=default_assignment,
            tier_assignments=tier_assignments,
        )
        flash("Signup info assignments saved.", "success")
    except SignupInfoPartialServiceError as exc:
        flash(str(exc), "error")
    except Exception as exc:
        logger.error("Failed to save signup info assignments: %s", exc)
        flash("Unable to save signup info assignments.", "error")
    return redirect(url_for(".manage_signup_info_partials"))


# --- Preview signup info partial on signup page ---
# Purpose: Render signup page with a partial override for visual preview.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/signup-info-partials/preview", methods=["GET"])
@login_required
@require_permission("dev.manage_tiers")
def preview_signup_info_partial():
    signup_context = SignupCheckoutService.build_request_context(
        request=request,
        oauth_user_info=None,
        allow_live_pricing_network=False,
    )
    view_state = SignupCheckoutService.build_initial_view_state(signup_context)
    template_context = SignupCheckoutService.build_template_context(
        signup_context,
        view_state,
        oauth_available=False,
        oauth_providers={"google": False, "facebook": False},
        canonical_url=url_for("core.signup_alias", _external=True),
    )

    preview_partial_id = str(request.args.get("partial_id") or "").strip()
    if preview_partial_id:
        available_tiers = template_context.get("available_tiers") or {}
        tier_ids = [str(tier_id) for tier_id in available_tiers.keys()]
        preview_panels = SignupInfoPartialService.build_uniform_preview_panels(
            partial_id=preview_partial_id,
            tier_ids=tier_ids,
        )
        if preview_panels:
            template_context["signup_info_panel_by_tier"] = preview_panels
            selected_tier_id = str(
                template_context.get("selected_paid_tier_id")
                or template_context.get("default_tier_id")
                or ""
            ).strip()
            selected_panel = preview_panels.get(selected_tier_id)
            if not selected_panel:
                selected_panel = next(iter(preview_panels.values()))
            template_context["signup_info_selected_panel"] = selected_panel

    template_context["show_public_header"] = True
    template_context["preview_mode"] = True
    return render_template("pages/auth/signup.html", **template_context)


# --- Create tier ---
# Purpose: Create a new tier with limits and entitlements.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/create", methods=["GET", "POST"])
@login_required
@require_permission("dev.manage_tiers")
def create_tier():
    """Create a new SubscriptionTier record directly in the database."""
    if request.method == "POST":
        # Data Collection
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "")
        marketing_tagline = (request.form.get("marketing_tagline") or "").strip()
        marketing_summary = (request.form.get("marketing_summary") or "").strip()
        marketing_bullets = request.form.get("marketing_bullets", "")

        def _parse_int_allow_neg1(text, default):
            try:
                v = int(str(text).strip())
                return v
            except Exception:
                logger.warning(
                    "Suppressed exception fallback at app/blueprints/developer/subscription_tiers.py:172",
                    exc_info=True,
                )
                return default

        user_limit = _parse_int_allow_neg1(request.form.get("user_limit", 1), 1)
        max_users = request.form.get("max_users", None)
        max_recipes = request.form.get("max_recipes", None)
        request.form.get("max_batches", None)
        max_products = request.form.get("max_products", None)
        max_batchbot_requests = request.form.get("max_batchbot_requests", None)
        max_monthly_batches = request.form.get("max_monthly_batches", None)
        retention_policy = (request.form.get("retention_policy") or "one_year").strip()
        data_retention_days_raw = request.form.get("data_retention_days", "").strip()
        retention_notice_days_raw = request.form.get(
            "retention_notice_days", ""
        ).strip()
        commission_percentage_raw = (
            request.form.get("commission_percentage") or ""
        ).strip()

        billing_provider = request.form.get("billing_provider", "exempt")
        stripe_key = request.form.get("stripe_lookup_key", "").strip()

        whop_key = request.form.get("whop_product_key", "").strip()

        # Convert limit fields to integers or None if empty, allow -1 for unlimited
        def parse_limit_field(value):
            if not value or value.strip() == "":
                return None
            try:
                num = int(value.strip())
                return num  # Allow -1 for unlimited
            except (ValueError, AttributeError):
                return None

        max_recipes = parse_limit_field(max_recipes)
        max_products = parse_limit_field(max_products)
        max_batchbot_requests = parse_limit_field(max_batchbot_requests)
        max_monthly_batches = parse_limit_field(max_monthly_batches)
        # Normalize retention settings
        data_retention_days = (
            int(data_retention_days_raw) if data_retention_days_raw.isdigit() else None
        )
        if retention_policy == "one_year":
            data_retention_days = 365
        elif retention_policy == "subscribed":
            data_retention_days = None
        retention_notice_days = (
            int(retention_notice_days_raw)
            if retention_notice_days_raw.isdigit()
            else None
        )
        try:
            commission_percentage = (
                round(float(commission_percentage_raw), 2)
                if commission_percentage_raw != ""
                else 0.0
            )
        except (TypeError, ValueError):
            flash("Commission percentage must be a number between 0 and 100.", "error")
            return redirect(url_for(".create_tier"))
        if commission_percentage < 0 or commission_percentage > 100:
            flash("Commission percentage must be between 0 and 100.", "error")
            return redirect(url_for(".create_tier"))

        # Validation
        if not name:
            flash("Tier Name is required.", "error")
            return redirect(url_for(".create_tier"))

        # Check for duplicate name
        if SubscriptionTierRouteService.tier_name_exists(name=name):
            flash(f"A tier with the name '{name}' already exists.", "error")
            return redirect(url_for(".create_tier"))

        # BILLING REQUIREMENTS:
        # For non-exempt tiers, require proper billing integration
        if billing_provider == "stripe":
            if not stripe_key:
                flash(
                    "A Stripe Lookup Key is required for Stripe-billed tiers.", "error"
                )
                return redirect(url_for(".create_tier"))
        elif billing_provider == "whop":
            if not whop_key:
                flash("A Whop Product Key is required for Whop-billed tiers.", "error")
                return redirect(url_for(".create_tier"))

        # Database Insertion
        is_customer_facing = "is_customer_facing" in request.form
        tier = SubscriptionTier(
            name=name,
            description=description,
            marketing_tagline=marketing_tagline or None,
            marketing_summary=marketing_summary or None,
            marketing_bullets=(marketing_bullets or "").strip() or None,
            user_limit=user_limit,
            max_users=max_users,
            max_recipes=max_recipes,
            max_products=max_products,
            max_batchbot_requests=max_batchbot_requests,
            max_monthly_batches=max_monthly_batches,
            retention_policy=retention_policy,
            data_retention_days=data_retention_days,
            retention_notice_days=retention_notice_days,
            billing_provider=billing_provider,
            commission_percentage=commission_percentage,
            stripe_lookup_key=stripe_key if stripe_key else None,
            whop_product_key=whop_key if whop_key else None,
            is_customer_facing=is_customer_facing,
        )

        # Add permissions (merge with addon-linked permissions)
        permission_ids = set(request.form.getlist("permissions", type=int))

        addon_ids = request.form.getlist("allowed_addons", type=int)
        included_ids = request.form.getlist("included_addons", type=int)
        SubscriptionTierRouteService.create_tier_with_relationships(
            tier=tier,
            permission_ids=permission_ids,
            addon_ids=addon_ids,
            included_ids=included_ids,
        )

        logger.info(f"Created subscription tier: {name} (id: {tier.id})")
        flash(f'Subscription tier "{name}" created successfully.', "success")
        return redirect(url_for(".manage_tiers"))

    # For GET request
    all_addons = SubscriptionTierRouteService.list_active_addons_ordered()
    addon_permissions = _addon_permission_map(all_addons)
    all_permissions = _base_permissions(all_addons)
    return render_template(
        "developer/create_tier.html",
        all_permissions=all_permissions,
        all_addons=all_addons,
        addon_permissions=addon_permissions,
    )


# --- Edit tier ---
# Purpose: Edit tier limits, permissions, and add-on entitlements.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/edit/<int:tier_id>", methods=["GET", "POST"])
@login_required
@require_permission("dev.manage_tiers")
def edit_tier(tier_id):
    """Edit an existing tier by its database ID."""
    tier = SubscriptionTierRouteService.get_tier(tier_id=tier_id)
    if not tier:
        flash("Tier not found.", "error")
        return redirect(url_for(".manage_tiers"))

    if request.method == "POST":
        # Data Collection & Validation
        billing_provider = request.form.get("billing_provider", "exempt")
        # The following line is removed as is_billing_exempt is no longer used directly for logic
        # is_billing_exempt = 'is_billing_exempt' in request.form
        stripe_key = request.form.get("stripe_lookup_key", "").strip()
        whop_key = request.form.get("whop_product_key", "").strip()

        # STRICT BILLING REQUIREMENTS:
        # Unless billing bypass is explicitly enabled (billing_provider == 'exempt'), require proper billing integration
        if billing_provider != "exempt":
            if billing_provider == "stripe":
                if not stripe_key:
                    flash(
                        "A Stripe Lookup Key is required for Stripe-billed tiers.",
                        "error",
                    )
                    return redirect(url_for(".edit_tier", tier_id=tier_id))
            elif billing_provider == "whop":
                if not whop_key:
                    flash(
                        "A Whop Product Key is required for Whop-billed tiers.", "error"
                    )
                    return redirect(url_for(".edit_tier", tier_id=tier_id))
            else:
                flash(
                    'You must select either Stripe or Whop as billing provider, or choose "Exempt".',
                    "error",
                )
                return redirect(url_for(".edit_tier", tier_id=tier_id))

        # Update and Save
        try:
            tier.name = request.form.get("name", tier.name)
            tier.description = request.form.get("description", tier.description)
            tier.marketing_tagline = (
                request.form.get("marketing_tagline") or ""
            ).strip() or None
            tier.marketing_summary = (
                request.form.get("marketing_summary") or ""
            ).strip() or None
            tier.marketing_bullets = (
                request.form.get("marketing_bullets") or ""
            ).strip() or None
            tier.is_customer_facing = "is_customer_facing" in request.form
            # Allow -1 for unlimited
            try:
                tier.user_limit = int(request.form.get("user_limit", tier.user_limit))
            except (ValueError, TypeError):
                tier.user_limit = tier.user_limit

            # Update limit fields, converting to int or None, allow -1 for unlimited
            # Stop processing legacy max_users from form; keep existing DB value intact
            # (We keep the column for backward compatibility but do not expose/edit it)

            def parse_limit_field(value):
                if not value or value.strip() == "":
                    return None
                try:
                    num = int(value.strip())
                    return num  # Allow -1 for unlimited
                except (ValueError, AttributeError):
                    return None

            max_recipes = request.form.get(
                "max_recipes",
                str(tier.max_recipes) if tier.max_recipes is not None else "",
            )
            tier.max_recipes = parse_limit_field(max_recipes)

            max_products = request.form.get(
                "max_products",
                str(tier.max_products) if tier.max_products is not None else "",
            )
            tier.max_products = parse_limit_field(max_products)

            max_batchbot_requests = request.form.get(
                "max_batchbot_requests",
                (
                    str(tier.max_batchbot_requests)
                    if tier.max_batchbot_requests is not None
                    else ""
                ),
            )
            tier.max_batchbot_requests = parse_limit_field(max_batchbot_requests)

            max_monthly_batches = request.form.get(
                "max_monthly_batches",
                (
                    str(tier.max_monthly_batches)
                    if tier.max_monthly_batches is not None
                    else ""
                ),
            )
            tier.max_monthly_batches = parse_limit_field(max_monthly_batches)

            tier.billing_provider = billing_provider
            # tier.is_billing_exempt is removed from updates as it's derived from billing_provider
            tier.stripe_lookup_key = stripe_key or None

            tier.whop_product_key = whop_key or None

            # Retention fields
            retention_policy = (
                request.form.get("retention_policy")
                or getattr(tier, "retention_policy", "one_year")
            ).strip()
            data_retention_days_raw = request.form.get(
                "data_retention_days", ""
            ).strip()
            retention_notice_days_raw = request.form.get(
                "retention_notice_days", ""
            ).strip()
            commission_percentage_raw = (
                request.form.get("commission_percentage")
                or str(tier.commission_percentage or 0)
            ).strip()
            # Apply policy normalization
            if retention_policy == "one_year":
                tier.retention_policy = "one_year"
                tier.data_retention_days = 365
            elif retention_policy == "subscribed":
                tier.retention_policy = "subscribed"
                tier.data_retention_days = None
            else:
                # Fallback: keep provided days if valid, otherwise default to 365
                tier.retention_policy = "one_year"
                tier.data_retention_days = (
                    int(data_retention_days_raw)
                    if data_retention_days_raw.isdigit()
                    else 365
                )
            tier.retention_notice_days = (
                int(retention_notice_days_raw)
                if retention_notice_days_raw.isdigit()
                else None
            )
            try:
                commission_percentage = round(float(commission_percentage_raw), 2)
            except (TypeError, ValueError):
                flash(
                    "Commission percentage must be a number between 0 and 100.",
                    "error",
                )
                return redirect(url_for(".edit_tier", tier_id=tier_id))
            if commission_percentage < 0 or commission_percentage > 100:
                flash("Commission percentage must be between 0 and 100.", "error")
                return redirect(url_for(".edit_tier", tier_id=tier_id))
            tier.commission_percentage = commission_percentage

            # Update allowed and included add-ons
            addon_ids = request.form.getlist("allowed_addons", type=int)
            included_ids = request.form.getlist("included_addons", type=int)
            permission_ids = set(request.form.getlist("permissions", type=int))
            SubscriptionTierRouteService.update_tier_relationships(
                tier=tier,
                permission_ids=permission_ids,
                addon_ids=addon_ids,
                included_ids=included_ids,
            )

            logger.info(f"Updated subscription tier: {tier.name} (id: {tier.id})")
            flash(f'Subscription tier "{tier.name}" updated successfully.', "success")
            return redirect(url_for(".manage_tiers"))

        except Exception as e:
            logger.warning(
                "Suppressed exception fallback at app/blueprints/developer/subscription_tiers.py:501",
                exc_info=True,
            )
            SubscriptionTierRouteService.rollback_session()
            logger.error(f"Error updating tier: {e}")
            flash("Error updating tier. Please try again.", "error")
            return redirect(url_for(".edit_tier", tier_id=tier_id))

    # For GET request
    all_addons = SubscriptionTierRouteService.list_active_addons_ordered()
    addon_permissions = _addon_permission_map(all_addons)
    all_permissions = _base_permissions(all_addons)
    return render_template(
        "developer/edit_tier.html",
        tier=tier,
        all_permissions=all_permissions,
        all_addons=all_addons,
        addon_permissions=addon_permissions,
    )


# --- Delete tier ---
# Purpose: Delete an unused tier.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/delete/<int:tier_id>", methods=["POST"])
@login_required
@require_permission("dev.manage_tiers")
def delete_tier(tier_id):
    """Delete a tier from the database, with safety checks."""
    tier = SubscriptionTierRouteService.get_tier(tier_id=tier_id)
    if not tier:
        flash("Tier not found.", "error")
        return redirect(url_for(".manage_tiers"))

    # Safety check for system-critical tiers
    if tier.id in [1, 2]:  # Assuming default IDs for exempt and free tiers
        flash(f'Cannot delete the system-critical "{tier.name}" tier.', "error")
        return redirect(url_for(".manage_tiers"))

    # Check for organizations using this tier
    orgs_on_tier = SubscriptionTierRouteService.count_organizations_on_tier(
        tier_id=tier_id
    )
    if orgs_on_tier > 0:
        flash(
            f'Cannot delete "{tier.name}" as {orgs_on_tier} organization(s) are currently subscribed to it.',
            "error",
        )
        return redirect(url_for(".manage_tiers"))

    try:
        SubscriptionTierRouteService.delete_tier(tier=tier)

        logger.info(f"Deleted subscription tier: {tier.name} (id: {tier.id})")
        flash(f'Subscription tier "{tier.name}" has been deleted.', "success")

    except Exception as e:
        logger.warning(
            "Suppressed exception fallback at app/blueprints/developer/subscription_tiers.py:555",
            exc_info=True,
        )
        SubscriptionTierRouteService.rollback_session()
        logger.error(f"Error deleting tier: {e}")
        flash("Error deleting tier. Please try again.", "error")

    return redirect(url_for(".manage_tiers"))


# =========================================================
# PROVIDER SYNC
# =========================================================
# --- Sync Stripe pricing ---
# Purpose: Pull Stripe pricing metadata for a tier.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/sync/<int:tier_id>", methods=["POST"])
@login_required
@require_permission("dev.manage_tiers")
def sync_tier_with_stripe(tier_id):
    """Sync a specific tier with Stripe pricing"""
    tier = SubscriptionTierRouteService.get_tier(tier_id=tier_id)
    if not tier:
        return jsonify({"success": False, "error": "Tier not found"}), 404

    if not tier.stripe_lookup_key:
        return (
            jsonify({"success": False, "error": "No Stripe lookup key configured"}),
            400,
        )

    try:
        from ...services.billing_service import BillingService

        # Get live pricing from Stripe
        live_pricing = BillingService.get_live_pricing_for_tier(tier)
        if live_pricing:
            logger.info(
                f'Successfully synced tier {tier.name} with Stripe - Price: {live_pricing["formatted_price"]}'
            )
            return jsonify(
                {
                    "success": True,
                    "message": f'Successfully synced {tier.name} with Stripe - Price: {live_pricing["formatted_price"]}',
                    "tier": {
                        "id": tier.id,
                        "key": str(tier.id),
                        "name": tier.name,
                        "stripe_price": live_pricing["formatted_price"],
                    },
                }
            )
        else:
            logger.warning(
                f"No pricing found for tier {tier.name} with lookup key {tier.stripe_lookup_key}"
            )
            return (
                jsonify(
                    {
                        "success": False,
                        "error": f"No pricing found in Stripe for lookup key: {tier.stripe_lookup_key}",
                    }
                ),
                400,
            )

    except Exception as e:
        logger.error(f"Error syncing tier {tier_id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# --- Sync Whop pricing ---
# Purpose: Pull Whop pricing metadata for a tier.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/sync-whop/<int:tier_id>", methods=["POST"])
@login_required
@require_permission("dev.manage_tiers")
def sync_tier_with_whop(tier_id):
    """Sync a specific tier with Whop"""
    tier = SubscriptionTierRouteService.get_tier(tier_id=tier_id)
    if not tier:
        return jsonify({"success": False, "error": "Tier not found"}), 404

    if not tier.whop_product_key:
        return (
            jsonify({"success": False, "error": "No Whop product key configured"}),
            400,
        )

    try:
        # Here you would implement actual Whop sync logic
        # For now, return success
        logger.info(f"Synced tier {tier_id} with Whop")
        return jsonify(
            {"success": True, "message": f"Successfully synced {tier.name} with Whop"}
        )
    except Exception as e:
        logger.error(f"Error syncing tier {tier_id} with Whop: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =========================================================
# API
# =========================================================
# --- Tier metadata API ---
# Purpose: Return tier metadata for developer UI.
# Inputs: Function arguments plus active request/application context.
# Outputs: Return value or response payload for caller/HTTP client.
@subscription_tiers_bp.route("/api/tiers")
@login_required
@require_permission("dev.manage_tiers")
def api_get_tiers():
    """API endpoint to get all tiers as JSON."""
    tiers = SubscriptionTierRouteService.list_customer_facing_tiers()
    return jsonify(
        [
            {
                "id": tier.id,
                "key": str(tier.id),  # Use ID as key for API
                "name": tier.name,
                "description": tier.description,
                "marketing_tagline": tier.marketing_tagline,
                "marketing_summary": tier.marketing_summary,
                "marketing_bullets": tier.marketing_bullets,
                "user_limit": tier.user_limit,
                "billing_provider": tier.billing_provider,
                "is_billing_exempt": tier.is_billing_exempt,
                "has_valid_integration": tier.has_valid_integration,
                "permissions": tier.get_permission_names(),
                "max_users": tier.max_users,
                "max_recipes": tier.max_recipes,
                "max_batches": tier.max_batches,
                "max_products": tier.max_products,
                "max_batchbot_requests": tier.max_batchbot_requests,
                "max_monthly_batches": tier.max_monthly_batches,
            }
            for tier in tiers
        ]
    )
