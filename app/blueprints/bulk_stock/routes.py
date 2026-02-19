"""Bulk stock check routes."""

import csv
import io

from flask import (
    Blueprint,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import login_required
from sqlalchemy.exc import SQLAlchemyError

from app.models import Recipe
from app.utils.permissions import require_permission
from app.utils.settings import is_feature_enabled

bulk_stock_bp = Blueprint("bulk_stock", __name__)


def _bulk_stock_check_enabled() -> bool:
    return is_feature_enabled("FEATURE_BULK_STOCK_CHECK")


@bulk_stock_bp.route("/bulk-check", methods=["GET", "POST"])
@login_required
@require_permission("recipes.plan_production")
def bulk_stock_check():
    try:
        if not _bulk_stock_check_enabled():
            flash("Bulk stock check is not enabled for your plan.", "warning")
            return redirect(url_for("app_routes.dashboard"))
        recipes = Recipe.scoped().all()
        summary = {}
        selected_ids = []

        if request.method == "POST":
            selected_ids = request.form.getlist("recipe_ids")
            if not selected_ids:
                flash("Please select at least one recipe")
                return redirect(url_for("bulk_stock.bulk_stock_check"))

            try:
                scale = float(request.form.get("scale", 1.0))
                if scale <= 0:
                    flash("Scale must be greater than 0")
                    return redirect(url_for("bulk_stock.bulk_stock_check"))
            except ValueError:
                flash("Invalid scale value")
                return redirect(url_for("bulk_stock.bulk_stock_check"))

            session["bulk_recipe_ids"] = selected_ids
            session["bulk_scale"] = scale

            from app.services.stock_check.core import UniversalStockCheckService

            uscs = UniversalStockCheckService()
            recipe_configs = [
                {"recipe_id": int(rid), "scale": scale} for rid in selected_ids
            ]
            bulk_results = uscs.check_bulk_recipes(recipe_configs)

            if bulk_results["success"]:
                # Aggregate results from USCS.
                ingredient_totals = {}

                for _rid, result in bulk_results["results"].items():
                    if result["success"]:
                        stock_data = result.get("stock_check", [])

                        for item in stock_data:
                            name = item.get("name", item.get("item_name", "Unknown"))
                            needed = item.get("needed", item.get("needed_quantity", 0))
                            unit = item.get("unit", item.get("needed_unit", "ml"))
                            available = item.get(
                                "available", item.get("available_quantity", 0)
                            )

                            key = (name, unit)
                            if key not in ingredient_totals:
                                ingredient_totals[key] = {
                                    "name": name,
                                    "unit": unit,
                                    "needed": 0,
                                    "available": available,
                                }
                            ingredient_totals[key]["needed"] += needed

                # Determine status for each ingredient.
                for item in ingredient_totals.values():
                    if item["available"] >= item["needed"]:
                        item["status"] = "OK"
                    elif item["available"] > 0:
                        item["status"] = "LOW"
                    else:
                        item["status"] = "NEEDED"

                summary = list(ingredient_totals.values())
                session["bulk_summary"] = summary
            else:
                flash("Bulk stock check failed", "error")

        return render_template(
            "bulk_stock_check.html", recipes=recipes, summary=summary
        )
    except Exception as exc:
        flash(f"Error checking stock: {str(exc)}")
        return redirect(url_for("bulk_stock.bulk_stock_check"))


@bulk_stock_bp.route("/bulk-check/csv")
@login_required
@require_permission("recipes.plan_production")
def export_shopping_list_csv():
    try:
        if not _bulk_stock_check_enabled():
            flash("Bulk stock check is not enabled for your plan.", "warning")
            return redirect(url_for("app_routes.dashboard"))
        summary = session.get("bulk_summary", [])
        if not summary:
            flash("No stock check results available")
            return redirect(url_for("bulk_stock.bulk_stock_check"))

        missing = [item for item in summary if item["status"] in ["LOW", "NEEDED"]]
        if not missing:
            flash("No items need restocking")
            return redirect(url_for("bulk_stock.bulk_stock_check"))

        string_io = io.StringIO()
        csv_writer = csv.writer(string_io)
        csv_writer.writerow(["Ingredient", "Needed", "Available", "Unit", "Status"])
        for item in missing:
            csv_writer.writerow(
                [
                    item["name"],
                    item["needed"],
                    item["available"],
                    item["unit"],
                    item["status"],
                ]
            )

        output = make_response(string_io.getvalue())
        output.headers["Content-Disposition"] = "attachment; filename=shopping_list.csv"
        output.headers["Content-type"] = "text/csv"
        return output
    except ValueError as exc:
        flash(f"Bulk stock processing failed: {exc}", "warning")
        return redirect(request.referrer or url_for("bulk_stock.bulk_stock_check"))
    except SQLAlchemyError:
        flash("Database error exporting CSV.", "danger")
        return redirect(url_for("bulk_stock.bulk_stock_check"))
