from __future__ import annotations

import os
from uuid import uuid4
from typing import Any, Dict, Optional, Tuple

from flask import current_app, url_for
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


class RecipeMarketplaceService:
    """Encapsulate marketplace form parsing and file-handling logic for recipes."""

    _ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

    @classmethod
    def extract_submission(cls, form, files=None, *, existing=None) -> Tuple[bool, Dict[str, Dict[str, Any]] | str]:
        """
        Normalize marketplace-related form data and optional cover image uploads.

        Returns:
            (success, payload|error_message)
        """
        try:
            marketplace_payload = cls._parse_marketplace_fields(form, existing=existing)
            cover_payload = cls._parse_cover_fields(form, files, existing=existing)
            return True, {"marketplace": marketplace_payload, "cover": cover_payload}
        except ValueError as exc:
            return False, str(exc)

    @classmethod
    def _parse_marketplace_fields(cls, form, *, existing=None) -> Dict[str, Any]:
        def _get(name: str, *, strip: bool = True):
            if name not in form:
                return None
            value = form.get(name)
            if strip and isinstance(value, str):
                value = value.strip()
            return value

        scope_value = _get("sharing_scope")
        if scope_value is None and existing is not None:
            scope_value = getattr(existing, "sharing_scope", None)
        scope_value = (scope_value or "private").lower()
        if scope_value not in {"public", "private"}:
            scope_value = "private"
        is_public = scope_value == "public"
        if existing is not None and "sharing_scope" not in form:
            is_public = getattr(existing, "is_public", False)

        sale_mode = (_get("sale_mode") or "").lower()
        if sale_mode not in {"free", "sale"}:
            sale_mode = "sale" if getattr(existing, "is_for_sale", False) else "free"
        is_for_sale = is_public and sale_mode == "sale"

        sale_price = _get("sale_price")
        if sale_price is None and existing is not None and "sale_mode" not in form and "sale_price" not in form:
            sale_price = getattr(existing, "sale_price", None)
        if isinstance(sale_price, str):
            sale_price = sale_price.strip()
        if not is_for_sale:
            sale_price = None
        elif sale_price in ("", None):
            sale_price = None

        product_group_id = None
        if "product_group_id" in form:
            product_group_id = cls._safe_int(form.get("product_group_id"))
        elif existing is not None:
            product_group_id = getattr(existing, "product_group_id", None)

        product_store_url = _get("product_store_url")
        if product_store_url is None and existing is not None and "product_store_url" not in form:
            product_store_url = getattr(existing, "product_store_url", None)
        if isinstance(product_store_url, str):
            product_store_url = product_store_url or None

        marketplace_notes = _get("marketplace_notes")
        if marketplace_notes is None and existing is not None and "marketplace_notes" not in form:
            marketplace_notes = getattr(existing, "marketplace_notes", None)

        public_description = _get("public_description")
        if public_description is None and existing is not None and "public_description" not in form:
            public_description = getattr(existing, "public_description", None)

        skin_opt_value = _get("skin_opt_in", strip=False)
        if skin_opt_value is None and existing is not None and "skin_opt_in" not in form:
            skin_opt = getattr(existing, "skin_opt_in", True)
        else:
            skin_opt = str(skin_opt_value).lower() == "true" if skin_opt_value is not None else True

        payload = {
            "product_group_id": product_group_id,
            "sharing_scope": scope_value,
            "is_public": is_public,
            "is_for_sale": is_for_sale,
            "sale_price": sale_price,
            "product_store_url": product_store_url,
            "marketplace_notes": marketplace_notes,
            "public_description": public_description,
            "skin_opt_in": skin_opt,
        }
        return payload

    @classmethod
    def _parse_cover_fields(cls, form, files, *, existing=None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        cover_file: Optional[FileStorage] = None
        if files:
            cover_file = files.get("cover_image")

        remove_cover_flag = str(form.get("remove_cover_image", "")).lower() == "true"
        if cover_file and getattr(cover_file, "filename", ""):
            path, url = cls._store_cover_image(cover_file)
            payload["cover_image_path"] = path
            payload["cover_image_url"] = url
            payload["remove_cover_image"] = False
        elif remove_cover_flag:
            payload["remove_cover_image"] = True

        return payload

    @classmethod
    def _store_cover_image(cls, file_storage: FileStorage) -> Tuple[str, str]:
        filename = secure_filename(file_storage.filename or "")
        if not filename:
            raise ValueError("Please select an image file to upload.")
        ext = filename.rsplit(".", 1)[-1].lower()
        if ext not in cls._ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError("Unsupported image type. Use PNG, JPG, GIF, or WEBP.")

        upload_root = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
            current_app.root_path, "static", "product_images"
        )
        target_dir = os.path.join(upload_root, "recipes")
        os.makedirs(target_dir, exist_ok=True)

        generated = f"{uuid4().hex}.{ext}"
        full_path = os.path.join(target_dir, generated)
        file_storage.save(full_path)

        relative_path = os.path.relpath(full_path, current_app.static_folder).replace("\\", "/")
        cover_url = url_for("static", filename=relative_path)
        return relative_path, cover_url

    @staticmethod
    def _safe_int(value: Any) -> Optional[int]:
        try:
            return int(value) if value not in (None, "", []) else None
        except (TypeError, ValueError):
            return None