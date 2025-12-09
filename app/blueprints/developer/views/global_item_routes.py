from __future__ import annotations

import json
import logging

from flask import (
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import and_, exists, or_

from app.extensions import db
from app.models import GlobalItem

from ..routes import developer_bp


@developer_bp.route("/global-items")
@login_required
def global_items_admin():
    """Developer admin page for managing Global Items."""
    item_type = request.args.get("type", "").strip()
    category_filter = request.args.get("category", "").strip()
    search_query = request.args.get("search", "").strip()

    query = GlobalItem.query.filter(GlobalItem.is_archived != True)

    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    if category_filter and item_type == "ingredient":
        from app.models.category import IngredientCategory

        query = query.join(
            IngredientCategory, GlobalItem.ingredient_category_id == IngredientCategory.id
        ).filter(IngredientCategory.name == category_filter)

    if search_query:
        term = f"%{search_query}%"
        try:
            alias_tbl = db.Table("global_item_alias", db.metadata, autoload_with=db.engine)
            query = query.filter(
                or_(
                    GlobalItem.name.ilike(term),
                    exists().where(
                        and_(alias_tbl.c.global_item_id == GlobalItem.id, alias_tbl.c.alias.ilike(term))
                    ),
                )
            )
        except Exception:
            query = query.filter(GlobalItem.name.ilike(term))

    page = request.args.get("page", type=int) or 1
    if page < 1:
        page = 1
    per_page_options = [20, 30, 40, 50]
    per_page = request.args.get("page_size", type=int) or per_page_options[0]
    if per_page not in per_page_options:
        per_page = per_page_options[0]

    pagination = query.order_by(
        GlobalItem.item_type.asc(),
        GlobalItem.name.asc(),
    ).paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items

    from app.models.category import IngredientCategory

    try:
        categories = [
            name
            for (name,) in db.session.query(IngredientCategory.name)
            .join(GlobalItem, GlobalItem.ingredient_category_id == IngredientCategory.id)
            .filter(
                IngredientCategory.organization_id == None,
                IngredientCategory.is_global_category == True,
                GlobalItem.item_type == "ingredient",
            )
            .distinct()
            .order_by(IngredientCategory.name)
            .all()
            if name
        ]
    except Exception:
        categories = [
            c.name
            for c in IngredientCategory.query.filter_by(
                organization_id=None, is_active=True, is_global_category=True
            )
            .order_by(IngredientCategory.name)
            .all()
        ]

    filter_params = {}
    if item_type:
        filter_params["type"] = item_type
    if category_filter:
        filter_params["category"] = category_filter
    if search_query:
        filter_params["search"] = search_query
    if per_page != per_page_options[0]:
        filter_params["page_size"] = per_page

    def build_page_url(page_number: int):
        params = dict(filter_params)
        params["page"] = page_number
        return url_for("developer.global_items_admin", **params)

    first_item_index = ((pagination.page - 1) * pagination.per_page) + 1 if pagination.total else 0
    last_item_index = min(pagination.page * pagination.per_page, pagination.total)

    return render_template(
        "developer/global_items.html",
        items=items,
        categories=categories,
        selected_type=item_type,
        selected_category=category_filter,
        search_query=search_query,
        pagination=pagination,
        per_page=per_page,
        per_page_options=per_page_options,
        filter_params=filter_params,
        build_page_url=build_page_url,
        first_item_index=first_item_index,
        last_item_index=last_item_index,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Global Item Library"},
        ],
    )


@developer_bp.route("/global-items/<int:item_id>")
@login_required
def global_item_detail(item_id):
    item = GlobalItem.query.get_or_404(item_id)
    from app.models.category import IngredientCategory

    global_ingredient_categories = (
        IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True,
        )
        .order_by(IngredientCategory.name)
        .all()
    )

    return render_template(
        "developer/global_item_detail.html",
        item=item,
        global_ingredient_categories=global_ingredient_categories,
    )


