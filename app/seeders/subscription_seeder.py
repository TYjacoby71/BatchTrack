
#!/usr/bin/env python3
"""Seed subscription tiers and data"""

import json
import os
from flask import current_app
from ..models import db, Organization, SubscriptionTier, Permission
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def safe_db_operation(operation_name, operation_func):
    """Safely execute a database operation with error handling"""
    try:
        result = operation_func()
        db.session.commit()
        return result, None
    except Exception as e:
        db.session.rollback()
        logger.warning(f"⚠️ {operation_name} failed: {e}")
        return None, str(e)

def create_exempt_tier():
    """Create the only hardcoded tier - exempt tier for system use"""
    def _create():
        exempt_tier = SubscriptionTier.query.filter_by(name='Exempt Plan').first()

        if not exempt_tier:
            print("✅ Creating exempt tier")
            exempt_tier = SubscriptionTier(
                name='Exempt Plan',
                description='System tier for exempt accounts - unlimited access',
                tier_type='monthly',
                user_limit=-1,  # Unlimited users
                max_users=None,
                max_recipes=None,
                max_batches=None,
                max_products=None,
                max_batchbot_requests=None,
                max_monthly_batches=None,
                retention_policy='subscribed',  # Keep data while subscribed
                data_retention_days=None,
                retention_notice_days=None,
                storage_addon_retention_days=None,
                is_customer_facing=False,
                billing_provider='exempt',
                stripe_lookup_key=None,
                stripe_storage_lookup_key=None,
                whop_product_key=None
            )
            db.session.add(exempt_tier)
            db.session.flush()

            # Give exempt tier ALL permissions
            all_permissions = Permission.query.all()
            exempt_tier.permissions = all_permissions

            print(f"   - Exempt tier created with {len(all_permissions)} permissions")
        else:
            print("ℹ️  Exempt tier already exists")
            # Ensure it has all permissions
            all_permissions = Permission.query.all()
            exempt_tier.permissions = all_permissions

        return exempt_tier

    tier, error = safe_db_operation("Exempt tier creation", _create)
    return tier

def create_free_tier():
    """Create the free tier"""
    def _create():
        free_tier = SubscriptionTier.query.filter_by(name='Free Tools').first()

        if not free_tier:
            print("✅ Creating free tier")
            free_tier = SubscriptionTier(
                name='Free Tools',
                description='Recipe-only starter. Inventory read-only. No batches.',
                tier_type='monthly',
                user_limit=1,
                max_users=1,
                max_recipes=10,
                max_batches=0,  # No batches allowed
                max_products=None,
                max_batchbot_requests=0,
                max_monthly_batches=0,
                retention_policy='one_year',
                data_retention_days=365,
                retention_notice_days=30,
                storage_addon_retention_days=None,
                is_customer_facing=True,
                billing_provider='exempt',  # Free tier is billing exempt
                stripe_lookup_key=None,
                stripe_storage_lookup_key=None,
                whop_product_key=None
            )
            db.session.add(free_tier)
            db.session.flush()

            # Assign limited permissions for free tier
            free_permissions = Permission.query.filter(Permission.name.in_([
                'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.delete',
                'inventory.view'  # Read-only inventory access
            ])).all()
            free_tier.permissions = free_permissions

            print(f"   - Free tier created with {len(free_permissions)} permissions")
        else:
            print("ℹ️  Free tier already exists")

        return free_tier

    tier, error = safe_db_operation("Free tier creation", _create)
    return tier

