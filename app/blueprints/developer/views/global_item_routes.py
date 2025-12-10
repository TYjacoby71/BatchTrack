from __future__ import annotations

import json
import logging

from collections import OrderedDict

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
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import GlobalItem
from app.models.category import IngredientCategory
from app.models.ingredient_reference import (
    ApplicationTag,
    FunctionTag,
    IngredientCategoryTag,
    IngredientDefinition,
    PhysicalForm,
)
from app.utils.seo import slugify_value

from ..routes import developer_bp


class FormValidationError(Exception):
    """Raised when a submitted form payload cannot be processed."""


def _generate_unique_slug(model, seed: str) -> str:
    base_slug = slugify_value(seed or "item")
    candidate = base_slug
    counter = 2
    while model.query.filter_by(slug=candidate).first():
        candidate = f"{base_slug}-{counter}"
        counter += 1
    return candidate


def _parse_csv_field(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    seen = set()
    values = []
    for part in raw_value.split(","):
        name = part.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        values.append(name)
    return values


def _get_or_create_tags(model, names: list[str]):
    tags = []
    for name in names:
        slug_candidate = slugify_value(name, default="tag")
        existing = model.query.filter(
            or_(model.slug == slug_candidate, model.name.ilike(name))
        ).first()
        if existing:
            tags.append(existing)
            continue
        unique_slug = _generate_unique_slug(model, slug_candidate)
        tag = model(name=name, slug=unique_slug)
        db.session.add(tag)
        tags.append(tag)
    return tags


def _apply_tag_collection(item, attr_name: str, model, raw_value: str | None):
    names = _parse_csv_field(raw_value)
    relationship = getattr(item, attr_name)
    if not names:
        relationship.clear()
        return
    setattr(item, attr_name, _get_or_create_tags(model, names))


def _determine_ingredient_layer(form_data, ingredient_category_id, *, current_ingredient=None):
    fallback_mode = "existing" if current_ingredient else "new"
    mode = (form_data.get("ingredient_mode") or fallback_mode).lower()

    if mode == "existing":
        existing_id = form_data.get("existing_ingredient_id") or (
            current_ingredient.id if current_ingredient else None
        )
        if not existing_id:
            raise FormValidationError("Select an ingredient definition or create a new one.")
        try:
            ingredient_id = int(existing_id)
        except (TypeError, ValueError):
            raise FormValidationError("Invalid ingredient definition selected.")

        ingredient = IngredientDefinition.query.get(ingredient_id)
        if not ingredient:
            raise FormValidationError("Ingredient definition not found.")

        if ingredient_category_id and ingredient.ingredient_category_id != ingredient_category_id:
            ingredient.ingredient_category_id = ingredient_category_id

        return ingredient, True

    name = (form_data.get("new_ingredient_name") or "").strip()
    if not name:
        raise FormValidationError("Ingredient name is required when defining a new ingredient.")

    slug_field = (form_data.get("new_ingredient_slug") or "").strip()
    slug = _generate_unique_slug(IngredientDefinition, slug_field or name)

    ingredient = IngredientDefinition(
        name=name,
        slug=slug,
        inci_name=(form_data.get("new_ingredient_inci") or "").strip() or None,
        cas_number=(form_data.get("new_ingredient_cas") or "").strip() or None,
        description=(form_data.get("new_ingredient_description") or "").strip() or None,
        ingredient_category_id=ingredient_category_id,
        is_active=True,
    )
    return ingredient, False


def _determine_physical_form_layer(form_data, *, current_physical_form=None):
    fallback_mode = "existing" if current_physical_form else "new"
    mode = (form_data.get("physical_form_mode") or fallback_mode).lower()

    if mode == "existing":
        existing_id = form_data.get("existing_physical_form_id") or (
            current_physical_form.id if current_physical_form else None
        )
        if not existing_id:
            raise FormValidationError("Select a physical form or define a new one.")
        try:
            physical_form_id = int(existing_id)
        except (TypeError, ValueError):
            raise FormValidationError("Invalid physical form selected.")

        physical_form = PhysicalForm.query.get(physical_form_id)
        if not physical_form:
            raise FormValidationError("Physical form not found.")

        return physical_form, True

    name = (form_data.get("new_physical_form_name") or "").strip()
    if not name:
        raise FormValidationError("Physical form name is required when creating a new entry.")

    slug_field = (form_data.get("new_physical_form_slug") or "").strip()
    slug = _generate_unique_slug(PhysicalForm, slug_field or name)

    physical_form = PhysicalForm(name=name, slug=slug)
    return physical_form, False


def _format_capacity_value(value):
    if value is None:
        return ""
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return str(value).strip()
    if numeric.is_integer():
        return str(int(numeric))
    return f"{numeric:.2f}".rstrip("0").rstrip(".")


def _compose_container_name(form_data, *, existing_item=None):
    def pick(key):
        if form_data:
            candidate = (form_data.get(key) or "").strip()
            if candidate:
                return candidate
        if existing_item is not None:
            existing_value = getattr(existing_item, key, None)
            if existing_value:
                return str(existing_value).strip()
        return ""

    capacity = pick("capacity")
    capacity_unit = pick("capacity_unit")
    material = pick("container_material")
    c_type = pick("container_type")
    style = pick("container_style")
    color = pick("container_color")

    capacity_label = ""
    if capacity:
        capacity_label = _format_capacity_value(capacity)
        if capacity_unit:
            capacity_label = f"{capacity_label} {capacity_unit}".strip()

    descriptors = " ".join(part for part in [material, c_type, style] if part).strip()
    parts = [capacity_label, descriptors, color]
    name = ", ".join(part for part in parts if part)
    return name.strip()


def _compose_ingredient_name(ingredient, physical_form, *, fallback=None):
    if ingredient and physical_form:
        return f"{ingredient.name}, {physical_form.name}"
    if ingredient:
        return ingredient.name
    return fallback


def _generate_item_name(item_type, form_data, *, ingredient=None, physical_form=None, existing_item=None):
    if item_type == "ingredient":
        name = _compose_ingredient_name(ingredient, physical_form, fallback=form_data.get("name") if form_data else None)
        return (name or "").strip()
    if item_type == "container":
        name = _compose_container_name(form_data, existing_item=existing_item)
        if not name and existing_item:
            return existing_item.name
        return name
    if form_data:
        candidate = (form_data.get("name") or "").strip()
        if candidate:
            return candidate
    if existing_item:
        return existing_item.name
    return ""


@developer_bp.route("/global-items")
@login_required
def global_items_admin():
    """Developer admin page for managing Global Items."""
    scope = (request.args.get("scope", "ingredient") or "ingredient").lower()
    valid_scopes = ["ingredient", "container", "packaging", "consumable"]
    if scope not in valid_scopes:
        scope = "ingredient"

    category_filter = request.args.get("category", "").strip() if scope == "ingredient" else ""
    search_query = request.args.get("search", "").strip()
    page = request.args.get("page", type=int) or 1
    if page < 1:
        page = 1
    per_page_options = [10, 50, 100]
    per_page = request.args.get("page_size", type=int) or per_page_options[0]
    if per_page not in per_page_options:
        per_page = per_page_options[0]

    query = GlobalItem.query.filter(
        GlobalItem.is_archived != True,
        GlobalItem.item_type == scope,
    )

    if scope == "ingredient" and category_filter:
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

    if scope == "ingredient":
        query = query.options(joinedload(GlobalItem.ingredient), joinedload(GlobalItem.physical_form))
        order_by = [GlobalItem.ingredient_id.asc(), GlobalItem.name.asc()]
    else:
        order_by = [GlobalItem.name.asc()]

    pagination = query.order_by(*order_by).paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items

    grouped_items = []
    if scope == "ingredient":
        buckets = OrderedDict()
        for gi in items:
            key = gi.ingredient_id or f"item-{gi.id}"
            if key not in buckets:
                buckets[key] = {
                    "ingredient": gi.ingredient,
                    "items": [],
                }
            buckets[key]["items"].append(gi)
        grouped_items = list(buckets.values())

    try:
        categories = (
            db.session.query(IngredientCategory.name)
            .join(GlobalItem, GlobalItem.ingredient_category_id == IngredientCategory.id)
            .filter(
                IngredientCategory.organization_id == None,
                IngredientCategory.is_global_category == True,
                GlobalItem.item_type == "ingredient",
            )
            .distinct()
            .order_by(IngredientCategory.name)
            .all()
        )
        categories = [row[0] for row in categories if row[0]]
    except Exception:
        categories = [
            c.name
            for c in IngredientCategory.query.filter_by(
                organization_id=None, is_active=True, is_global_category=True
            )
            .order_by(IngredientCategory.name)
            .all()
        ]

    filter_params = {
        "scope": scope,
    }
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

    scope_labels = {
        "ingredient": "Ingredients",
        "container": "Containers",
        "packaging": "Packaging",
        "consumable": "Consumables",
    }

    base_query_params = {}
    if search_query:
        base_query_params["search"] = search_query
    if per_page != per_page_options[0]:
        base_query_params["page_size"] = per_page
    if category_filter and scope == "ingredient":
        base_query_params["category"] = category_filter

    return render_template(
        "developer/global_items.html",
        items=items,
        grouped_items=grouped_items,
        categories=categories,
        active_scope=scope,
        scope_labels=scope_labels,
        selected_category=category_filter,
        search_query=search_query,
        pagination=pagination,
        per_page=per_page,
        per_page_options=per_page_options,
        build_page_url=build_page_url,
        first_item_index=first_item_index,
        last_item_index=last_item_index,
        base_query_params=base_query_params,
        breadcrumb_items=[
            {"label": "Developer Dashboard", "url": url_for("developer.dashboard")},
            {"label": "Global Item Library"},
        ],
    )


@developer_bp.route("/global-items/<int:item_id>")
@login_required
def global_item_detail(item_id):
    item = GlobalItem.query.get_or_404(item_id)
    global_ingredient_categories = (
        IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True,
        )
        .order_by(IngredientCategory.name)
        .all()
    )
    physical_forms = PhysicalForm.query.order_by(PhysicalForm.name).all()
    selected_ingredient = item.ingredient
    selected_physical_form = item.physical_form
    existing_items = []
    if selected_ingredient:
        existing_items = (
            GlobalItem.query.filter(
                GlobalItem.ingredient_id == selected_ingredient.id,
                GlobalItem.is_archived != True,
            )
            .order_by(GlobalItem.name.asc())
            .all()
        )

    return render_template(
        "developer/global_item_detail.html",
        item=item,
        global_ingredient_categories=global_ingredient_categories,
        physical_forms=physical_forms,
        selected_ingredient=selected_ingredient,
        selected_physical_form=selected_physical_form,
        existing_items=existing_items,
        form_data={},
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
    form_data = request.form
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

    submitted_name = (form_data.get("name") or "").strip()
    new_item_type = form_data.get("item_type", item.item_type)
    item.item_type = new_item_type
    item.default_unit = form_data.get("default_unit", item.default_unit)
    density = form_data.get("density")
    item.density = float(density) if density not in (None, "") else None
    capacity = form_data.get("capacity")
    item.capacity = float(capacity) if capacity not in (None, "") else None
    item.capacity_unit = form_data.get("capacity_unit", item.capacity_unit)
    try:
        item.container_material = (form_data.get("container_material") or "").strip() or None
        item.container_type = (form_data.get("container_type") or "").strip() or None
        item.container_style = (form_data.get("container_style") or "").strip() or None
        item.container_color = (form_data.get("container_color") or "").strip() or None
    except Exception:
        pass
    item.default_is_perishable = form_data.get("default_is_perishable") == "on"
    shelf_life = form_data.get("recommended_shelf_life_days")
    item.recommended_shelf_life_days = int(shelf_life) if shelf_life not in (None, "") else None

    aliases = form_data.get("aliases")
    if aliases is not None:
        item.aliases = [n.strip() for n in aliases.split(",") if n.strip()]

    item.recommended_fragrance_load_pct = form_data.get("recommended_fragrance_load_pct") or None
    item.is_active_ingredient = form_data.get("is_active_ingredient") == "on"
    item.inci_name = form_data.get("inci_name") or None

    protein = form_data.get("protein_content_pct")
    item.protein_content_pct = float(protein) if protein not in (None, "") else None

    brewing_color = form_data.get("brewing_color_srm")
    item.brewing_color_srm = float(brewing_color) if brewing_color not in (None, "") else None

    brewing_potential = form_data.get("brewing_potential_sg")
    item.brewing_potential_sg = float(brewing_potential) if brewing_potential not in (None, "") else None

    brewing_dp = form_data.get("brewing_diastatic_power_lintner")
    item.brewing_diastatic_power_lintner = float(brewing_dp) if brewing_dp not in (None, "") else None

    fatty_acid_profile_raw = form_data.get("fatty_acid_profile")
    if fatty_acid_profile_raw is not None:
        fatty_acid_profile_raw = fatty_acid_profile_raw.strip()
        if fatty_acid_profile_raw:
            try:
                item.fatty_acid_profile = json.loads(fatty_acid_profile_raw)
            except json.JSONDecodeError:
                flash("Invalid JSON for fatty acid profile. Please provide valid JSON.", "error")
        else:
            item.fatty_acid_profile = None

    certifications_raw = form_data.get("certifications")
    if certifications_raw is not None:
        certifications = [c.strip() for c in certifications_raw.split(",") if c.strip()]
        item.certifications = certifications or None

    ingredient_category_id_value = None
    ingredient_category_id = form_data.get("ingredient_category_id", "").strip()
    if ingredient_category_id:
        if ingredient_category_id.isdigit():
            category = IngredientCategory.query.filter_by(
                id=int(ingredient_category_id),
                organization_id=None,
                is_global_category=True,
            ).first()
            if not category:
                db.session.rollback()
                flash(f'Ingredient category ID "{ingredient_category_id}" not found or invalid.', "error")
                return redirect(url_for("developer.global_item_detail", item_id=item.id))
            ingredient_category_id_value = category.id
        else:
            db.session.rollback()
            flash(f"Invalid Ingredient Category ID format: '{ingredient_category_id}'", "error")
            return redirect(url_for("developer.global_item_detail", item_id=item.id))
    item.ingredient_category_id = ingredient_category_id_value

    if new_item_type == "ingredient":
        try:
            ingredient_obj, _ = _determine_ingredient_layer(
                form_data, ingredient_category_id_value, current_ingredient=item.ingredient
            )
            physical_form_obj, _ = _determine_physical_form_layer(
                form_data, current_physical_form=item.physical_form
            )
            item.ingredient = ingredient_obj
            item.physical_form = physical_form_obj
            _apply_tag_collection(item, "functions", FunctionTag, form_data.get("function_tags"))
            _apply_tag_collection(item, "applications", ApplicationTag, form_data.get("application_tags"))
            _apply_tag_collection(item, "category_tags", IngredientCategoryTag, form_data.get("category_tags"))
            name_candidate = _generate_item_name(
                new_item_type,
                form_data,
                ingredient=ingredient_obj,
                physical_form=physical_form_obj,
                existing_item=item,
            )
            if name_candidate:
                item.name = name_candidate
        except FormValidationError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return redirect(url_for("developer.global_item_detail", item_id=item.id))
    else:
        item.ingredient = None
        item.physical_form = None
        item.functions.clear()
        item.applications.clear()
        item.category_tags.clear()
        if new_item_type == "container":
            name_candidate = _generate_item_name(new_item_type, form_data, existing_item=item)
            if name_candidate:
                item.name = name_candidate
        elif submitted_name:
            item.name = submitted_name

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

    def render_form(form_data=None, selected_ingredient=None, selected_physical_form=None):
        global_ingredient_categories = (
            IngredientCategory.query.filter_by(
                organization_id=None,
                is_active=True,
                is_global_category=True,
            )
            .order_by(IngredientCategory.name)
            .all()
        )
        physical_forms = PhysicalForm.query.order_by(PhysicalForm.name).all()

        ingredient_id = (
            selected_ingredient.id if selected_ingredient else request.args.get("ingredient_id")
        )
        physical_form_id = (
            selected_physical_form.id if selected_physical_form else request.args.get("physical_form_id")
        )

        if not selected_ingredient and ingredient_id:
            try:
                selected_ingredient = IngredientDefinition.query.get(int(ingredient_id))
            except (ValueError, TypeError):
                selected_ingredient = None

        existing_items = []
        if selected_ingredient:
            existing_items = (
                GlobalItem.query.filter(
                    GlobalItem.ingredient_id == selected_ingredient.id,
                    GlobalItem.is_archived != True,
                )
                .order_by(GlobalItem.name.asc())
                .all()
            )

        if not selected_physical_form and physical_form_id:
            try:
                selected_physical_form = PhysicalForm.query.get(int(physical_form_id))
            except (ValueError, TypeError):
                selected_physical_form = None

        return render_template(
            "developer/create_global_item.html",
            global_ingredient_categories=global_ingredient_categories,
            physical_forms=physical_forms,
            selected_ingredient=selected_ingredient,
            selected_physical_form=selected_physical_form,
            existing_items=existing_items,
            form_data=form_data or {},
        )

    if request.method == "POST":
        form_data = request.form
        selected_ingredient_for_render = None
        selected_physical_form_for_render = None

        def _error_response(message: str):
            db.session.rollback()
            flash(message, "error")
            return render_form(
                form_data,
                selected_ingredient=selected_ingredient_for_render,
                selected_physical_form=selected_physical_form_for_render,
            )

        try:
            name = (form_data.get("name") or "").strip()
            item_type = (form_data.get("item_type") or "ingredient").strip() or "ingredient"
            default_unit = form_data.get("default_unit", "").strip() or None
            ingredient_category_id_str = form_data.get("ingredient_category_id", "").strip() or None

            if not name:
                return _error_response("Name is required")

            ingredient_category_id = None
            if ingredient_category_id_str:
                if ingredient_category_id_str.isdigit():
                    category = IngredientCategory.query.filter_by(
                        id=int(ingredient_category_id_str),
                        organization_id=None,
                        is_global_category=True,
                    ).first()
                    if category:
                        ingredient_category_id = category.id
                    else:
                        return _error_response(
                            f'Ingredient category ID "{ingredient_category_id_str}" not found or invalid.'
                        )
                else:
                    return _error_response(
                        f"Invalid Ingredient Category ID format: '{ingredient_category_id_str}'"
                    )

            existing = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
            if existing and not existing.is_archived:
                return _error_response(f'Global item "{name}" of type "{item_type}" already exists')

            ingredient_obj = None
            physical_form_obj = None
            if item_type == "ingredient":
                ingredient_obj, ingredient_is_existing = _determine_ingredient_layer(
                    form_data, ingredient_category_id
                )
                if ingredient_is_existing:
                    selected_ingredient_for_render = ingredient_obj
                physical_form_obj, physical_is_existing = _determine_physical_form_layer(form_data)
                if physical_is_existing:
                    selected_physical_form_for_render = physical_form_obj
                name = _generate_item_name(
                    item_type,
                    form_data,
                    ingredient=ingredient_obj,
                    physical_form=physical_form_obj,
                )
            elif item_type == "container":
                name = _generate_item_name(item_type, form_data)

            if not name:
                return _error_response("Name is required")

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
                    return _error_response("Invalid density value")

            capacity = form_data.get("capacity")
            if capacity:
                try:
                    new_item.capacity = float(capacity)
                except ValueError:
                    return _error_response("Invalid capacity value")

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
                    return _error_response("Invalid shelf life value")

            new_item.recommended_fragrance_load_pct = (
                form_data.get("recommended_fragrance_load_pct", "").strip() or None
            )
            new_item.inci_name = form_data.get("inci_name", "").strip() or None

            protein_content = form_data.get("protein_content_pct", "").strip()
            if protein_content:
                try:
                    new_item.protein_content_pct = float(protein_content)
                except ValueError:
                    return _error_response("Invalid protein content percentage")

            brewing_color = form_data.get("brewing_color_srm", "").strip()
            if brewing_color:
                try:
                    new_item.brewing_color_srm = float(brewing_color)
                except ValueError:
                    return _error_response("Invalid brewing SRM value")

            brewing_potential = form_data.get("brewing_potential_sg", "").strip()
            if brewing_potential:
                try:
                    new_item.brewing_potential_sg = float(brewing_potential)
                except ValueError:
                    return _error_response("Invalid brewing potential SG value")

            brewing_dp = form_data.get("brewing_diastatic_power_lintner", "").strip()
            if brewing_dp:
                try:
                    new_item.brewing_diastatic_power_lintner = float(brewing_dp)
                except ValueError:
                    return _error_response("Invalid brewing diastatic power value")

            fatty_acid_profile_raw = form_data.get("fatty_acid_profile", "").strip()
            if fatty_acid_profile_raw:
                try:
                    new_item.fatty_acid_profile = json.loads(fatty_acid_profile_raw)
                except json.JSONDecodeError:
                    return _error_response("Fatty acid profile must be valid JSON.")

            certifications_raw = form_data.get("certifications", "").strip()
            if certifications_raw:
                new_item.certifications = [c.strip() for c in certifications_raw.split(",") if c.strip()]

            aliases_raw = form_data.get("aliases", "").strip()
            if aliases_raw:
                new_item.aliases = [n.strip() for n in aliases_raw.split(",") if n.strip()]

            if item_type == "ingredient":
                new_item.ingredient = ingredient_obj
                new_item.physical_form = physical_form_obj
                _apply_tag_collection(new_item, "functions", FunctionTag, form_data.get("function_tags"))
                _apply_tag_collection(
                    new_item, "applications", ApplicationTag, form_data.get("application_tags")
                )
                _apply_tag_collection(
                    new_item, "category_tags", IngredientCategoryTag, form_data.get("category_tags")
                )
            else:
                new_item.ingredient = None
                new_item.physical_form = None

            db.session.add(new_item)
            db.session.commit()

            try:
                from app.services.event_emitter import EventEmitter

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
        except FormValidationError as exc:
            db.session.rollback()
            flash(str(exc), "error")
            return render_form(
                form_data,
                selected_ingredient=selected_ingredient_for_render,
                selected_physical_form=selected_physical_form_for_render,
            )
        except Exception as exc:
            db.session.rollback()
            flash(f"Error creating global item: {exc}", "error")
            return render_form(
                form_data,
                selected_ingredient=selected_ingredient_for_render,
                selected_physical_form=selected_physical_form_for_render,
            )

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
