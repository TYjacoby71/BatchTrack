from types import SimpleNamespace

from app.extensions import db
from app.models.pending_signup import PendingSignup
from app.models.subscription_tier import SubscriptionTier
from app.models.models import Organization, User
from app.services.billing_service import BillingService


class _DummySession:
    def __init__(self, session_id: str, url: str = 'https://stripe.test/checkout'):
        self.id = session_id
        self.url = url


def _make_fake_checkout_session(pending_id: int, customer):
    return SimpleNamespace(
        id=f'cs_test_{pending_id}',
        metadata={'pending_signup_id': str(pending_id)},
        customer_details={
            'email': customer.email,
            'phone': '555-0100',
            'name': f'{customer.first_name} {customer.last_name}',
        },
        customer=customer,
        custom_fields=[
            {'key': 'workspace_name', 'text': {'value': 'Solo Labs'}},
            {'key': 'first_name', 'text': {'value': customer.first_name}},
            {'key': 'last_name', 'text': {'value': customer.last_name}},
        ],
        client_reference_id=str(pending_id),
    )


def test_signup_flow_creates_org_and_user(app, client, monkeypatch):
    with app.app_context():
        solo = SubscriptionTier(
            name='Solo Plan',
            user_limit=1,
            billing_provider='stripe',
            is_customer_facing=True,
            stripe_lookup_key='price_batchtrack_solo',
        )
        db.session.add(solo)
        db.session.commit()

        def fake_checkout(tier_obj, *, customer_email, success_url, cancel_url, metadata,
                          client_reference_id=None, phone_required=True,
                          allow_promo=True, existing_customer_id=None):
            assert tier_obj.id == solo.id
            assert customer_email == 'solo@applicant.com'
            assert success_url.endswith('{CHECKOUT_SESSION_ID}')
            assert metadata['tier_id'] == str(solo.id)
            return _DummySession(f'cs_test_{tier_obj.id}')

        monkeypatch.setattr(BillingService, 'create_checkout_session_for_tier', fake_checkout)

        response = client.post(
            '/auth/signup',
            data={
                'selected_tier': str(solo.id),
                'contact_email': 'solo@applicant.com',
                'contact_phone': '555-0100',
            },
            follow_redirects=False,
        )

        assert response.status_code == 302
        assert response.headers['Location'] == 'https://stripe.test/checkout'

        pending = PendingSignup.query.filter_by(email='solo@applicant.com').first()
        assert pending is not None
        assert pending.tier_id == solo.id

        # Simulate Stripe sending back a completed checkout session payload
        fake_customer = SimpleNamespace(
            id='cus_test_123',
            email='solo@applicant.com',
            name='Alex Solo',
            first_name='Alex',
            last_name='Solo',
            metadata={},
        )
        fake_session = _make_fake_checkout_session(pending.id, fake_customer)

        monkeypatch.setattr(BillingService, 'update_customer_metadata', lambda *args, **kwargs: True)

        org, user = BillingService._provision_checkout_session(fake_session)

        assert org is not None
        assert user is not None
        assert isinstance(org, Organization)
        assert isinstance(user, User)
        assert org.subscription_tier_id == solo.id
        assert org.contact_email == 'solo@applicant.com'
        assert user.organization_id == org.id
        assert user.email == 'solo@applicant.com'
        assert pending.status == 'account_created'