def create_solo_tier():
    """Create the solo tier"""
    def _create():
        solo_tier = SubscriptionTier.query.filter_by(name='Solo Maker').first()

        if not solo_tier:
            print("✅ Creating solo tier")
            solo_tier = SubscriptionTier(
                name='Solo Maker',
                description='Perfect for individual makers and small producers',
                tier_type='monthly',
                user_limit=1,
                max_users=1,
                max_recipes=50,
                max_batches=None,  # Unlimited batches
                max_products=25,
                max_batchbot_requests=100,
                max_monthly_batches=200,
                retention_policy='one_year',
                data_retention_days=365,
                retention_notice_days=30,
                storage_addon_retention_days=365,
                is_customer_facing=True,
                billing_provider='stripe',
                stripe_lookup_key='batchtrack_solo_monthly',
                stripe_storage_lookup_key=None,  # No hardcoded lookup key
                whop_product_key=None
            )
            db.session.add(solo_tier)
            db.session.flush()

            # Assign comprehensive permissions for solo tier
            solo_permissions = Permission.query.filter(Permission.name.in_([
                'dashboard.view',
                'inventory.view', 'inventory.edit', 'inventory.adjust', 'inventory.reserve', 
                'inventory.delete', 'inventory.view_costs',
                'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.delete', 
                'recipes.scale', 'recipes.plan_production',
                'batches.view', 'batches.create', 'batches.edit', 'batches.finish', 
                'batches.cancel', 'batches.view_costs',
                'products.view', 'products.create', 'products.edit', 'products.delete',
                'products.manage_variants', 'products.sales_tracking',
                'organization.manage_billing',
                'alerts.view', 'alerts.manage', 'alerts.dismiss',
                'reports.view', 'reports.export', 'reports.advanced', 'reports.custom',
                'integrations.shopify', 'integrations.marketplace', 'integrations.api_access',
                'ai.recipe_optimization', 'ai.demand_forecasting', 'ai.quality_insights'
            ])).all()
            solo_tier.permissions = solo_permissions

            print(f"   - Solo tier created with {len(solo_permissions)} permissions")
        else:
            print("ℹ️  Solo tier already exists")

        return solo_tier

    tier, error = safe_db_operation("Solo tier creation", _create)
    return tier

def create_team_tier():
    """Create the team tier"""
    def _create():
        team_tier = SubscriptionTier.query.filter_by(name='Team Plan').first()

        if not team_tier:
            print("✅ Creating team tier")
            team_tier = SubscriptionTier(
                name='Team Plan',
                description='Collaboration tools for small teams',
                tier_type='monthly',
                user_limit=10,
                max_users=10,
                max_recipes=200,
                max_batches=None,  # Unlimited batches
                max_products=100,
                max_batchbot_requests=500,
                max_monthly_batches=1000,
                retention_policy='one_year',
                data_retention_days=365,
                retention_notice_days=30,
                storage_addon_retention_days=365,
                is_customer_facing=True,
                billing_provider='stripe',
                stripe_lookup_key='batchtrack_team_monthly',
                stripe_storage_lookup_key=None,  # No hardcoded lookup key
                whop_product_key=None
            )
            db.session.add(team_tier)
            db.session.flush()

            # Assign all permissions except developer permissions for team tier
            team_permissions = Permission.query.filter(
                ~Permission.name.like('developer.%')
            ).all()
            team_tier.permissions = team_permissions

            print(f"   - Team tier created with {len(team_permissions)} permissions")
        else:
            print("ℹ️  Team tier already exists")

        return team_tier

    tier, error = safe_db_operation("Team tier creation", _create)
    return tier