@developer_bp.route("/global-items/<int:item_id>/edit", methods=["POST"])
@login_required
def global_item_edit(item_id):
    """Edit existing global item."""
    from flask_wtf.csrf import validate_csrf

    try:
        validate_csrf(request.form.get("csrf_token"))
    except Exception as exc:
        flash(f"CSRF validation failed: {exc}", "error")
        return redirect(url_for("developer.global_item_detail", item_id=item_id))

    item = GlobalItem.query.get_or_404(item_id)
    before = {
        "name": item.name,
        "item_type": item.item_type,
        "default_unit": item.default_unit,
        "density": item.density,
        "capacity": item.capacity,
        "capacity_unit": item.capacity_unit,
        "container_material": getattr(item, "container_material", None),
        "container_type": getattr(item, "container_type", None),
        "container_style": getattr(item, "container_style", None),
        "default_is_perishable": item.default_is_perishable,
        "recommended_shelf_life_days": item.recommended_shelf_life_days,
        "aliases": item.aliases,
        "recommended_fragrance_load_pct": item.recommended_fragrance_load_pct,
        "is_active_ingredient": item.is_active_ingredient,
        "inci_name": item.inci_name,
        "protein_content_pct": item.protein_content_pct,
        "brewing_color_srm": item.brewing_color_srm,
        "brewing_potential_sg": item.brewing_potential_sg,
        "brewing_diastatic_power_lintner": item.brewing_diastatic_power_lintner,
        "fatty_acid_profile": item.fatty_acid_profile,
        "certifications": item.certifications,
    }

    item.name = request.form.get("name", item.name)
    item.item_type = request.form.get("item_type", item.item_type)
    item.default_unit = request.form.get("default_unit", item.default_unit)
    density = request.form.get("density")
    item.density = float(density) if density not in (None, "") else None
    capacity = request.form.get("capacity")
    item.capacity = float(capacity) if capacity not in (None, "") else None
    item.capacity_unit = request.form.get("capacity_unit", item.capacity_unit)
    try:
        item.container_material = (request.form.get("container_material") or "").strip() or None
        item.container_type = (request.form.get("container_type") or "").strip() or None
        item.container_style = (request.form.get("container_style") or "").strip() or None
        item.container_color = (request.form.get("container_color") or "").strip() or None
    except Exception:
        pass
    item.default_is_perishable = request.form.get("default_is_perishable") == "on"
    shelf_life = request.form.get("recommended_shelf_life_days")
    item.recommended_shelf_life_days = int(shelf_life) if shelf_life not in (None, "") else None

    aliases = request.form.get("aliases")
    if aliases is not None:
        item.aliases = [n.strip() for n in aliases.split(",") if n.strip()]

    item.recommended_fragrance_load_pct = request.form.get("recommended_fragrance_load_pct") or None
    item.is_active_ingredient = request.form.get("is_active_ingredient") == "on"
    item.inci_name = request.form.get("inci_name") or None

    protein = request.form.get("protein_content_pct")
    item.protein_content_pct = float(protein) if protein not in (None, "") else None

    brewing_color = request.form.get("brewing_color_srm")
    item.brewing_color_srm = float(brewing_color) if brewing_color not in (None, "") else None

    brewing_potential = request.form.get("brewing_potential_sg")
    item.brewing_potential_sg = float(brewing_potential) if brewing_potential not in (None, "") else None

    brewing_dp = request.form.get("brewing_diastatic_power_lintner")
    item.brewing_diastatic_power_lintner = float(brewing_dp) if brewing_dp not in (None, "") else None

    fatty_acid_profile_raw = request.form.get("fatty_acid_profile")
    if fatty_acid_profile_raw is not None:
        fatty_acid_profile_raw = fatty_acid_profile_raw.strip()
        if fatty_acid_profile_raw:
            try:
                item.fatty_acid_profile = json.loads(fatty_acid_profile_raw)
            except json.JSONDecodeError:
                flash("Invalid JSON for fatty acid profile. Please provide valid JSON.", "error")
        else:
            item.fatty_acid_profile = None

    certifications_raw = request.form.get("certifications")
    if certifications_raw is not None:
        certifications = [c.strip() for c in certifications_raw.split(",") if c.strip()]
        item.certifications = certifications or None

    ingredient_category_id = request.form.get("ingredient_category_id", "").strip()
    if ingredient_category_id and ingredient_category_id.isdigit():
        from app.models.category import IngredientCategory

        category = IngredientCategory.query.filter_by(
            id=int(ingredient_category_id),
            organization_id=None,
            is_global_category=True,
        ).first()
        item.ingredient_category_id = category.id if category else None
    else:
        item.ingredient_category_id = None

    try:
        db.session.commit()
        logging.info(
            "GLOBAL_ITEM_EDIT: user=%s item_id=%s before=%s",
            current_user.id,
            item.id,
            before,
        )
        flash("Global item updated successfully", "success")
    except Exception as exc:
        db.session.rollback()
        flash(f"Error updating global item: {exc}", "error")

    return redirect(url_for("developer.global_item_detail", item_id=item.id))


