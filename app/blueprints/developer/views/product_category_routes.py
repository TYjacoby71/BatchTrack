from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import ProductCategory, Product, Recipe

from ..routes import developer_bp


@developer_bp.route("/product-categories")
@login_required
def product_categories():
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    return render_template("developer/categories/list.html", categories=categories)


@developer_bp.route("/product-categories/new", methods=["GET", "POST"])
@login_required
def create_product_category():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        is_typically_portioned = request.form.get("is_typically_portioned") == "on"
        sku_name_template = (request.form.get("sku_name_template") or "").strip() or None
        if not name:
            flash("Name is required", "error")
            return redirect(url_for("developer.create_product_category"))
        exists = ProductCategory.query.filter(ProductCategory.name.ilike(name)).first()
        if exists:
            flash("Category name already exists", "error")
            return redirect(url_for("developer.create_product_category"))
        cat = ProductCategory(
            name=name,
            is_typically_portioned=is_typically_portioned,
            sku_name_template=sku_name_template,
        )
        db.session.add(cat)
        db.session.commit()
        flash("Product category created", "success")
        return redirect(url_for("developer.product_categories"))
    return render_template("developer/categories/new.html")


@developer_bp.route("/product-categories/<int:cat_id>/edit", methods=["GET", "POST"])
@login_required
def edit_product_category(cat_id):
    cat = ProductCategory.query.get_or_404(cat_id)
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        is_typically_portioned = request.form.get("is_typically_portioned") == "on"
        sku_name_template = (request.form.get("sku_name_template") or "").strip() or None
        if not name:
            flash("Name is required", "error")
            return redirect(url_for("developer.edit_product_category", cat_id=cat_id))
        conflict = (
            ProductCategory.query.filter(ProductCategory.id != cat_id)
            .filter(ProductCategory.name.ilike(name))
            .first()
        )
        if conflict:
            flash("Another category with that name exists", "error")
            return redirect(url_for("developer.edit_product_category", cat_id=cat_id))
        cat.name = name
        cat.is_typically_portioned = is_typically_portioned
        cat.sku_name_template = sku_name_template
        db.session.commit()
        flash("Product category updated", "success")
        return redirect(url_for("developer.product_categories"))
    return render_template("developer/categories/edit.html", category=cat)


@developer_bp.route("/product-categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def delete_product_category(cat_id):
    cat = ProductCategory.query.get_or_404(cat_id)
    in_use = (
        db.session.query(Product).filter_by(category_id=cat.id).first()
        or db.session.query(Recipe).filter_by(category_id=cat.id).first()
    )
    if in_use:
        flash("Cannot delete category that is used by products or recipes", "error")
        return redirect(url_for("developer.product_categories"))
    db.session.delete(cat)
    db.session.commit()
    flash("Product category deleted", "success")
    return redirect(url_for("developer.product_categories"))
