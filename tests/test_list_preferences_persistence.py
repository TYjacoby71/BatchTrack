"""DB-backed list preference persistence behavior."""

from app.extensions import db
from app.models import User, UserPreferences


def _login(client, user_id: int) -> None:
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def test_user_preferences_scoped_merge_and_replace(app):
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None

        prefs = UserPreferences.get_for_user(user.id)
        assert prefs is not None

        prefs.set_list_preferences(
            "inventory_list",
            {"ingredients_name_filter": "wax"},
            merge=True,
        )
        db.session.commit()

        prefs = UserPreferences.get_for_user(user.id)
        assert prefs.get_list_preferences("inventory_list") == {
            "ingredients_name_filter": "wax"
        }

        prefs.set_list_preferences(
            "inventory_list",
            {"ingredients_archived_filter": "false"},
            merge=True,
        )
        db.session.commit()

        prefs = UserPreferences.get_for_user(user.id)
        assert prefs.get_list_preferences("inventory_list") == {
            "ingredients_name_filter": "wax",
            "ingredients_archived_filter": "false",
        }

        prefs.set_list_preferences(
            "inventory_list",
            {"ingredients_sort_filter": "name_asc"},
            merge=False,
        )
        db.session.commit()

        prefs = UserPreferences.get_for_user(user.id)
        assert prefs.get_list_preferences("inventory_list") == {
            "ingredients_sort_filter": "name_asc"
        }


def test_settings_list_preferences_api_round_trip(client, app):
    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        assert user is not None
        user_id = user.id

    _login(client, user_id)

    payload = {
        "mode": "replace",
        "values": {
            "ingredients_name_filter": "lavender",
            "ingredients_archived_filter": "true",
        },
    }
    save_response = client.post("/settings/api/list-preferences/inventory_list", json=payload)
    assert save_response.status_code == 200
    save_data = save_response.get_json() or {}
    assert save_data.get("success") is True
    assert save_data.get("scope") == "inventory_list"

    fetch_response = client.get("/settings/api/list-preferences/inventory_list")
    assert fetch_response.status_code == 200
    fetch_data = fetch_response.get_json() or {}
    assert fetch_data.get("success") is True
    assert fetch_data.get("values", {}).get("ingredients_name_filter") == "lavender"
    assert fetch_data.get("values", {}).get("ingredients_archived_filter") == "true"
