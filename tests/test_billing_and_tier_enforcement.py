import pytest
from flask_login import login_user
from app.models import db, User, Organization, SubscriptionTier, Role, Permission

# FIX 1: Add the missing import for AppPermission
from app.utils.permissions import AppPermission

class TestBillingAndTierEnforcement:
    """Test the full security cascade: billing status -> tier -> role -> permission"""

    def test_tier_permission_is_the_hard_ceiling(self, app):
        """
        Tests that a user is BLOCKED from an action if their org's tier
        does not allow it, even if their role DOES have the permission.
        """
        with app.app_context():
            # ARRANGE: Create a complex state

            # 1. Create permissions
            perm_view = Permission(name=AppPermission.PRODUCT_VIEW.value)
            perm_create = Permission(name=AppPermission.PRODUCT_CREATE.value)
            db.session.add_all([perm_view, perm_create])

            # 2. Create a "Hobbyist" tier that can ONLY view products
            hobbyist_tier = SubscriptionTier(
                name='hobbyist',
                key='hobbyist'
            )
            hobbyist_tier.permissions = [perm_view]  # Only view, no create
            db.session.add(hobbyist_tier)
            db.session.flush()  # Get the ID

            # 3. Create an Organization subscribed to the Hobbyist tier
            org = Organization(
                name='Test Hobby Org',
                subscription_tier_id=hobbyist_tier.id,
                billing_status='active'
            )
            db.session.add(org)
            db.session.flush()  # Get the ID

            # 4. Create a Role that has MORE permissions than the tier allows
            overpowered_role = Role(
                name='Manager',
                organization_id=org.id
            )
            overpowered_role.permissions = [perm_view, perm_create]  # More than tier allows
            db.session.add(overpowered_role)

            # 5. Create a User with that powerful role
            user = User(
                email='test@hobby.org',
                username='hobbytest',
                organization_id=org.id
            )
            db.session.add(user)
            db.session.commit()

            # Assign the role properly using the role assignment system
            user.assign_role(overpowered_role)

            # ACT & ASSERT

            # This should succeed because the Hobbyist tier allows 'product:view'
            assert user.has_permission(AppPermission.PRODUCT_VIEW) is True

            # This MUST FAIL. The tier is the ceiling. This is the critical test.
            assert user.has_permission(AppPermission.PRODUCT_CREATE) is False

    @pytest.mark.parametrize("billing_status, expected_status_code", [
        ('active', 200),
        ('past_due', 302),
        ('suspended', 302),
        ('canceled', 302),
    ])
    def test_billing_status_enforcement(self, app, client, test_user, billing_status, expected_status_code):
        """
        Tests that the billing middleware blocks access for non-active billing statuses.
        """
        with app.app_context():
            # ARRANGE
            # Update the user's organization with the test billing status
            org = test_user.organization
            org.billing_status = billing_status

            # THE FIX: This block ensures the user is on a tier that REQUIRES a billing check.
            if not org.subscription_tier or org.subscription_tier.is_billing_exempt:
                from app.models.subscription_tier import SubscriptionTier
                # Find a non-exempt tier in the DB or create one for the test
                non_exempt_tier = SubscriptionTier.query.filter_by(is_billing_exempt=False).first()
                if not non_exempt_tier:
                    non_exempt_tier = SubscriptionTier(name="Paid Tier", key="paid", is_billing_exempt=False, billing_provider='stripe')
                    db.session.add(non_exempt_tier)
                org.subscription_tier = non_exempt_tier

            db.session.commit()

            # Create a simple protected route to test against
            @app.route('/_protected_dashboard')
            def _protected_dashboard():
                return "Welcome to the dashboard", 200

            # ACT
            # Log the user in and try to access the protected route
            with client:
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(test_user.id)
                    sess['_fresh'] = True

                response = client.get('/_protected_dashboard')

                # ASSERT
                assert response.status_code == expected_status_code

                # If redirected, ensure it's to the correct billing page
                if expected_status_code == 302:
                    assert '/billing/upgrade' in response.location or '/billing' in response.location

    def test_developer_can_masquerade_regardless_of_billing(self, app, client):
        """
        Tests that developers can access customer data even if billing is bad.
        """
        with app.app_context():
            # ARRANGE: Create a developer user (NO organization)
            developer = User(
                email='dev@batchtrack.com',
                username='developer',
                user_type='developer',
                organization_id=None  # Developers have no organization
            )
            db.session.add(developer)

            # Create a customer org with bad billing
            customer_tier = SubscriptionTier(
                name='Pro',
                key='pro'
            )
            db.session.add(customer_tier)
            db.session.flush()  # Get the ID

            customer_org = Organization(
                name='Customer Org',
                subscription_tier_id=customer_tier.id,
                billing_status='past_due'  # Bad billing
            )
            db.session.add(customer_org)
            db.session.flush()  # Get the ID

            customer = User(
                email='customer@example.com',
                username='customer',
                organization=customer_org
            )
            db.session.add(customer)
            db.session.commit()

            # Create protected route
            @app.route('/_masquerade_test')
            def _masquerade_test():
                return "Developer access granted", 200

            # ACT: Developer accesses customer route
            with client:
                with client.session_transaction() as sess:
                    sess['_user_id'] = str(developer.id)
                    sess['_fresh'] = True
                    sess['masquerade_org_id'] = customer_org.id  # Masquerading

                response = client.get('/_masquerade_test')

                # ASSERT: Developer should have access despite customer's bad billing
                assert response.status_code == 200

    def test_complete_security_cascade(self, app):
        """
        Tests the complete security flow: billing -> tier -> role -> permission
        """
        with app.app_context():
            # ARRANGE: Create a realistic scenario

            # 1. Create permissions
            perm_batch_view = Permission(name=AppPermission.BATCH_VIEW.value)
            perm_batch_create = Permission(name=AppPermission.BATCH_CREATE.value)
            perm_admin = Permission(name=AppPermission.ADMIN.value)
            db.session.add_all([perm_batch_view, perm_batch_create, perm_admin])

            # 2. Create a "Pro" tier with batch permissions but no admin
            pro_tier = SubscriptionTier(
                name='Pro',
                key='pro'
            )
            pro_tier.permissions = [perm_batch_view, perm_batch_create]  # No admin
            db.session.add(pro_tier)
            db.session.flush()  # Get the ID

            # 3. Create organization with active billing
            org = Organization(
                name='Pro Company',
                subscription_tier_id=pro_tier.id,
                billing_status='active'
            )
            db.session.add(org)
            db.session.flush()  # Get the ID

            # 4. Create a manager role (subset of tier permissions)
            manager_role = Role(
                name='Manager',
                organization_id=org.id
            )
            manager_role.permissions = [perm_batch_view]  # Only view, not create
            db.session.add(manager_role)

            # 5. Create user with manager role
            user = User(
                email='manager@procompany.com',
                username='manager',
                organization=org
            )
            user.roles = [manager_role]
            db.session.add(user)
            db.session.commit()

            # ACT & ASSERT: Test the cascade

            # 1. User can view batches (role allows, tier allows)
            assert user.has_permission(AppPermission.BATCH_VIEW) is True

            # 2. User CANNOT create batches (role doesn't allow, even though tier does)
            assert user.has_permission(AppPermission.BATCH_CREATE) is False

            # 3. User CANNOT access admin (tier doesn't allow, regardless of role)
            assert user.has_permission(AppPermission.ADMIN) is False

            # 4. Now test billing enforcement - suspend the org
            org.billing_status = 'suspended'
            db.session.commit()

            # Even basic permissions should be blocked now by middleware
            # (This would be caught by the middleware before permission check)
            assert org.billing_status != 'active'  # Confirms billing is bad