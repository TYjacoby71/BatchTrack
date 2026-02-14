from app.extensions import db
from app.models import Batch, BatchTimer, Recipe
from app.models.models import User
from app.utils.timezone_utils import TimezoneUtils


def _login(client, user_id: int) -> None:
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def test_view_batch_in_progress_renders_with_active_timer(app, client):
    app.config["SKIP_PERMISSIONS"] = True

    with app.app_context():
        user = User.query.first()
        assert user is not None

        recipe = Recipe(
            name="Timer Render Recipe",
            predicted_yield=10.0,
            predicted_yield_unit="oz",
            category_id=1,
            organization_id=user.organization_id,
        )
        db.session.add(recipe)
        db.session.flush()

        batch = Batch(
            recipe_id=recipe.id,
            batch_type="ingredient",
            projected_yield=10.0,
            projected_yield_unit="oz",
            status="in_progress",
            organization_id=user.organization_id,
            created_by=user.id,
            started_at=TimezoneUtils.utc_now(),
        )
        db.session.add(batch)
        db.session.flush()

        timer = BatchTimer(
            batch_id=batch.id,
            name="Regression Timer",
            duration_seconds=600,
            start_time=TimezoneUtils.utc_now().replace(tzinfo=None),
            status="active",
            organization_id=user.organization_id,
            created_by=user.id,
        )
        db.session.add(timer)
        db.session.commit()
        user_id = user.id
        batch_id = batch.id

    _login(client, user_id)
    response = client.get(f"/batches/in-progress/{batch_id}", follow_redirects=False)

    assert response.status_code == 200
    assert b"Regression Timer" in response.data
    assert b"Time Left" in response.data


def test_timer_list_template_uses_safe_start_time_parsing(app, client):
    app.config["SKIP_PERMISSIONS"] = True

    with app.app_context():
        user = User.query.first()
        assert user is not None
        user_id = user.id

    _login(client, user_id)
    response = client.get("/timers/list_timers", follow_redirects=False)

    assert response.status_code == 200
    assert b"parseTimerStart(timer)" in response.data
    assert b"new Date(timer.start_time + 'Z')" not in response.data