def create_enterprise_tier():
    """Create the enterprise tier"""
    def _create():
        enterprise_tier = SubscriptionTier.query.filter_by(name='Enterprise Plan').first()

        if not enterprise_tier:
            print("✅ Creating enterprise tier")
            enterprise_tier = SubscriptionTier(
                name='Enterprise Plan',
                description='Full-scale production management',
                tier_type='monthly',
                user_limit=-1,  # Unlimited users
                max_users=None,
                max_recipes=None,  # Unlimited recipes
                max_batches=None,  # Unlimited batches
                max_products=None,  # Unlimited products
                max_batchbot_requests=None,  # Unlimited AI requests
                max_monthly_batches=None,  # Unlimited monthly batches
                retention_policy='subscribed',  # Keep data while subscribed
                data_retention_days=None,
                retention_notice_days=30,
                storage_addon_retention_days=None,
                is_customer_facing=True,
                billing_provider='stripe',
                stripe_lookup_key='batchtrack_enterprise_monthly',
                stripe_storage_lookup_key=None,  # No hardcoded lookup key
                whop_product_key=None
            )
            db.session.add(enterprise_tier)
            db.session.flush()

            # Assign all permissions except developer permissions for enterprise tier
            enterprise_permissions = Permission.query.filter(
                ~Permission.name.like('developer.%')
            ).all()
            enterprise_tier.permissions = enterprise_permissions

            print(f"   - Enterprise tier created with {len(enterprise_permissions)} permissions")
        else:
            print("ℹ️  Enterprise tier already exists")

        return enterprise_tier

    tier, error = safe_db_operation("Enterprise tier creation", _create)
    return tier

def seed_subscription_tiers():
    """Create all subscription tiers with proper schema"""
    if not current_app:
        raise RuntimeError("seed_subscription_tiers() must be called within Flask application context")

    print("=== Seeding Complete Subscription System ===")
    successful_tiers = []
    failed_tiers = []

    # Create all tiers - continue even if some fail
    tier_creators = [
        ("Exempt tier", create_exempt_tier),
        ("Free tier", create_free_tier),
        ("Solo tier", create_solo_tier),
        ("Team tier", create_team_tier),
        ("Enterprise tier", create_enterprise_tier)
    ]

    for tier_name, creator_func in tier_creators:
        try:
            tier = creator_func()
            if tier:
                successful_tiers.append(tier_name)
            else:
                failed_tiers.append(tier_name)
        except Exception as e:
            print(f"⚠️ Failed to create {tier_name}: {e}")
            failed_tiers.append(tier_name)

    # Final commit attempt
    try:
        db.session.commit()
        print("✅ Subscription tier seeding completed!")
    except Exception as e:
        print(f"⚠️ Final commit had issues: {e}")
        db.session.rollback()

    # Report results
    if successful_tiers:
        print(f"✅ Successfully created/verified: {', '.join(successful_tiers)}")
    if failed_tiers:
        print(f"⚠️ Had issues with: {', '.join(failed_tiers)}")
        print("   - These tiers may need manual attention")

def migrate_existing_organizations():
    """Migrate existing organizations to use tier IDs"""
    if not current_app:
        raise RuntimeError("migrate_existing_organizations() must be called within Flask application context")

    print("=== Migrating Organizations to Tier IDs ===")

    def _migrate():
        organizations = Organization.query.all()
        migrated_count = 0

        for org in organizations:
            if not org.subscription_tier_id:
                # Assign free tier to any organization without a tier
                free_tier = SubscriptionTier.query.filter_by(name='Free Tools').first()
                if free_tier:
                    org.subscription_tier_id = free_tier.id
                    migrated_count += 1
                    print(f"✅ Assigned free tier to organization {org.name}")

        return migrated_count

    count, error = safe_db_operation("Organization migration", _migrate)
    
    if count is not None:
        print(f"✅ Organization migration completed! ({count} organizations migrated)")
    else:
        print(f"⚠️ Organization migration had issues: {error}")

def seed_subscriptions():
    """Seed all subscription tiers and migrate organizations"""
    from flask import current_app

    # Ensure we're in an application context
    if not current_app:
        raise RuntimeError("seed_subscriptions() must be called within Flask application context")

    print("=== Seeding Complete Subscription System ===")

    # Step 1: Create all subscription tiers (with error recovery)
    seed_subscription_tiers()

    # Step 2: Migrate existing organizations if any exist (with error recovery)
    migrate_existing_organizations()

    print("✅ Complete subscription system seeding completed!")
    print("   - Tiers processed with error recovery")
    print("   - Organizations migrated with error recovery")
    print("   - System ready for production use")
