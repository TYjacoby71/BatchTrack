"""Module documentation.

Synopsis:
This module defines route handlers and helpers for `app/blueprints/developer/views/product_category_routes.py`.

Glossary:
- Route handler: A Flask view function bound to an endpoint.
- Helper unit: A module-level function or class supporting route/service flow.
"""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from app.services.developer.product_category_service import ProductCategoryService

from ..decorators import require_developer_permission
from ..routes import developer_bp


# --- Product Categories ---
# Purpose: Define the top-level behavior of `product_categories` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/product-categories")
@require_developer_permission("dev.system_admin")
def product_categories():
    categories = ProductCategoryService.list_categories()
    return render_template("developer/categories/list.html", categories=categories)


# --- Create Product Category ---
# Purpose: Define the top-level behavior of `create_product_category` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/product-categories/new", methods=["GET", "POST"])
@require_developer_permission("dev.system_admin")
def create_product_category():
    if request.method == "POST":
        name, is_typically_portioned, sku_name_template = (
            ProductCategoryService.normalize_form_inputs(
                name=request.form.get("name"),
                is_typically_portioned_raw=request.form.get("is_typically_portioned"),
                sku_name_template=request.form.get("sku_name_template"),
            )
        )
        name_ok, name_error = ProductCategoryService.validate_name_required(name)
        if not name_ok:
            flash(name_error, "error")
            return redirect(url_for("developer.create_product_category"))

        exists = ProductCategoryService.find_conflict(name=name)
        if exists:
            flash("Category name already exists", "error")
            return redirect(url_for("developer.create_product_category"))

        ProductCategoryService.create_category(
            name=name,
            is_typically_portioned=is_typically_portioned,
            sku_name_template=sku_name_template,
        )
        flash("Product category created", "success")
        return redirect(url_for("developer.product_categories"))
    return render_template("developer/categories/new.html")


# --- Edit Product Category ---
# Purpose: Define the top-level behavior of `edit_product_category` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/product-categories/<int:cat_id>/edit", methods=["GET", "POST"])
@require_developer_permission("dev.system_admin")
def edit_product_category(cat_id):
    cat = ProductCategoryService.get_category_or_404(cat_id)
    if request.method == "POST":
        name, is_typically_portioned, sku_name_template = (
            ProductCategoryService.normalize_form_inputs(
                name=request.form.get("name"),
                is_typically_portioned_raw=request.form.get("is_typically_portioned"),
                sku_name_template=request.form.get("sku_name_template"),
            )
        )
        name_ok, name_error = ProductCategoryService.validate_name_required(name)
        if not name_ok:
            flash(name_error, "error")
            return redirect(url_for("developer.edit_product_category", cat_id=cat_id))

        conflict = ProductCategoryService.find_conflict(
            name=name,
            exclude_category_id=cat_id,
        )
        if conflict:
            flash("Another category with that name exists", "error")
            return redirect(url_for("developer.edit_product_category", cat_id=cat_id))

        ProductCategoryService.update_category(
            cat,
            name=name,
            is_typically_portioned=is_typically_portioned,
            sku_name_template=sku_name_template,
        )
        flash("Product category updated", "success")
        return redirect(url_for("developer.product_categories"))
    return render_template("developer/categories/edit.html", category=cat)


# --- Delete Product Category ---
# Purpose: Define the top-level behavior of `delete_product_category` in this module.
# Inputs: Function/class parameters and request/runtime context used by this unit.
# Outputs: Response payloads, control-flow effects, or reusable definitions for callers.
@developer_bp.route("/product-categories/<int:cat_id>/delete", methods=["POST"])
@require_developer_permission("dev.system_admin")
def delete_product_category(cat_id):
    cat = ProductCategoryService.get_category_or_404(cat_id)
    in_use = ProductCategoryService.is_category_in_use(cat)
    if in_use:
        flash("Cannot delete category that is used by products or recipes", "error")
        return redirect(url_for("developer.product_categories"))
    ProductCategoryService.delete_category(cat)
    flash("Product category deleted", "success")
    return redirect(url_for("developer.product_categories"))