@developer_bp.route("/global-items/<int:item_id>/stats")
@login_required
def global_item_stats_view(item_id):
    from app.services.statistics.global_item_stats import GlobalItemStatsService

    item = GlobalItem.query.get_or_404(item_id)
    stats = GlobalItemStatsService.get_rollup(item_id)
    return render_template("developer/global_item_stats.html", item=item, stats=stats)


@developer_bp.route("/global-items/create", methods=["GET", "POST"])
@login_required
def create_global_item():
    """Create a new global item."""

    def render_form(form_data=None):
        from app.models.category import IngredientCategory

        global_ingredient_categories = (
            IngredientCategory.query.filter_by(
                organization_id=None,
                is_active=True,
                is_global_category=True,
            )
            .order_by(IngredientCategory.name)
            .all()
        )

        return render_template(
            "developer/create_global_item.html",
            global_ingredient_categories=global_ingredient_categories,
            form_data=form_data or {},
        )

    if request.method == "POST":
        form_data = request.form
        try:
            name = form_data.get("name", "").strip()
            item_type = form_data.get("item_type", "ingredient")
            default_unit = form_data.get("default_unit", "").strip() or None
            ingredient_category_id_str = form_data.get("ingredient_category_id", "").strip() or None

            if not name:
                flash("Name is required", "error")
                return render_form(form_data)

            ingredient_category_id = None
            if ingredient_category_id_str:
                if ingredient_category_id_str.isdigit():
                    from app.models.category import IngredientCategory

                    category = IngredientCategory.query.filter_by(
                        id=int(ingredient_category_id_str),
                        organization_id=None,
                        is_global_category=True,
                    ).first()
                    if category:
                        ingredient_category_id = category.id
                    else:
                        flash(
                            f'Ingredient category ID "{ingredient_category_id_str}" not found or invalid.',
                            "error",
                        )
                        return render_form(form_data)
                else:
                    flash(f"Invalid Ingredient Category ID format: '{ingredient_category_id_str}'", "error")
                    return render_form(form_data)

            existing = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
            if existing and not existing.is_archived:
                flash(f'Global item "{name}" of type "{item_type}" already exists', "error")
                return render_form(form_data)

            new_item = GlobalItem(
                name=name,
                item_type=item_type,
                default_unit=default_unit,
                ingredient_category_id=ingredient_category_id,
            )

            density = form_data.get("density")
            if density:
                try:
                    new_item.density = float(density)
                except ValueError:
                    flash("Invalid density value", "error")
                    return render_form(form_data)

            capacity = form_data.get("capacity")
            if capacity:
                try:
                    new_item.capacity = float(capacity)
                except ValueError:
                    flash("Invalid capacity value", "error")
                    return render_form(form_data)

            new_item.capacity_unit = form_data.get("capacity_unit", "").strip() or None
            try:
                new_item.container_material = (form_data.get("container_material") or "").strip() or None
                new_item.container_type = (form_data.get("container_type") or "").strip() or None
                new_item.container_style = (form_data.get("container_style") or "").strip() or None
                new_item.container_color = (form_data.get("container_color") or "").strip() or None
            except Exception:
                pass
            new_item.default_is_perishable = form_data.get("default_is_perishable") == "on"
            new_item.is_active_ingredient = form_data.get("is_active_ingredient") == "on"

            shelf_life = form_data.get("recommended_shelf_life_days")
            if shelf_life:
                try:
                    new_item.recommended_shelf_life_days = int(shelf_life)
                except ValueError:
                    flash("Invalid shelf life value", "error")
                    return render_form(form_data)

            new_item.recommended_fragrance_load_pct = (
                form_data.get("recommended_fragrance_load_pct", "").strip() or None
            )
            new_item.inci_name = form_data.get("inci_name", "").strip() or None

            protein_content = form_data.get("protein_content_pct", "").strip()
            if protein_content:
                try:
                    new_item.protein_content_pct = float(protein_content)
                except ValueError:
                    flash("Invalid protein content percentage", "error")
                    return render_form(form_data)

            brewing_color = form_data.get("brewing_color_srm", "").strip()
            if brewing_color:
                try:
                    new_item.brewing_color_srm = float(brewing_color)
                except ValueError:
                    flash("Invalid brewing SRM value", "error")
                    return render_form(form_data)

            brewing_potential = form_data.get("brewing_potential_sg", "").strip()
            if brewing_potential:
                try:
                    new_item.brewing_potential_sg = float(brewing_potential)
                except ValueError:
                    flash("Invalid brewing potential SG value", "error")
                    return render_form(form_data)

            brewing_dp = form_data.get("brewing_diastatic_power_lintner", "").strip()
            if brewing_dp:
                try:
                    new_item.brewing_diastatic_power_lintner = float(brewing_dp)
                except ValueError:
                    flash("Invalid brewing diastatic power value", "error")
                    return render_form(form_data)

            fatty_acid_profile_raw = form_data.get("fatty_acid_profile", "").strip()
            if fatty_acid_profile_raw:
                try:
                    new_item.fatty_acid_profile = json.loads(fatty_acid_profile_raw)
                except json.JSONDecodeError:
                    flash("Fatty acid profile must be valid JSON.", "error")
                    return render_form(form_data)

            certifications_raw = form_data.get("certifications", "").strip()
            if certifications_raw:
                new_item.certifications = [c.strip() for c in certifications_raw.split(",") if c.strip()]

            aliases_raw = form_data.get("aliases", "").strip()
            if aliases_raw:
                new_item.aliases = [n.strip() for n in aliases_raw.split(",") if n.strip()]

            db.session.add(new_item)
            db.session.commit()

            try:
                from app.services.event_emitter import EventEmitter
                from app.models.category import IngredientCategory

                category_name = None
                if new_item.ingredient_category_id:
                    cat_obj = db.session.get(IngredientCategory, new_item.ingredient_category_id)
                    category_name = cat_obj.name if cat_obj else None
                EventEmitter.emit(
                    event_name="global_item_created",
                    properties={
                        "name": name,
                        "item_type": item_type,
                        "ingredient_category": category_name,
                    },
                    user_id=getattr(current_user, "id", None),
                    entity_type="global_item",
                    entity_id=new_item.id,
                )
            except Exception:
                pass

            flash(f'Global item "{name}" created successfully', "success")
            return redirect(url_for("developer.global_item_detail", item_id=new_item.id))
        except Exception as exc:
            db.session.rollback()
            flash(f"Error creating global item: {exc}", "error")
            return render_form(form_data)

    return render_form()


