import os


def test_stripe_env_config_present(app):
    with app.app_context():
        # In tests, conftest sets secret/webhook; publishable is optional for server flows
        assert os.environ.get('STRIPE_SECRET_KEY') or app.config.get('STRIPE_SECRET_KEY')
        assert os.environ.get('STRIPE_WEBHOOK_SECRET') or app.config.get('STRIPE_WEBHOOK_SECRET')