@developer_bp.route("/global-items/<int:item_id>/delete", methods=["POST"])
@login_required
def delete_global_item(item_id):
    """Delete a global item, handling organization inventory disconnection."""
    try:
        data = request.get_json() or {}
        confirm_name = data.get("confirm_name", "").strip()
        force_delete = data.get("force_delete", False)

        item = GlobalItem.query.get_or_404(item_id)
        if confirm_name != item.name:
            return jsonify(
                {"success": False, "error": f'Confirmation text must match exactly: "{item.name}"'}
            )

        from app.models.inventory import InventoryItem

        connected_items = InventoryItem.query.filter_by(global_item_id=item.id).all()
        if connected_items and not force_delete:
            org_names = {
                inv_item.organization.name
                for inv_item in connected_items
                if inv_item.organization
            }
            return jsonify(
                {
                    "success": False,
                    "requires_confirmation": True,
                    "connected_count": len(connected_items),
                    "organizations": list(org_names),
                    "message": (
                        "This global item is connected to "
                        f"{len(connected_items)} inventory items across {len(org_names)} organizations. "
                        "These will be disconnected and become organization-owned items."
                    ),
                }
            )

        item_name = item.name
        connected_count = len(connected_items)

        if connected_items:
            for inv_item in connected_items:
                inv_item.global_item_id = None
                inv_item.is_org_custom_item = True

        if force_delete:
            db.session.delete(item)
        else:
            item.is_archived = True

        db.session.commit()

        try:
            from app.services.event_emitter import EventEmitter

            EventEmitter.emit(
                event_name="global_item_deleted",
                properties={"force_delete": force_delete},
                user_id=getattr(current_user, "id", None),
                entity_type="global_item",
                entity_id=item_id,
            )
        except Exception:
            pass

        if not force_delete:
            return jsonify(
                {
                    "success": True,
                    "message": f'Global item "{item_name}" archived successfully.',
                }
            )
        return jsonify(
            {
                "success": True,
                "message": (
                    f'Global item "{item_name}" deleted successfully. '
                    f"{connected_count} connected inventory items converted to organization-owned items."
                ),
            }
        )

    except Exception as exc:
        db.session.rollback()
        logging.error(
            "GLOBAL_ITEM_DELETE_FAILED: Error deleting global item %s: %s",
            item_id,
            exc,
        )
        return jsonify(
            {
                "success": False,
                "error": f"Failed to delete global item: {exc}",
            }
        )
