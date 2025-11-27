from flask import Blueprint, render_template, request, session, redirect, flash, jsonify, url_for, current_app
from flask_login import login_required, current_user
from app.models import Organization, User, Permission, Role, GlobalItem
from app.models import ProductCategory
from app.extensions import db
from app.utils.json_store import read_json_file, write_json_file
from datetime import datetime, timedelta, timezone
from sqlalchemy import func
from .system_roles import system_roles_bp
from .subscription_tiers import subscription_tiers_bp

# Assuming require_developer_permission is defined elsewhere, e.g., in system_roles.py or utils.py
# If not, you'll need to define or import it. For now, let's assume it's available.
# If you are using @login_required, you might not need @require_developer_permission for all routes
# but for the waitlist statistics, it seems intended.
# For demonstration, if require_developer_permission is not defined, you can temporarily remove it
# or define a placeholder. Let's assume it's correctly imported or defined.
try:
    from .decorators import require_developer_permission, permission_required
except ImportError:
    # Define a placeholder if not found, to allow the rest of the code to be processed
    # In a real scenario, ensure this decorator is correctly imported.
    def require_developer_permission(permission_name):
        def decorator(func):
            return func
        return decorator
    def permission_required(permission_name):
        def decorator(func):
            return func
        return decorator

# Assuming TimezoneUtils is available and correctly imported
try:
    from app.utils.timezone_utils import TimezoneUtils
except ImportError:
    # Define a placeholder if not found
    class TimezoneUtils:
        @staticmethod
        def utc_now():
            return datetime.now(timezone.utc)

developer_bp = Blueprint('developer', __name__, url_prefix='/developer')
developer_bp.register_blueprint(system_roles_bp)
developer_bp.register_blueprint(subscription_tiers_bp)
from .addons import addons_bp
developer_bp.register_blueprint(addons_bp)

# Developer access control is handled centrally in `app/middleware.py`.
# This eliminates the dual security checkpoints that were causing routing conflicts

FEATURE_FLAG_SECTIONS = [
    {
        'title': 'Core business features',
        'description': 'Enable or disable the production features that every organization depends on.',
        'flags': [
            {'key': 'FEATURE_FIFO_TRACKING', 'label': 'FIFO Inventory Tracking', 'status': 'wired', 'description': 'First-in-first-out inventory tracking via the inventory adjustment service.'},
            {'key': 'FEATURE_BARCODE_SCANNING', 'label': 'Barcode Scanning', 'status': 'stub', 'description': 'Placeholder for future scanner integrations.'},
            {'key': 'FEATURE_PRODUCT_VARIANTS', 'label': 'Product Variants System', 'status': 'wired', 'description': 'Manage SKUs with variants powered by ProductService.'},
            {'key': 'FEATURE_AUTO_SKU_GENERATION', 'label': 'Auto-generate SKUs', 'status': 'wired', 'description': 'Automatically create SKU codes when products are saved.'},
            {'key': 'FEATURE_RECIPE_VARIATIONS', 'label': 'Recipe Variations', 'status': 'wired', 'description': 'Support parent/child recipe relationships.'},
            {'key': 'FEATURE_COST_TRACKING', 'label': 'Cost Tracking & Profit Margins', 'status': 'wired', 'description': 'Costing engine + FIFO/average cost calculations.'},
            {'key': 'FEATURE_EXPIRATION_TRACKING', 'label': 'Expiration Date Tracking', 'status': 'wired', 'description': 'Lot-based expiration alerts and services.'},
            {'key': 'FEATURE_BULK_OPERATIONS', 'label': 'Bulk Inventory Operations', 'status': 'wired', 'description': 'Bulk stock adjustments and checks.'},
        ],
    },
    {
        'title': 'Developer & advanced features',
        'description': 'Capabilities intended for internal tooling or staging environments.',
        'flags': [
            {'key': 'FEATURE_INVENTORY_ANALYTICS', 'label': 'Inventory Analytics (Developer)', 'status': 'wired', 'description': 'Developer-only analytics dashboard and APIs.'},
            {'key': 'FEATURE_DEBUG_MODE', 'label': 'Debug Mode', 'status': 'stub', 'description': 'Verbose logging & unsafe diagnostics.'},
            {'key': 'FEATURE_AUTO_BACKUP', 'label': 'Auto-backup System', 'status': 'stub', 'description': 'Nightly exports of core tables.'},
            {'key': 'FEATURE_CSV_EXPORT', 'label': 'CSV Export', 'status': 'wired', 'description': 'Downloadable CSV exports for reports.'},
            {'key': 'FEATURE_ADVANCED_REPORTS', 'label': 'Advanced Reports', 'status': 'stub', 'description': 'Future premium reporting suite.'},
            {'key': 'FEATURE_GLOBAL_ITEM_LIBRARY', 'label': 'Global Item Library Access', 'status': 'wired', 'description': 'Org access to the shared global inventory library.'},
        ],
    },
    {
        'title': 'Notifications & integrations',
        'description': 'Toggle customer-facing communications and external app hooks.',
        'flags': [
            {'key': 'FEATURE_EMAIL_NOTIFICATIONS', 'label': 'Email Notifications', 'status': 'wired', 'description': 'Transactional + lifecycle email delivery.'},
            {'key': 'FEATURE_BROWSER_NOTIFICATIONS', 'label': 'Browser Push Notifications', 'status': 'stub', 'description': 'Web push notifications to the browser.'},
            {'key': 'FEATURE_SHOPIFY_INTEGRATION', 'label': 'Shopify Integration', 'status': 'stub', 'description': 'Future e-commerce sync pipeline.'},
            {'key': 'FEATURE_API_ACCESS', 'label': 'REST API Access', 'status': 'stub', 'description': 'Public REST API for third-party apps.'},
            {'key': 'FEATURE_OAUTH_PROVIDERS', 'label': 'OAuth Login Providers', 'status': 'wired', 'description': 'Google/Facebook sign-in support.'},
        ],
    },
    {
        'title': 'AI & forecasting experiments',
        'description': 'Aspirational features that are not yet implemented.',
        'flags': [
            {'key': 'FEATURE_AI_RECIPE_OPTIMIZATION', 'label': 'AI Recipe Optimization', 'status': 'stub', 'description': 'ML-assisted formulation suggestions.'},
            {'key': 'FEATURE_AI_DEMAND_FORECASTING', 'label': 'AI Demand Forecasting', 'status': 'stub', 'description': 'Predict demand to guide purchasing.'},
            {'key': 'FEATURE_AI_QUALITY_INSIGHTS', 'label': 'AI Quality Insights', 'status': 'stub', 'description': 'Automated quality checks & anomaly detection.'},
        ],
    },
    {
        'title': 'Public tool availability',
        'description': 'Control which calculator suites are exposed on the marketing site.',
        'flags': [
            {'key': 'TOOLS_SOAP', 'label': 'Soap Making Tools', 'status': 'wired', 'description': 'Saponification & curing calculators.'},
            {'key': 'TOOLS_CANDLES', 'label': 'Candle Making Tools', 'status': 'wired', 'description': 'Wick, wax, and fragrance load calculators.'},
            {'key': 'TOOLS_LOTIONS', 'label': 'Lotion & Cosmetic Tools', 'status': 'wired', 'description': 'Batch math for cosmetics and topicals.'},
            {'key': 'TOOLS_HERBAL', 'label': 'Herbalist Tools', 'status': 'wired', 'description': 'Tincture and infusion helpers.'},
            {'key': 'TOOLS_BAKING', 'label': 'Baking Tools', 'status': 'wired', 'description': 'Recipe scaling for bakers & confectioners.'},
        ],
    },
]

FEATURE_FLAG_KEYS = [flag['key'] for section in FEATURE_FLAG_SECTIONS for flag in section['flags']]

BATCHLEY_JOB_CATALOG = [
    {
        'slug': 'recipe-intake',
        'name': 'Recipe Draft Intake',
        'tool': 'create_recipe_draft',
        'status': 'wired',
        'description': 'Uploads text (and OCR’d images) to create missing inventory items first, then saves the recipe as a draft with granular success messaging.',
        'inputs': [
            'Text instructions, ingredient lists, or OCR payloads',
            'Optional yield amount/unit for scaling',
            'Ingredient rows with allow_create toggles',
        ],
        'outputs': [
            'New inventory items seeded before the recipe',
            'Recipe draft saved for manual review/publish',
            'Partial failure report when a single ingredient needs correction',
        ],
        'handoff': 'Draft stays unpublished until a human reviews and publishes the recipe.',
    },
    {
        'slug': 'bulk-inventory',
        'name': 'Bulk Inventory Receipt Builder',
        'tool': 'submit_bulk_inventory_update',
        'status': 'wired',
        'description': 'Parses messy receipts or free-form shopping lists, asks for clarifications, and stages create/restock/spoil/trash rows in the bulk modal.',
        'inputs': [
            'Receipt text or photo transcription (quantities + units)',
            'Desired change_type per row (create/restock/spoil/trash)',
            'Optional cost overrides and notes',
        ],
        'outputs': [
            'Draft bulk adjustment queued for user confirmation',
            'Ability to auto-submit when customer explicitly asks',
            'Row-level audit trail posted back to the chat transcript',
        ],
        'handoff': 'Customer can edit/save drafts in the modal before the final submit call.',
    },
    {
        'slug': 'single-restock',
        'name': 'Single Item Restock',
        'tool': 'log_inventory_purchase',
        'status': 'wired',
        'description': 'Fast path for topping up one inventory item when the user already knows the SKU.',
        'inputs': [
            'Inventory item ID or fuzzy name match',
            'Quantity + unit, optional cost per unit',
            'Free-form note for receipt/source',
        ],
        'outputs': [
            'Inventory adjustment entry with costing metadata',
            'Follow-up prompt offering FIFO/expiration guidance',
        ],
        'handoff': 'Ideal for “I just restocked olive oil” requests—no modal required.',
    },
    {
        'slug': 'insights',
        'name': 'Insight Snapshot / KPI Q&A',
        'tool': 'fetch_insight_snapshot',
        'status': 'wired',
        'description': 'Returns costing, freshness, throughput, and global benchmark snippets that Batchley can narrate back to the user.',
        'inputs': [
            'Optional focus flag: cost, freshness, throughput, overview',
        ],
        'outputs': [
            'Structured JSON (org dashboard, hotspots, freshness risks)',
            'Comparative guidance vs global averages',
        ],
        'handoff': 'Often paired with coaching copy or follow-up prompts to gather more context.',
    },
    {
        'slug': 'marketplace',
        'name': 'Marketplace Sync Check',
        'tool': 'fetch_marketplace_status',
        'status': 'beta',
        'description': 'Surfaces recipe marketplace readiness, pending syncs, and recent failures so support can respond inside the chat.',
        'inputs': [
            'Optional “limit” to cap how many listings to summarize (default 5)',
        ],
        'outputs': [
            'Counts for total/pending/failed listings',
            'Top product cards with last sync timestamp + status',
        ],
        'handoff': 'Hidden unless the org tier has marketplace permissions.',
    },
]

BATCHLEY_ENV_KEYS = [
    {
        'key': 'GOOGLE_AI_API_KEY',
        'label': 'Google AI API Key',
        'description': 'Gemini credential for both Batchley and the public help bot.',
        'secret': True,
    },
    {
        'key': 'GOOGLE_AI_BATCHBOT_MODEL',
        'label': 'Batchley Model',
        'description': 'Model override for authenticated Batchley traffic.',
    },
    {
        'key': 'GOOGLE_AI_PUBLICBOT_MODEL',
        'label': 'Public Bot Model',
        'description': 'Model used on the marketing site/public help modal.',
    },
    {
        'key': 'BATCHBOT_DEFAULT_MAX_REQUESTS',
        'label': 'Default Action Cap',
        'description': 'Base automation quota per org per window (tiers override).',
    },
    {
        'key': 'BATCHBOT_CHAT_MAX_MESSAGES',
        'label': 'Default Chat Cap',
        'description': 'Baseline chat-only prompts per window.',
    },
    {
        'key': 'BATCHBOT_REQUEST_WINDOW_DAYS',
        'label': 'Usage Window (days)',
        'description': 'Length of the rolling window for action/chat quotas.',
    },
    {
        'key': 'BATCHBOT_SIGNUP_BONUS_REQUESTS',
        'label': 'Signup Bonus Credits',
        'description': 'Promo requests granted to new organizations.',
    },
    {
        'key': 'BATCHBOT_REFILL_LOOKUP_KEY',
        'label': 'Stripe Refill Lookup Key',
        'description': 'Price lookup key referenced when issuing refill checkout sessions.',
    },
    {
        'key': 'BATCHBOT_COST_PER_MILLION_INPUT',
        'label': 'Cost Per Million Input Tokens',
        'description': 'Reference compute cost for per-token pricing.',
        'format': 'currency',
    },
    {
        'key': 'BATCHBOT_COST_PER_MILLION_OUTPUT',
        'label': 'Cost Per Million Output Tokens',
        'description': 'Reference compute cost for responses.',
        'format': 'currency',
    },
]

BATCHLEY_WORKFLOW_NOTES = [
    {
        'title': 'Session-bound execution',
        'body': 'Batchley refuses to run without an authenticated organization user, so every automation inherits the same RBAC + tier limits as the UI.',
    },
    {
        'title': 'Chat vs action metering',
        'body': 'Pure Q&A consumes the chat bucket; tool calls consume the action bucket and will automatically recommend the refill checkout URL when exhausted.',
    },
    {
        'title': 'Draft-first UX',
        'body': 'Recipe creation and bulk inventory flows always build drafts so humans can confirm edits before publishing. Partial failures are spelled out in the response payload.',
    },
    {
        'title': 'Marketplace awareness',
        'body': 'Marketplace tooling only activates for tiers that include `integrations.marketplace`, preventing leakage for customers without licensing.',
    },
]

@developer_bp.route('/dashboard')
@login_required
def dashboard():
    """Main developer system dashboard"""
    from app.services.statistics import AnalyticsDataService

    force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
    dashboard_data = AnalyticsDataService.get_developer_dashboard(force_refresh=force_refresh)
    overview = dashboard_data.get('overview') or {}
    tier_breakdown = overview.get('tiers') or {}
    recent_orgs = dashboard_data.get('recent_organizations') or []
    problem_orgs = dashboard_data.get('attention_organizations') or []
    waitlist_count = dashboard_data.get('waitlist_count', 0)
    new_orgs_count = dashboard_data.get('recent_count') or len(recent_orgs)
    attention_count = dashboard_data.get('attention_count') or len(problem_orgs)
    fault_feed = AnalyticsDataService.get_fault_log_entries(include_all=True, force_refresh=force_refresh)
    support_queue = fault_feed[:4]
    support_queue_total = len(fault_feed)

    generated_iso = dashboard_data.get('generated_at')
    generated_display = None
    if generated_iso:
        try:
            generated_dt = datetime.fromisoformat(generated_iso)
            generated_display = generated_dt.strftime('%Y-%m-%d %H:%M UTC')
        except ValueError:
            generated_display = generated_iso

    return render_template(
        'developer/dashboard.html',
        total_orgs=overview.get('total_organizations', 0),
        active_orgs=overview.get('active_organizations', 0),
        total_users=overview.get('total_users', 0),
        active_users=overview.get('active_users', 0),
        new_orgs_count=new_orgs_count,
        attention_count=attention_count,
        tier_breakdown=tier_breakdown,
        recent_orgs=recent_orgs,
        problem_orgs=problem_orgs,
        support_queue=support_queue,
        support_queue_total=support_queue_total,
        waitlist_count=waitlist_count,
        dashboard_generated_at=generated_display,
        force_refresh=force_refresh,
        breadcrumb_items=[{'label': 'Developer Dashboard'}],
    )

@developer_bp.route('/marketing-admin')
@login_required
def marketing_admin():
    """Manage homepage marketing content (reviews, spotlights, messages)."""
    from app.services.statistics import AnalyticsDataService

    marketing_data = AnalyticsDataService.get_marketing_content()
    reviews = marketing_data.get('reviews', [])
    spotlights = marketing_data.get('spotlights', [])
    messages = {'day_1': '', 'day_3': '', 'day_5': ''}
    messages.update(marketing_data.get('marketing_messages', {}))
    promo_codes = marketing_data.get('promo_codes', []) or []
    demo_url = marketing_data.get('demo_url', '') or ''
    demo_videos = marketing_data.get('demo_videos', []) or []

    return render_template(
        'developer/marketing_admin.html',
        reviews=reviews,
        spotlights=spotlights,
        messages=messages,
        promo_codes=promo_codes,
        demo_url=demo_url,
        demo_videos=demo_videos
    )

@developer_bp.route('/marketing-admin/save', methods=['POST'])
@login_required
def marketing_admin_save():
    """Save reviews, spotlights, and marketing messages (simple JSON persistence)."""
    try:
        data = request.get_json() or {}
        if 'reviews' in data:
            write_json_file('data/reviews.json', data['reviews'])
        if 'spotlights' in data:
            write_json_file('data/spotlights.json', data['spotlights'])
        if 'messages' in data or 'promo_codes' in data or 'demo_url' in data or 'demo_videos' in data:
            # merge into settings.json under marketing_messages
            cfg = read_json_file('settings.json', default={}) or {}
            if 'messages' in data:
                cfg['marketing_messages'] = data['messages']
            if 'promo_codes' in data:
                cfg['promo_codes'] = data['promo_codes']
            if 'demo_url' in data:
                cfg['demo_url'] = data['demo_url']
            if 'demo_videos' in data:
                cfg['demo_videos'] = data['demo_videos']
            write_json_file('settings.json', cfg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@developer_bp.route('/batchley')
@login_required
def batchley_overview():
    """Developer view of Batchley's capabilities, limits, and configuration."""

    def _format_env_value(entry, raw_value):
        if raw_value in (None, ''):
            return None
        if entry.get('format') == 'currency':
            try:
                return f"${float(raw_value):,.2f}"
            except (TypeError, ValueError):
                return raw_value
        return raw_value

    def _format_limit(raw_value, *, suffix=''):
        if raw_value in (None, ''):
            return 'Not set'
        try:
            numeric = float(raw_value)
            if numeric < 0:
                return 'Unlimited'
            if numeric.is_integer():
                numeric = int(numeric)
            return f"{numeric}{suffix}"
        except (TypeError, ValueError):
            return f"{raw_value}{suffix}"

    env_status = []
    for entry in BATCHLEY_ENV_KEYS:
        raw_value = current_app.config.get(entry['key'])
        formatted = _format_env_value(entry, raw_value)
        is_set = raw_value not in (None, '')
        env_status.append(
            {
                'key': entry['key'],
                'label': entry['label'],
                'description': entry['description'],
                'is_secret': entry.get('secret', False),
                'is_set': is_set,
                'value': 'Configured' if entry.get('secret') and is_set else formatted,
            }
        )

    limit_cards = [
        {
            'label': 'Default action cap / window',
            'value': _format_limit(current_app.config.get('BATCHBOT_DEFAULT_MAX_REQUESTS'), suffix=' requests'),
            'description': 'Used when a subscription tier does not override `max_batchbot_requests` (set -1 for unlimited).',
        },
        {
            'label': 'Default chat cap / window',
            'value': _format_limit(current_app.config.get('BATCHBOT_CHAT_MAX_MESSAGES'), suffix=' messages'),
            'description': 'Pure Q&A prompts before Batchley demands either a refill or tier bump (set -1 for unlimited).',
        },
        {
            'label': 'Usage window',
            'value': _format_limit(current_app.config.get('BATCHBOT_REQUEST_WINDOW_DAYS'), suffix=' days'),
            'description': 'Defines when counters reset for both chat and action buckets.',
        },
        {
            'label': 'Signup bonus credits',
            'value': _format_limit(current_app.config.get('BATCHBOT_SIGNUP_BONUS_REQUESTS'), suffix=' requests'),
            'description': 'Granted per organization immediately after the signup service creates the org.',
        },
        {
            'label': 'Stripe refill lookup key',
            'value': current_app.config.get('BATCHBOT_REFILL_LOOKUP_KEY') or 'Not set',
            'description': 'Must match the price lookup key used by the `batchbot_refill_100` add-on.',
        },
        {
            'label': 'Request timeout',
            'value': _format_limit(current_app.config.get('BATCHBOT_REQUEST_TIMEOUT_SECONDS'), suffix=' seconds'),
            'description': 'Raise when Gemini calls might take longer—defaults to 45 seconds.',
        },
        {
            'label': 'Cost reference (input tokens)',
            'value': _format_env_value({'format': 'currency'}, current_app.config.get('BATCHBOT_COST_PER_MILLION_INPUT')) or 'Not set',
            'description': 'Used for pricing conversations; update when Google adjusts rates.',
        },
        {
            'label': 'Cost reference (output tokens)',
            'value': _format_env_value({'format': 'currency'}, current_app.config.get('BATCHBOT_COST_PER_MILLION_OUTPUT')) or 'Not set',
            'description': 'Pairs with the input rate when modeling gross margin.',
        },
    ]

    return render_template(
        'developer/batchley.html',
        job_catalog=BATCHLEY_JOB_CATALOG,
        env_status=env_status,
        limit_cards=limit_cards,
        workflow_notes=BATCHLEY_WORKFLOW_NOTES,
        breadcrumb_items=[
            {'label': 'Developer Dashboard', 'url': url_for('developer.dashboard')},
            {'label': 'Batchley'},
        ],
    )


@developer_bp.route('/organizations')
@developer_bp.route('/customer-support')
@login_required
def organizations():
    """Customer support dashboard for organization triage"""
    organizations = Organization.query.order_by(Organization.name.asc()).all()
    selected_org_id = session.get('dev_selected_org_id')
    selected_org = db.session.get(Organization, selected_org_id) if selected_org_id else None

    from app.services.statistics import AnalyticsDataService
    dashboard_snapshot = AnalyticsDataService.get_developer_dashboard()
    waitlist_count = dashboard_snapshot.get('waitlist_count', 0)
    attention_orgs = dashboard_snapshot.get('attention_organizations') or []
    attention_org_ids = {org['id'] for org in attention_orgs}
    recent_orgs = dashboard_snapshot.get('recent_organizations') or []

    fault_feed = AnalyticsDataService.get_fault_log_entries(include_all=True)
    support_queue = fault_feed[:8]

    support_metrics = {
        'total_orgs': len(organizations),
        'active_orgs': len([org for org in organizations if org.is_active]),
        'attention_count': len(attention_orgs),
        'waitlist_count': waitlist_count,
        'open_tickets': len(fault_feed),
        'recent_signups': recent_orgs[:5],
    }

    return render_template(
        'developer/customer_support.html',
        organizations=organizations,
        selected_org=selected_org,
        attention_orgs=attention_orgs,
        attention_org_ids=attention_org_ids,
        support_queue=support_queue,
        support_metrics=support_metrics,
        waitlist_count=waitlist_count,
        recent_orgs=recent_orgs[:6],
        breadcrumb_items=[
            {'label': 'Developer Dashboard', 'url': url_for('developer.dashboard')},
            {'label': 'Customer Support'}
        ],
    )

@developer_bp.route('/organizations/create', methods=['GET', 'POST'])
@login_required
def create_organization():
    """Create new organization with owner user"""
    # Load available tiers for the form (DB only)
    from app.models.subscription_tier import SubscriptionTier as _ST
    available_tiers = {str(t.id): {'name': t.name} for t in _ST.query.order_by(_ST.name).all()}

    def render_form(form_data=None):
        return render_template(
            'developer/create_organization.html',
            available_tiers=available_tiers,
            form_data=form_data or {}
        )

    if request.method == 'POST':
        form_data = request.form
        # Organization details
        name = form_data.get('name')
        subscription_tier = form_data.get('subscription_tier', 'free')
        creation_reason = form_data.get('creation_reason')
        notes = form_data.get('notes', '')

        # User details
        username = form_data.get('username')
        email = form_data.get('email')
        first_name = form_data.get('first_name')
        last_name = form_data.get('last_name')
        password = form_data.get('password')
        phone = form_data.get('phone')

        # Validation
        if not name:
            flash('Organization name is required', 'error')
            return render_form(form_data)

        if not username:
            flash('Username is required', 'error')
            return render_form(form_data)

        if not email:
            flash('Email is required', 'error')
            return render_form(form_data)

        if not password:
            flash('Password is required', 'error')
            return render_form(form_data)

        # Check if username already exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists', 'error')
            return render_form(form_data)

        try:
            # Create organization
            org = Organization(
                name=name,
                contact_email=email,
                is_active=True
            )
            db.session.add(org)
            db.session.flush()  # Get the ID

            # Assign subscription tier to organization
            from app.models.subscription_tier import SubscriptionTier
            tier_record = SubscriptionTier.find_by_identifier(subscription_tier)
            if tier_record:
                org.subscription_tier_id = tier_record.id
            else:
                # Default to exempt tier if tier not found
                exempt_tier = SubscriptionTier.find_by_identifier('exempt')
                if exempt_tier:
                    org.subscription_tier_id = exempt_tier.id

            # Create organization owner user
            owner_user = User(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                organization_id=org.id,
                user_type='customer',
                is_organization_owner=True,
                is_active=True
            )
            owner_user.set_password(password)
            db.session.add(owner_user)
            db.session.flush()  # Get the user ID

            # Assign organization owner role
            from app.models.role import Role
            org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
            if org_owner_role:
                owner_user.assign_role(org_owner_role)

            db.session.commit()

            flash(f'Organization "{name}" and owner user "{username}" created successfully', 'success')
            return redirect(url_for('developer.organization_detail', org_id=org.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating organization: {str(e)}', 'error')
            return render_form(form_data)

    return render_form()

@developer_bp.route('/organizations/<int:org_id>')
@login_required
def organization_detail(org_id):
    """Detailed organization management"""
    org = Organization.query.get_or_404(org_id)
    users_query = User.query.filter_by(organization_id=org_id).all()

    # Convert User objects to dictionaries for JSON serialization
    users = []
    for user in users_query:
        user_dict = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'user_type': user.user_type,
            'is_organization_owner': user.is_organization_owner,
            'is_active': user.is_active,
            'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
            'full_name': user.full_name
        }
        users.append(user_dict)

    # Build subscription tiers from DB for the dropdown
    from app.models.subscription_tier import SubscriptionTier as _ST
    try:
        all_db_tiers = _ST.query.order_by(_ST.name).all()
        tiers_config = {str(t.id): {'name': t.name, 'is_available': t.has_valid_integration or t.is_billing_exempt} for t in all_db_tiers}
    except Exception:
        tiers_config = {}

    # Debug subscription info
    current_tier = org.effective_subscription_tier
    tier_record = org.tier

    print(f"DEBUG: Organization {org.name} (ID: {org.id})")
    print(f"DEBUG: Has tier record: {tier_record is not None}")
    if tier_record:
        print(f"DEBUG: Tier id: {tier_record.id}")
        print(f"DEBUG: Tier name: {tier_record.name}")
    print(f"DEBUG: Effective tier id: {current_tier}")
    print(f"DEBUG: Available tiers: {list(tiers_config.keys())}")

    return render_template(
        'developer/organization_detail.html',
        organization=org,
        users=users,
        users_objects=users_query,
        tiers_config=tiers_config,
        current_tier=current_tier,
        breadcrumb_items=[
            {'label': 'Developer Dashboard', 'url': url_for('developer.dashboard')},
            {'label': 'Customer Support', 'url': url_for('developer.organizations')},
            {'label': org.name}
        ],
    )

@developer_bp.route('/organizations/<int:org_id>/edit', methods=['POST'])
@login_required
def edit_organization(org_id):
    """Edit organization details"""
    org = Organization.query.get_or_404(org_id)

    # Debug form data
    print(f"DEBUG: Form data received: {dict(request.form)}")

    old_name = org.name
    old_active = org.is_active
    old_tier = org.effective_subscription_tier

    org.name = request.form.get('name', org.name)
    org.is_active = request.form.get('is_active') == 'true'

    # Update subscription tier if provided
    new_tier = request.form.get('subscription_tier')
    print(f"DEBUG: Updating tier from '{old_tier}' to '{new_tier}'")

    tier_record = None
    if new_tier:
        from app.models.subscription_tier import SubscriptionTier
        tier_record = SubscriptionTier.find_by_identifier(new_tier)
        if tier_record:
            print(f"DEBUG: Updating organization tier to '{new_tier}'")
            org.subscription_tier_id = tier_record.id
        else:
            print(f"DEBUG: Tier '{new_tier}' not found in database")

    try:
        db.session.commit()
        print(f"DEBUG: Successfully committed changes")
        print(f"DEBUG: Name: '{old_name}' -> '{org.name}'")
        print(f"DEBUG: Active: {old_active} -> {org.is_active}")
        print(f"DEBUG: New effective tier: '{org.effective_subscription_tier}'")
        flash('Organization updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        print(f"DEBUG: Error committing changes: {str(e)}")
        flash(f'Error updating organization: {str(e)}', 'error')

    return redirect(url_for('developer.organization_detail', org_id=org_id))

@developer_bp.route('/organizations/<int:org_id>/upgrade', methods=['POST'])
@login_required
def upgrade_organization(org_id):
    """Upgrade organization subscription"""
    org = Organization.query.get_or_404(org_id)
    new_tier = request.form.get('tier')

    from app.models.subscription_tier import SubscriptionTier
    tier_record = SubscriptionTier.find_by_identifier(new_tier)

    if tier_record:
        org.subscription_tier_id = tier_record.id
        db.session.commit()
        flash(f'Organization upgraded to {new_tier}', 'success')
    else:
        flash('Invalid subscription tier', 'error')

    return redirect(url_for('developer.organization_detail', org_id=org_id))

@developer_bp.route('/organizations/<int:org_id>/delete', methods=['POST'])
@login_required
def delete_organization(org_id):
    """Permanently delete an organization and all associated data (developers only)"""
    try:
        data = request.get_json()
        password = data.get('password')
        confirm_text = data.get('confirm_text')

        org = Organization.query.get_or_404(org_id)
        expected_confirm = f"DELETE {org.name}"

        # Validate developer password
        if not current_user.check_password(password):
            return jsonify({'success': False, 'error': 'Invalid developer password'})

        # Validate confirmation text
        if confirm_text != expected_confirm:
            return jsonify({'success': False, 'error': f'Confirmation text must match exactly: "{expected_confirm}"'})

        # Security check - prevent deletion of organizations with active subscriptions
        # You might want to add additional checks here based on your business rules

        # Log the deletion attempt for security audit
        from datetime import datetime
        import logging
        logging.warning(f"ORGANIZATION DELETION: Developer {current_user.username} is deleting organization '{org.name}' (ID: {org.id}) at {datetime.now(timezone.utc)}")

        # Begin deletion process
        org_name = org.name
        users_count = len(org.users)

        # Delete all organization data in the correct order to respect foreign key constraints

        # Import all models needed for deletion
        from app.models import (
            User, Batch, BatchIngredient, BatchContainer, ExtraBatchContainer, 
            ExtraBatchIngredient, BatchTimer, Recipe, RecipeIngredient, 
            InventoryItem, Category, Role, Permission, ProductSKU, Product,
            Organization
        )
        from app.models.reservation import Reservation
        from app.models.subscription_tier import Subscription
        from app.models.user_role_assignment import UserRoleAssignment

        # Delete in proper order to avoid foreign key violations

        # 1. Delete batch-related data first (most dependent)
        ExtraBatchContainer.query.filter_by(organization_id=org_id).delete()
        ExtraBatchIngredient.query.filter_by(organization_id=org_id).delete()
        BatchContainer.query.filter_by(organization_id=org_id).delete()
        BatchIngredient.query.filter_by(organization_id=org_id).delete()
        BatchTimer.query.filter_by(organization_id=org_id).delete()

        # 2. Delete batches
        Batch.query.filter_by(organization_id=org_id).delete()

        # 3. Delete recipe ingredients, then recipes
        recipe_ids = [r.id for r in Recipe.query.filter_by(organization_id=org_id).all()]
        if recipe_ids:
            RecipeIngredient.query.filter(RecipeIngredient.recipe_id.in_(recipe_ids)).delete()
        Recipe.query.filter_by(organization_id=org_id).delete()

        # 4. Delete reservations
        Reservation.query.filter_by(organization_id=org_id).delete()

        # 5. Delete product-related data
        ProductSKU.query.filter_by(organization_id=org_id).delete()
        Product.query.filter_by(organization_id=org_id).delete()

        # 6. Delete inventory items
        InventoryItem.query.filter_by(organization_id=org_id).delete()

        # 7. Delete categories
        Category.query.filter_by(organization_id=org_id).delete()

        # 8. Delete user role assignments for org users
        org_user_ids = [u.id for u in User.query.filter_by(organization_id=org_id).all()]
        if org_user_ids:
            UserRoleAssignment.query.filter(UserRoleAssignment.user_id.in_(org_user_ids)).delete()

        # 9. Delete organization-specific roles (not system roles)
        Role.query.filter_by(organization_id=org_id, is_system_role=False).delete()

        # 10. Delete subscription
        subscription = Subscription.query.filter_by(organization_id=org_id).first()
        if subscription:
            db.session.delete(subscription)

        # 11. Delete users (this will handle the foreign key to organization)
        User.query.filter_by(organization_id=org_id).delete()

        # 12. Finally delete the organization itself
        db.session.delete(org)

        # Commit all deletions
        db.session.commit()

        # Log successful deletion
        logging.warning(f"ORGANIZATION DELETED: '{org_name}' (ID: {org_id}) successfully deleted by developer {current_user.username}. {users_count} users removed.")

        return jsonify({
            'success': True, 
            'message': f'Organization "{org_name}" and all associated data permanently deleted. {users_count} users removed.'
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"ORGANIZATION DELETION FAILED: Error deleting organization {org_id}: {str(e)}")
        return jsonify({'success': False, 'error': f'Failed to delete organization: {str(e)}'})

@developer_bp.route('/users')
@login_required
def users():
    """User management dashboard"""
    # Get all users separated by type
    customer_users = User.query.filter(User.user_type != 'developer').all()
    developer_users = User.query.filter(User.user_type == 'developer').all()

    return render_template('developer/users.html',
                         customer_users=customer_users,
                         developer_users=developer_users)

@developer_bp.route('/users/<int:user_id>/toggle-active', methods=['POST'])
@login_required
def toggle_user_active(user_id):
    """Toggle user active status"""
    user = User.query.get_or_404(user_id)

    if user.user_type == 'developer':
        flash('Cannot modify developer users', 'error')
        return redirect(url_for('developer.users'))

    user.is_active = not user.is_active
    db.session.commit()

    status = 'activated' if user.is_active else 'deactivated'
    flash(f'User {user.username} {status}', 'success')

    return redirect(url_for('developer.users'))

@developer_bp.route('/system-settings')
@require_developer_permission('system_admin')
def system_settings():
    """Legacy endpoint retained for backwards compatibility."""
    flash('System settings have moved to Feature Flags & Integrations.', 'info')
    return redirect(url_for('developer.feature_flags'))

@developer_bp.route('/feature-flags')
@login_required
@permission_required('dev.system_admin')
def feature_flags():
    """Feature flags management page"""
    from app.models.feature_flag import FeatureFlag

    # Get all feature flags from database
    db_flags = FeatureFlag.query.all()
    flag_state = {flag.key: flag.enabled for flag in db_flags}

    # Define feature flag sections and their flags
    feature_flag_sections = [
        {
            'title': 'Core business features',
            'description': 'Enable or disable the production features that every organization depends on.',
            'flags': [
                {'key': 'FEATURE_FIFO_TRACKING', 'label': 'FIFO Inventory Tracking', 'status': 'wired', 'description': 'First-in-first-out inventory tracking via the inventory adjustment service.'},
                {'key': 'FEATURE_BARCODE_SCANNING', 'label': 'Barcode Scanning', 'status': 'stub', 'description': 'Placeholder for future scanner integrations.'},
                {'key': 'FEATURE_PRODUCT_VARIANTS', 'label': 'Product Variants System', 'status': 'wired', 'description': 'Manage SKUs with variants powered by ProductService.'},
                {'key': 'FEATURE_AUTO_SKU_GENERATION', 'label': 'Auto-generate SKUs', 'status': 'wired', 'description': 'Automatically create SKU codes when products are saved.'},
                {'key': 'FEATURE_RECIPE_VARIATIONS', 'label': 'Recipe Variations', 'status': 'wired', 'description': 'Support parent/child recipe relationships.'},
                {'key': 'FEATURE_COST_TRACKING', 'label': 'Cost Tracking & Profit Margins', 'status': 'wired', 'description': 'Costing engine + FIFO/average cost calculations.'},
                {'key': 'FEATURE_EXPIRATION_TRACKING', 'label': 'Expiration Date Tracking', 'status': 'wired', 'description': 'Lot-based expiration alerts and services.'},
                {'key': 'FEATURE_BULK_OPERATIONS', 'label': 'Bulk Inventory Operations', 'status': 'wired', 'description': 'Bulk stock adjustments and checks.'},
            ],
        },
        {
            'title': 'Developer & advanced features',
            'description': 'Capabilities intended for internal tooling or staging environments.',
            'flags': [
                {'key': 'FEATURE_INVENTORY_ANALYTICS', 'label': 'Inventory Analytics (Developer)', 'status': 'wired', 'description': 'Developer-only analytics dashboard and APIs.'},
                {'key': 'FEATURE_DEBUG_MODE', 'label': 'Debug Mode', 'status': 'stub', 'description': 'Verbose logging & unsafe diagnostics.'},
                {'key': 'FEATURE_AUTO_BACKUP', 'label': 'Auto-backup System', 'status': 'stub', 'description': 'Nightly exports of core tables.'},
                {'key': 'FEATURE_CSV_EXPORT', 'label': 'CSV Export', 'status': 'wired', 'description': 'Downloadable CSV exports for reports.'},
                {'key': 'FEATURE_ADVANCED_REPORTS', 'label': 'Advanced Reports', 'status': 'stub', 'description': 'Future premium reporting suite.'},
                {'key': 'FEATURE_GLOBAL_ITEM_LIBRARY', 'label': 'Global Item Library Access', 'status': 'wired', 'description': 'Org access to the shared global inventory library.'},
            ],
        },
        {
            'title': 'Recipe Library & Marketplace',
            'description': 'Controls for sharing recipes publicly and exposing the marketplace surface.',
            'flags': [
                {'key': 'FEATURE_RECIPE_SHARING_CONTROLS', 'label': 'Recipe Sharing Controls', 'status': 'wired', 'description': 'Enable private/public/free/sale selectors on recipe forms.'},
                {'key': 'FEATURE_RECIPE_LIBRARY_NAV', 'label': 'Recipe Library Navigation', 'status': 'wired', 'description': 'Expose the public recipe library link in customer menus.'},
                {'key': 'FEATURE_RECIPE_PURCHASE_OPTIONS', 'label': 'Public Purchase Buttons', 'status': 'wired', 'description': 'Show Shopify purchase links inside the public recipe library.'},
                {'key': 'FEATURE_ORG_MARKETPLACE_DASHBOARD', 'label': 'Organization Marketplace', 'status': 'wired', 'description': 'Enable the organization-specific public marketplace dashboard and related links.'},
            ],
        },
        {
            'title': 'Notifications & integrations',
            'description': 'Toggle customer-facing communications and external app hooks.',
            'flags': [
                {'key': 'FEATURE_EMAIL_NOTIFICATIONS', 'label': 'Email Notifications', 'status': 'wired', 'description': 'Transactional + lifecycle email delivery.'},
                {'key': 'FEATURE_BROWSER_NOTIFICATIONS', 'label': 'Browser Push Notifications', 'status': 'stub', 'description': 'Web push notifications to the browser.'},
                {'key': 'FEATURE_SHOPIFY_INTEGRATION', 'label': 'Shopify Integration', 'status': 'stub', 'description': 'Future e-commerce sync pipeline.'},
                {'key': 'FEATURE_API_ACCESS', 'label': 'REST API Access', 'status': 'stub', 'description': 'Public REST API for third-party apps.'},
                {'key': 'FEATURE_OAUTH_PROVIDERS', 'label': 'OAuth Login Providers', 'status': 'wired', 'description': 'Google/Facebook sign-in support.'},
            ],
        },
        {
            'title': 'AI & forecasting experiments',
            'description': 'Aspirational features that are not yet implemented.',
            'flags': [
                {'key': 'FEATURE_AI_RECIPE_OPTIMIZATION', 'label': 'AI Recipe Optimization', 'status': 'stub', 'description': 'ML-assisted formulation suggestions.'},
                {'key': 'FEATURE_AI_DEMAND_FORECASTING', 'label': 'AI Demand Forecasting', 'status': 'stub', 'description': 'Predict demand to guide purchasing.'},
                {'key': 'FEATURE_AI_QUALITY_INSIGHTS', 'label': 'AI Quality Insights', 'status': 'stub', 'description': 'Automated quality checks & anomaly detection.'},
            ],
        },
        {
            'title': 'Public tool availability',
            'description': 'Control which calculator suites are exposed on the marketing site.',
            'flags': [
                {'key': 'TOOLS_SOAP', 'label': 'Soap Making Tools', 'status': 'wired', 'description': 'Saponification & curing calculators.'},
                {'key': 'TOOLS_CANDLES', 'label': 'Candle Making Tools', 'status': 'wired', 'description': 'Wick, wax, and fragrance load calculators.'},
                {'key': 'TOOLS_LOTIONS', 'label': 'Lotion & Cosmetic Tools', 'status': 'wired', 'description': 'Batch math for cosmetics and topicals.'},
                {'key': 'TOOLS_HERBAL', 'label': 'Herbalist Tools', 'status': 'wired', 'description': 'Tincture and infusion helpers.'},
                {'key': 'TOOLS_BAKING', 'label': 'Baking Tools', 'status': 'wired', 'description': 'Recipe scaling for bakers & confectioners.'},
            ],
        },
    ]

    return render_template(
        'developer/feature_flags.html',
        feature_flag_sections=feature_flag_sections,
        flag_state=flag_state,
        breadcrumb_items=[
            {'label': 'Developer Dashboard', 'url': url_for('developer.dashboard')},
            {'label': 'Feature Flags'}
        ],
    )

@developer_bp.route('/global-items')
@login_required
def global_items_admin():
    """Developer admin page for managing Global Items"""
    # Get filter parameters
    item_type = request.args.get('type', '').strip()
    category_filter = request.args.get('category', '').strip()
    search_query = request.args.get('search', '').strip()

    # Build base query (exclude archived)
    query = GlobalItem.query.filter(GlobalItem.is_archived != True)

    # Filter by item type if specified
    if item_type:
        query = query.filter(GlobalItem.item_type == item_type)

    # Filter by ingredient category name if specified (join via ingredient_category_id)
    if category_filter and item_type == 'ingredient':
        from app.models.category import IngredientCategory
        query = query.join(
            IngredientCategory, GlobalItem.ingredient_category_id == IngredientCategory.id
        ).filter(IngredientCategory.name == category_filter)

    # Add search functionality across name and aliases
    if search_query:
        term = f"%{search_query}%"
        try:
            # Prefer alias table when available
            from sqlalchemy import or_, exists, and_
            _alias_tbl = db.Table('global_item_alias', db.metadata, autoload_with=db.engine)
            query = query.filter(
                or_(
                    GlobalItem.name.ilike(term),
                    exists().where(and_(_alias_tbl.c.global_item_id == GlobalItem.id, _alias_tbl.c.alias.ilike(term)))
                )
            )
        except Exception:
            # Fallback to name-only search
            query = query.filter(GlobalItem.name.ilike(term))

    # Pagination controls
    page = request.args.get('page', type=int) or 1
    if page < 1:
        page = 1
    per_page_options = [20, 30, 40, 50]
    per_page = request.args.get('page_size', type=int) or per_page_options[0]
    if per_page not in per_page_options:
        per_page = per_page_options[0]

    pagination = query.order_by(
        GlobalItem.item_type.asc(),
        GlobalItem.name.asc()
    ).paginate(page=page, per_page=per_page, error_out=False)
    items = pagination.items

    # Get unique ingredient categories for filter dropdown (ingredients only, global scope)
    from app.models.category import IngredientCategory
    categories = []
    try:
        categories = [
            name for (name,) in db.session.query(IngredientCategory.name)
            .join(GlobalItem, GlobalItem.ingredient_category_id == IngredientCategory.id)
            .filter(
                IngredientCategory.organization_id == None,  # global categories
                IngredientCategory.is_global_category == True,
                GlobalItem.item_type == 'ingredient'
            )
            .distinct()
            .order_by(IngredientCategory.name)
            .all()
            if name
        ]
    except Exception:
        # Safe fallback: list all global categories
        categories = [c.name for c in IngredientCategory.query.filter_by(
            organization_id=None, is_active=True, is_global_category=True
        ).order_by(IngredientCategory.name).all()]

    # Preserve filters for pagination links
    filter_params = {}
    if item_type:
        filter_params['type'] = item_type
    if category_filter:
        filter_params['category'] = category_filter
    if search_query:
        filter_params['search'] = search_query
    if per_page != per_page_options[0]:
        filter_params['page_size'] = per_page

    def build_page_url(page_number: int):
        params = dict(filter_params)
        params['page'] = page_number
        return url_for('developer.global_items_admin', **params)

    first_item_index = ((pagination.page - 1) * pagination.per_page) + 1 if pagination.total else 0
    last_item_index = min(pagination.page * pagination.per_page, pagination.total)

    return render_template(
        'developer/global_items.html',
        items=items,
        categories=categories,
        selected_type=item_type,
        selected_category=category_filter,
        search_query=search_query,
        pagination=pagination,
        per_page=per_page,
        per_page_options=per_page_options,
        filter_params=filter_params,
        build_page_url=build_page_url,
        first_item_index=first_item_index,
        last_item_index=last_item_index,
        breadcrumb_items=[
            {'label': 'Developer Dashboard', 'url': url_for('developer.dashboard')},
            {'label': 'Global Item Library'}
        ],
    )

@developer_bp.route('/global-items/<int:item_id>')
@login_required
def global_item_detail(item_id):
    item = GlobalItem.query.get_or_404(item_id)

    # Get available global ingredient categories from IngredientCategory table
    from app.models.category import IngredientCategory
    global_ingredient_categories = IngredientCategory.query.filter_by(
        organization_id=None,
        is_active=True,
        is_global_category=True
    ).order_by(IngredientCategory.name).all()

    return render_template('developer/global_item_detail.html', item=item, global_ingredient_categories=global_ingredient_categories)

@developer_bp.route('/global-items/<int:item_id>/edit', methods=['POST'])
@login_required
def global_item_edit(item_id):
    """Edit existing global item"""
    # Add CSRF protection
    from flask_wtf.csrf import validate_csrf
    try:
        validate_csrf(request.form.get('csrf_token'))
    except Exception as e:
        flash(f"CSRF validation failed: {e}", "error")
        return redirect(url_for('developer.global_item_detail', item_id=item_id))

    item = GlobalItem.query.get_or_404(item_id)

    before = {
        'name': item.name,
        'item_type': item.item_type,
        'default_unit': item.default_unit,
        'density': item.density,
        'capacity': item.capacity,
        'capacity_unit': item.capacity_unit,
        'container_material': getattr(item, 'container_material', None),
        'container_type': getattr(item, 'container_type', None),
        'container_style': getattr(item, 'container_style', None),
        'default_is_perishable': item.default_is_perishable,
        'recommended_shelf_life_days': item.recommended_shelf_life_days,
        'aliases': item.aliases,
        'recommended_usage_rate': item.recommended_usage_rate,
        'recommended_fragrance_load_pct': item.recommended_fragrance_load_pct,
        'is_active_ingredient': item.is_active_ingredient,
        'inci_name': item.inci_name,
        'protein_content_pct': item.protein_content_pct,
        'brewing_color_srm': item.brewing_color_srm,
        'brewing_potential_sg': item.brewing_potential_sg,
        'brewing_diastatic_power_lintner': item.brewing_diastatic_power_lintner,
        'fatty_acid_profile': item.fatty_acid_profile,
        'certifications': item.certifications,
    }

    # Apply edits
    item.name = request.form.get('name', item.name)
    item.item_type = request.form.get('item_type', item.item_type)
    item.default_unit = request.form.get('default_unit', item.default_unit)
    density = request.form.get('density')
    item.density = float(density) if density not in (None, '',) else None
    capacity = request.form.get('capacity')
    item.capacity = float(capacity) if capacity not in (None, '',) else None
    item.capacity_unit = request.form.get('capacity_unit', item.capacity_unit)
    # Container attributes (optional)
    try:
        item.container_material = (request.form.get('container_material') or '').strip() or None
        item.container_type = (request.form.get('container_type') or '').strip() or None
        item.container_style = (request.form.get('container_style') or '').strip() or None
        item.container_color = (request.form.get('container_color') or '').strip() or None
    except Exception:
        pass
    item.default_is_perishable = True if request.form.get('default_is_perishable') == 'on' else False
    rsl = request.form.get('recommended_shelf_life_days')
    item.recommended_shelf_life_days = int(rsl) if rsl not in (None, '',) else None
    aliases = request.form.get('aliases')  # comma-separated
    if aliases is not None:
        item.aliases = [n.strip() for n in aliases.split(',') if n.strip()]

    item.recommended_usage_rate = request.form.get('recommended_usage_rate') or None
    item.recommended_fragrance_load_pct = request.form.get('recommended_fragrance_load_pct') or None
    item.is_active_ingredient = request.form.get('is_active_ingredient') == 'on'
    item.inci_name = request.form.get('inci_name') or None

    protein = request.form.get('protein_content_pct')
    item.protein_content_pct = float(protein) if protein not in (None, '',) else None

    brewing_color = request.form.get('brewing_color_srm')
    item.brewing_color_srm = float(brewing_color) if brewing_color not in (None, '',) else None

    brewing_potential = request.form.get('brewing_potential_sg')
    item.brewing_potential_sg = float(brewing_potential) if brewing_potential not in (None, '',) else None

    brewing_dp = request.form.get('brewing_diastatic_power_lintner')
    item.brewing_diastatic_power_lintner = float(brewing_dp) if brewing_dp not in (None, '',) else None

    fatty_acid_profile_raw = request.form.get('fatty_acid_profile')
    if fatty_acid_profile_raw is not None:
        import json
        fatty_acid_profile_raw = fatty_acid_profile_raw.strip()
        if fatty_acid_profile_raw:
            try:
                item.fatty_acid_profile = json.loads(fatty_acid_profile_raw)
            except json.JSONDecodeError:
                flash('Invalid JSON for fatty acid profile. Please provide valid JSON.', 'error')
        else:
            item.fatty_acid_profile = None

    certifications_raw = request.form.get('certifications')
    if certifications_raw is not None:
        certifications = [c.strip() for c in certifications_raw.split(',') if c.strip()]
        item.certifications = certifications or None

    # Handle ingredient category - use the ID directly
    ingredient_category_id = request.form.get('ingredient_category_id', '').strip()
    if ingredient_category_id and ingredient_category_id.isdigit():
        # Verify the category exists (global scope)
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            id=int(ingredient_category_id),
            organization_id=None,
            is_global_category=True
        ).first()
        if category:
            item.ingredient_category_id = category.id
        else:
            item.ingredient_category_id = None
    else:
        item.ingredient_category_id = None

    try:
        db.session.commit()
        # Basic audit log
        import logging
        logging.info(f"GLOBAL_ITEM_EDIT: user={current_user.id} item_id={item.id} before={before} after={{'name': item.name, 'item_type': item.item_type, 'container_material': item.container_material, 'container_type': item.container_type, 'container_style': item.container_style}}")
        flash('Global item updated successfully', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating global item: {e}', 'error')

    return redirect(url_for('developer.global_item_detail', item_id=item.id))

@developer_bp.route('/global-items/<int:item_id>/stats')
@login_required
def global_item_stats_view(item_id):
    from app.services.statistics.global_item_stats import GlobalItemStatsService
    item = GlobalItem.query.get_or_404(item_id)
    stats = GlobalItemStatsService.get_rollup(item_id)
    return render_template('developer/global_item_stats.html', item=item, stats=stats)

@developer_bp.route('/reference-categories')
@login_required
def reference_categories():
    """Manage global ingredient categories"""
    # Get existing ingredient categories in global scope (ignore legacy flag)
    from app.models.category import IngredientCategory
    existing_categories = IngredientCategory.query.filter_by(
        organization_id=None,
        is_active=True,
        is_global_category=True
    ).order_by(IngredientCategory.name).all()

    categories = [cat.name for cat in existing_categories]

    # Get global items by category for counting
    global_items_by_category = {}
    category_densities = {}

    for category_obj in existing_categories:
        # Correctly filter GlobalItems using ingredient_category_id
        items = GlobalItem.query.filter_by(ingredient_category_id=category_obj.id, is_archived=False).all()
        global_items_by_category[category_obj.name] = items

        # Use the category's default density
        if category_obj.default_density:
            category_densities[category_obj.name] = category_obj.default_density

    return render_template('developer/reference_categories.html', 
                         categories=categories,
                         global_items_by_category=global_items_by_category,
                         category_densities=category_densities)

@developer_bp.route('/container-management')
@login_required
def container_management():
    """Container management page for curating materials, colors, styles"""
    # Load master lists from settings - these are the single source of truth
    curated_lists = load_curated_container_lists()

    return render_template('developer/container_management.html',
                         curated_materials=curated_lists['materials'],
                         curated_types=curated_lists['types'],
                         curated_styles=curated_lists['styles'],
                         curated_colors=curated_lists['colors'])

@developer_bp.route('/container-management/save-curated', methods=['POST'])
@login_required
def save_curated_container_lists():
    """Save curated container lists to settings.json"""
    try:
        data = request.get_json()
        curated_lists = data.get('curated_lists', {})

        # Validate the structure
        required_keys = ['materials', 'types', 'styles', 'colors']
        for key in required_keys:
            if key not in curated_lists or not isinstance(curated_lists[key], list):
                return jsonify({'success': False, 'error': f'Invalid or missing {key} list'})

        # Load current settings
        settings_file = 'settings.json'
        settings = read_json_file(settings_file, default={}) or {}

        # Update container curated lists
        if 'container_management' not in settings:
            settings['container_management'] = {}

        settings['container_management']['curated_lists'] = curated_lists

        # Save back to file
        write_json_file(settings_file, settings)

        return jsonify({'success': True, 'message': 'Curated lists saved successfully'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def load_curated_container_lists():
    """Load curated container lists from settings or return defaults with existing database values merged in"""
    settings = read_json_file('settings.json', default={}) or {}
    curated_lists = settings.get('container_management', {}).get('curated_lists', {})

    if curated_lists and all(key in curated_lists for key in ['materials', 'types', 'styles', 'colors']):
        return curated_lists

    # First time setup: merge database values with defaults
    defaults = {
        'materials': [
            'Glass', 'PET Plastic', 'HDPE Plastic', 'PP Plastic', 'Aluminum', 
            'Tin', 'Steel', 'Paperboard', 'Cardboard', 'Silicone'
        ],
        'types': [
            'Jar', 'Bottle', 'Tin', 'Tube', 'Pump Bottle', 'Spray Bottle',
            'Dropper Bottle', 'Roll-on Bottle', 'Squeeze Bottle', 'Vial'
        ],
        'styles': [
            'Boston Round', 'Straight Sided', 'Wide Mouth', 'Narrow Mouth',
            'Cobalt Blue', 'Amber', 'Clear', 'Frosted'
        ],
        'colors': [
            'Clear', 'Amber', 'Cobalt Blue', 'Green', 'White', 'Black',
            'Frosted', 'Silver', 'Gold'
        ]
    }

    # Get existing values from database and merge with defaults
    try:
        from app.models.global_item import GlobalItem
        from app.extensions import db

        # Get existing materials
        materials = db.session.query(GlobalItem.container_material)\
            .filter(GlobalItem.container_material.isnot(None))\
            .distinct().all()
        existing_materials = [m[0] for m in materials if m[0] and m[0] not in defaults['materials']]

        # Get existing types
        types = db.session.query(GlobalItem.container_type)\
            .filter(GlobalItem.container_type.isnot(None))\
            .distinct().all()
        existing_types = [t[0] for t in types if t[0] and t[0] not in defaults['types']]

        # Get existing styles
        styles = db.session.query(GlobalItem.container_style)\
            .filter(GlobalItem.container_style.isnot(None))\
            .distinct().all()
        existing_styles = [s[0] for s in styles if s[0] and s[0] not in defaults['styles']]

        # Get existing colors
        colors = db.session.query(GlobalItem.container_color)\
            .filter(GlobalItem.container_color.isnot(None))\
            .distinct().all()
        existing_colors = [c[0] for c in colors if c[0] and c[0] not in defaults['colors']]

        # Merge and sort
        defaults['materials'].extend(existing_materials)
        defaults['materials'] = sorted(list(set(defaults['materials'])))

        defaults['types'].extend(existing_types)
        defaults['types'] = sorted(list(set(defaults['types'])))

        defaults['styles'].extend(existing_styles)
        defaults['styles'] = sorted(list(set(defaults['styles'])))

        defaults['colors'].extend(existing_colors)
        defaults['colors'] = sorted(list(set(defaults['colors'])))

    except Exception:
        pass  # Use defaults if database query fails

    return defaults

@developer_bp.route('/system-statistics')
@login_required
def system_statistics():
    """System-wide statistics dashboard"""
    from app.services.statistics import AnalyticsDataService

    force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
    stats = AnalyticsDataService.get_system_overview(force_refresh=force_refresh)

    return render_template('developer/system_statistics.html', stats=stats)

@developer_bp.route('/billing-integration')
@login_required
def billing_integration():
    """Billing integration management"""
    return render_template('developer/billing_integration.html')

@developer_bp.route('/reference-categories/add', methods=['POST'])
@login_required
def add_reference_category():
    """Add a new global ingredient category"""
    try:
        data = request.get_json()
        category_name = data.get('name', '').strip()
        default_density = data.get('default_density', None)

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Check if category already exists
        from app.models.category import IngredientCategory
        existing = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None
        ).first()

        if existing:
            return jsonify({'success': False, 'error': 'Category already exists'})

        # Create new ingredient category
        new_category = IngredientCategory(
            name=category_name,
            is_global_category=True,
            organization_id=None,
            is_active=True,
            default_density=default_density if isinstance(default_density, (int, float)) else None
        )

        db.session.add(new_category)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Category "{category_name}" added successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/delete', methods=['POST'])
@login_required
def delete_reference_category():
    """Delete a global ingredient category"""
    try:
        data = request.get_json()
        category_name = data.get('name', '').strip()

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Find the category
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None
        ).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Count items using this category
        items_count = GlobalItem.query.filter_by(
            ingredient_category_id=category.id, # Use the correct foreign key
            is_archived=False
        ).count()

        if items_count > 0:
            return jsonify({
                'success': False, 
                'error': f'Cannot delete category. {items_count} active items are using this category.'
            })

        # Delete the category
        db.session.delete(category)
        db.session.commit()

        return jsonify({'success': True, 'message': f'Category "{category_name}" deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/update-density', methods=['POST'])
@login_required
def update_category_density():
    """Update the default density for a global ingredient category"""
    try:
        data = request.get_json()
        category_name = data.get('category', '').strip()
        density = data.get('density')

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Find the category
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(
            name=category_name,
            organization_id=None
        ).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Update the category's default density
        try:
            density_value = float(density) if density is not None else None
        except (TypeError, ValueError):
            return jsonify({'success': False, 'error': 'Invalid density value'}), 400

        if density_value is not None and density_value >= 0: # Allow 0 density
            category.default_density = density_value

            # Optionally update items that don't have specific densities
            items = GlobalItem.query.filter_by(ingredient_category_id=category.id, is_archived=False).all()
            for item in items:
                if item.density is None or item.density == 0:
                    item.density = density

        db.session.commit()

        return jsonify({
            'success': True, 
            'message': f'Density updated for category "{category_name}"',
            'density': category.default_density
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/reference-categories/calculate-density', methods=['POST'])
@login_required
def calculate_category_density():
    """Calculate average density for a category based on its items"""
    try:
        data = request.get_json()
        category_name = data.get('category', '').strip()

        if not category_name:
            return jsonify({'success': False, 'error': 'Category name is required'})

        # Get the category object to find its ID
        from app.models.category import IngredientCategory
        category = IngredientCategory.query.filter_by(name=category_name, organization_id=None).first()

        if not category:
            return jsonify({'success': False, 'error': 'Category not found'})

        # Get all items in this category with valid densities
        items = GlobalItem.query.filter_by(ingredient_category_id=category.id, is_archived=False).all()
        densities = [item.density for item in items if item.density is not None and item.density > 0]

        if not densities:
            return jsonify({
                'success': False, 
                'error': 'No items with valid density values found in this category'
            })

        calculated_density = sum(densities) / len(densities)

        return jsonify({
            'success': True, 
            'calculated_density': calculated_density,
            'items_count': len(densities),
            'message': f'Calculated density: {calculated_density:.3f} g/ml from {len(densities)} items'
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/global-items/create', methods=['GET', 'POST'])
@login_required
def create_global_item():
    """Create a new global item"""

    def render_form(form_data=None):
        from app.models.category import IngredientCategory
        global_ingredient_categories = IngredientCategory.query.filter_by(
            organization_id=None,
            is_active=True,
            is_global_category=True
        ).order_by(IngredientCategory.name).all()

        return render_template(
            'developer/create_global_item.html',
            global_ingredient_categories=global_ingredient_categories,
            form_data=form_data or {}
        )

    if request.method == 'POST':
        form_data = request.form
        try:
            # Extract form data
            name = form_data.get('name', '').strip()
            item_type = form_data.get('item_type', 'ingredient')
            default_unit = form_data.get('default_unit', '').strip() or None
            # Get ingredient category id from form
            ingredient_category_id_str = form_data.get('ingredient_category_id', '').strip() or None

            # Validation
            if not name:
                flash('Name is required', 'error')
                return render_form(form_data)

            # Validate ingredient_category_id
            ingredient_category_id = None
            if ingredient_category_id_str:
                if ingredient_category_id_str.isdigit():
                    # Verify the category exists and is a global ingredient category
                    from app.models.category import IngredientCategory
                    category = IngredientCategory.query.filter_by(
                        id=int(ingredient_category_id_str),
                        organization_id=None,  # Global categories are global
                        is_global_category=True
                    ).first()
                    if category:
                        ingredient_category_id = category.id
                    else:
                        flash(f'Ingredient category ID "{ingredient_category_id_str}" not found or is not a valid reference category.', 'error')
                        return render_form(form_data)
                else:
                    flash(f'Invalid Ingredient Category ID format: "{ingredient_category_id_str}"', 'error')
                    return render_form(form_data)

            # Check for duplicate
            existing = GlobalItem.query.filter_by(name=name, item_type=item_type).first()
            if existing and not existing.is_archived:
                flash(f'Global item "{name}" of type "{item_type}" already exists', 'error')
                return render_form(form_data)

            # Create new global item
            new_item = GlobalItem(
                name=name,
                item_type=item_type,
                default_unit=default_unit,
                ingredient_category_id=ingredient_category_id
            )

            # Add optional fields
            density = form_data.get('density')
            if density:
                try:
                    new_item.density = float(density)
                except ValueError:
                    flash('Invalid density value', 'error')
                    return render_form(form_data)

            capacity = form_data.get('capacity')
            if capacity:
                try:
                    new_item.capacity = float(capacity)
                except ValueError:
                    flash('Invalid capacity value', 'error')
                    return render_form(form_data)

            new_item.capacity_unit = form_data.get('capacity_unit', '').strip() or None
            # Container attributes (optional)
            try:
                new_item.container_material = (form_data.get('container_material') or '').strip() or None
                new_item.container_type = (form_data.get('container_type') or '').strip() or None
                new_item.container_style = (form_data.get('container_style') or '').strip() or None
                new_item.container_color = (form_data.get('container_color') or '').strip() or None
            except Exception:
                pass
            new_item.default_is_perishable = form_data.get('default_is_perishable') == 'on'
            new_item.is_active_ingredient = form_data.get('is_active_ingredient') == 'on'

            shelf_life = form_data.get('recommended_shelf_life_days')
            if shelf_life:
                try:
                    new_item.recommended_shelf_life_days = int(shelf_life)
                except ValueError:
                    flash('Invalid shelf life value', 'error')
                    return render_form(form_data)

            # Ingredient-specific metadata
            new_item.recommended_usage_rate = form_data.get('recommended_usage_rate', '').strip() or None
            new_item.recommended_fragrance_load_pct = form_data.get('recommended_fragrance_load_pct', '').strip() or None
            new_item.inci_name = form_data.get('inci_name', '').strip() or None

            protein_content = form_data.get('protein_content_pct', '').strip()
            if protein_content:
                try:
                    new_item.protein_content_pct = float(protein_content)
                except ValueError:
                    flash('Invalid protein content percentage', 'error')
                    return render_form(form_data)

            brewing_color = form_data.get('brewing_color_srm', '').strip()
            if brewing_color:
                try:
                    new_item.brewing_color_srm = float(brewing_color)
                except ValueError:
                    flash('Invalid brewing SRM value', 'error')
                    return render_form(form_data)

            brewing_potential = form_data.get('brewing_potential_sg', '').strip()
            if brewing_potential:
                try:
                    new_item.brewing_potential_sg = float(brewing_potential)
                except ValueError:
                    flash('Invalid brewing potential SG value', 'error')
                    return render_form(form_data)

            brewing_dp = form_data.get('brewing_diastatic_power_lintner', '').strip()
            if brewing_dp:
                try:
                    new_item.brewing_diastatic_power_lintner = float(brewing_dp)
                except ValueError:
                    flash('Invalid brewing diastatic power value', 'error')
                    return render_form(form_data)

            fatty_acid_profile_raw = form_data.get('fatty_acid_profile', '').strip()
            if fatty_acid_profile_raw:
                import json
                try:
                    new_item.fatty_acid_profile = json.loads(fatty_acid_profile_raw)
                except json.JSONDecodeError:
                    flash('Fatty acid profile must be valid JSON.', 'error')
                    return render_form(form_data)

            certifications_raw = form_data.get('certifications', '').strip()
            if certifications_raw:
                new_item.certifications = [c.strip() for c in certifications_raw.split(',') if c.strip()]

            # Handle aliases (comma-separated)
            aliases_raw = form_data.get('aliases', '').strip()
            if aliases_raw:
                new_item.aliases = [n.strip() for n in aliases_raw.split(',') if n.strip()]

            db.session.add(new_item)
            db.session.commit()

            # Emit event
            try:
                from app.services.event_emitter import EventEmitter
                from flask_login import current_user
                # Resolve category name for telemetry
                category_name = None
                if ingredient_category_id:
                    from app.models.category import IngredientCategory
                    cat_obj = db.session.get(IngredientCategory, ingredient_category_id)
                    category_name = cat_obj.name if cat_obj else None
                EventEmitter.emit(
                    event_name='global_item_created',
                    properties={
                        'name': name,
                        'item_type': item_type,
                        'ingredient_category': category_name
                    },
                    user_id=getattr(current_user, 'id', None),
                    entity_type='global_item',
                    entity_id=new_item.id
                )
            except Exception:
                pass

            flash(f'Global item "{name}" created successfully', 'success')
            return redirect(url_for('developer.global_item_detail', item_id=new_item.id))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating global item: {str(e)}', 'error')
            return render_form(form_data)

    return render_form()

@developer_bp.route('/global-items/<int:item_id>/delete', methods=['POST'])
@login_required
def delete_global_item(item_id):
    """Delete a global item, handling organization inventory disconnection"""
    try:
        data = request.get_json()
        confirm_name = data.get('confirm_name', '').strip()
        force_delete = data.get('force_delete', False)

        item = GlobalItem.query.get_or_404(item_id)

        # Validate confirmation
        if confirm_name != item.name:
            return jsonify({
                'success': False, 
                'error': f'Confirmation text must match exactly: "{item.name}"'
            })

        # Check for connected inventory items
        from app.models.inventory import InventoryItem
        connected_items = InventoryItem.query.filter_by(global_item_id=item.id).all()

        if connected_items and not force_delete:
            # Return info about connected items for user decision
            org_names = list(set([inv_item.organization.name for inv_item in connected_items if inv_item.organization]))
            return jsonify({
                'success': False,
                'requires_confirmation': True,
                'connected_count': len(connected_items),
                'organizations': org_names,
                'message': f'This global item is connected to {len(connected_items)} inventory items across {len(org_names)} organizations. These will be disconnected and become organization-owned items.'
            })

        # Proceed with deletion
        item_name = item.name
        connected_count = len(connected_items)

        # Default behavior: soft-delete (archive) the global item
        if not force_delete:
            from datetime import datetime
            item.is_archived = True
            item.archived_at = datetime.now(timezone.utc)
            item.archived_by = current_user.id
            db.session.commit()
        else:
            # Hard delete: Disconnect all inventory items (set global_item_id to NULL and ownership='org')
            for inv_item in connected_items:
                inv_item.global_item_id = None
                try:
                    inv_item.ownership = 'org'
                except Exception:
                    pass
            # Delete the global item
            db.session.delete(item)
            db.session.commit()

        # Log the deletion for audit purposes
        import logging
        logging.warning(f"GLOBAL_ITEM_DELETED: Developer {current_user.username} deleted global item '{item_name}' (ID: {item_id}). {connected_count} inventory items disconnected and converted to organization-owned.")

        # Emit event
        try:
            from app.services.event_emitter import EventEmitter
            EventEmitter.emit(
                event_name='global_item_deleted' if force_delete else 'global_item_archived',
                properties={'name': item_name, 'connected_count': connected_count},
                user_id=getattr(current_user, 'id', None),
                entity_type='global_item',
                entity_id=item_id
            )
        except Exception:
            pass

        if not force_delete:
            return jsonify({
                'success': True,
                'message': f'Global item "{item_name}" archived successfully.'
            })
        else:
            return jsonify({
                'success': True,
                'message': f'Global item "{item_name}" deleted successfully. {connected_count} connected inventory items converted to organization-owned items.'
            })

    except Exception as e:
        db.session.rollback()
        import logging
        logging.error(f"GLOBAL_ITEM_DELETE_FAILED: Error deleting global item {item_id}: {str(e)}")
        return jsonify({
            'success': False, 
            'error': f'Failed to delete global item: {str(e)}'
        })

@developer_bp.route('/inventory-analytics')
@login_required
def inventory_analytics_stub():
    """Developer inventory analytics (feature-flagged)."""
    from flask import current_app
    enabled = current_app.config.get('FEATURE_INVENTORY_ANALYTICS', False)
    if not enabled:
        flash('Inventory analytics is not enabled for this environment.', 'info')
        return redirect(url_for('developer.dashboard'))
    return render_template(
        'developer/inventory_analytics.html',
        breadcrumb_items=[
            {'label': 'Developer Dashboard', 'url': url_for('developer.dashboard')},
            {'label': 'Inventory Analytics'}
        ]
    )

# Inventory Analytics API Endpoints
@developer_bp.route('/api/inventory-analytics/metrics')
@login_required
def api_inventory_analytics_metrics():
    """Get key inventory analytics metrics"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        return jsonify(AnalyticsDataService.get_inventory_metrics(force_refresh=force_refresh))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@developer_bp.route('/api/inventory-analytics/top-items')
@login_required
def api_inventory_analytics_top_items():
    """Get top items by usage across organizations"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        items = AnalyticsDataService.get_top_global_items(force_refresh=force_refresh)
        return jsonify({'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@developer_bp.route('/api/inventory-analytics/spoilage')
@login_required
def api_inventory_analytics_spoilage():
    """Get spoilage analysis by item"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        items = AnalyticsDataService.get_spoilage_analysis(force_refresh=force_refresh)
        return jsonify({'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@developer_bp.route('/api/inventory-analytics/data-quality')
@login_required
def api_inventory_analytics_data_quality():
    """Get data quality metrics for global items"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        return jsonify(AnalyticsDataService.get_data_quality_summary(force_refresh=force_refresh))
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@developer_bp.route('/api/inventory-analytics/recent-activity')
@login_required
def api_inventory_analytics_recent_activity():
    """Get recent inventory activity across all organizations"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        activities = AnalyticsDataService.get_recent_inventory_activity(force_refresh=force_refresh)
        return jsonify({'activities': activities})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@developer_bp.route('/api/inventory-analytics/items-list')
@login_required
def api_inventory_analytics_items_list():
    """Get list of global items for selection"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        items = AnalyticsDataService.get_inventory_item_options(force_refresh=force_refresh)
        return jsonify({'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@developer_bp.route('/api/inventory-analytics/cost-distribution/<int:item_id>')
@login_required
def api_inventory_analytics_cost_distribution(item_id):
    """Get cost distribution for a specific global item"""
    from app.services.statistics import AnalyticsDataService

    try:
        force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
        distribution = AnalyticsDataService.get_cost_distribution(
            item_id, force_refresh=force_refresh
        )
        return jsonify(distribution)
    except Exception as e:
        return jsonify({'error': str(e)}), 500




# ===================== Integrations & Launch Checklist =====================

@developer_bp.route('/integrations')
@login_required
def integrations_checklist():
    """Comprehensive integrations and launch checklist (developer only)."""
    from flask import current_app
    import os, re
    from app.services.email_service import EmailService
    from app.models.subscription_tier import SubscriptionTier

    def _env_or_config_value(key):
        """Read latest value from environment, falling back to Flask config snapshot."""
        value = os.environ.get(key)
        if value not in (None, ''):
            return value
        return current_app.config.get(key)

    # Email provider status
    email_provider = (current_app.config.get('EMAIL_PROVIDER') or 'smtp').lower()
    email_configured = EmailService.is_configured()
    email_keys = {
        'SMTP': bool(current_app.config.get('MAIL_SERVER')),
        'SendGrid': bool(current_app.config.get('SENDGRID_API_KEY')),
        'Postmark': bool(current_app.config.get('POSTMARK_SERVER_TOKEN')),
        'Mailgun': bool(current_app.config.get('MAILGUN_API_KEY') and current_app.config.get('MAILGUN_DOMAIN')),
    }

    # Stripe status
    stripe_secret = _env_or_config_value('STRIPE_SECRET_KEY')
    stripe_publishable = _env_or_config_value('STRIPE_PUBLISHABLE_KEY')
    stripe_webhook_secret = _env_or_config_value('STRIPE_WEBHOOK_SECRET')
    tiers_count = SubscriptionTier.query.count()
    stripe_status = {
        'secret_key_present': bool(stripe_secret),
        'publishable_key_present': bool(stripe_publishable),
        'webhook_secret_present': bool(stripe_webhook_secret),
        'tiers_configured': tiers_count > 0,
    }

    # Core environment & secrets
    env_core = {
        'FLASK_ENV': os.environ.get('FLASK_ENV', 'development'),
        'SECRET_KEY_present': bool(os.environ.get('FLASK_SECRET_KEY') or current_app.config.get('SECRET_KEY')),
        'LOG_LEVEL': current_app.config.get('LOG_LEVEL', 'WARNING'),
    }

    # Database info
    uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    def _mask_url(u: str) -> str:
        try:
            return re.sub(r"//[^:@/]+:[^@/]+@", "//****:****@", u)
        except Exception:
            return u
    backend = 'PostgreSQL' if uri.startswith('postgres') else ('SQLite' if 'sqlite' in uri else 'Other')
    source = 'fallback'
    if 'sqlite' not in uri:
        if os.environ.get('DATABASE_INTERNAL_URL'):
            source = 'DATABASE_INTERNAL_URL'
        elif os.environ.get('DATABASE_URL'):
            source = 'DATABASE_URL'
        else:
            source = 'config'
    db_info = {
        'uri': _mask_url(uri),
        'backend': backend,
        'source': source,
        'DATABASE_INTERNAL_URL_present': bool(os.environ.get('DATABASE_INTERNAL_URL')),
        'DATABASE_URL_present': bool(os.environ.get('DATABASE_URL')),
    }

    # Cache / rate limit info
    cache_info = {
        'RATELIMIT_STORAGE_URL': current_app.config.get('RATELIMIT_STORAGE_URL', 'memory://'),
        'REDIS_URL_present': bool(os.environ.get('REDIS_URL')),
    }

    # OAuth & marketplace
    oauth_status = {
        'GOOGLE_OAUTH_CLIENT_ID_present': bool(current_app.config.get('GOOGLE_OAUTH_CLIENT_ID')),
        'GOOGLE_OAUTH_CLIENT_SECRET_present': bool(current_app.config.get('GOOGLE_OAUTH_CLIENT_SECRET')),
    }
    whop_status = {
        'WHOP_API_KEY_present': bool(current_app.config.get('WHOP_API_KEY')),
        'WHOP_APP_ID_present': bool(current_app.config.get('WHOP_APP_ID')),
    }

    def _env_status(key, *, allow_config=False, config_key=None):
        raw = os.environ.get(key)
        if raw not in (None, ''):
            return True, 'env'
        if allow_config:
            cfg_val = current_app.config.get(config_key or key)
            if cfg_val not in (None, ''):
                return True, 'config'
        return False, 'missing'

    def _make_item(key, description, *, required=True, recommended=None, allow_config=False, config_key=None, is_secret=False, note=None):
        present, source = _env_status(key, allow_config=allow_config, config_key=config_key)
        return {
            'key': key,
            'description': description,
            'present': present,
            'source': source,
            'required': required,
            'recommended': recommended,
            'is_secret': is_secret,
            'note': note,
            'allow_config': allow_config,
        }

    launch_env_sections = [
        {
            'title': 'Core Runtime & Platform',
            'note': 'Set these to lock the app into production mode and disable development conveniences before launch.',
            'section_items': [
                _make_item('FLASK_ENV', 'Runtime environment. Use "production" for live deployments.', required=True, recommended='production', allow_config=True, config_key='ENV'),
                _make_item('FLASK_SECRET_KEY', 'Flask session signing secret. Use a random 32+ character string.', required=True, allow_config=True, config_key='SECRET_KEY', is_secret=True),
                _make_item('FLASK_DEBUG', 'Flask debug flag. Must stay false/unset in production.', required=False, recommended='false / unset'),
                _make_item('LOG_LEVEL', 'Application logging level. Use INFO or WARN in production.', required=True, recommended='INFO', allow_config=True),
            ]
        },
        {
            'title': 'Database & Persistence',
            'note': 'Configure a managed Postgres instance before launch. Disable automatic table creation in production.',
            'section_items': [
                _make_item('DATABASE_INTERNAL_URL', 'Primary database connection string (preferred in production).', required=True, is_secret=True, note='Provision managed Postgres (Render, Supabase, RDS). Copy the full postgres:// URI with username, password, host, and database name.'),
                _make_item('DATABASE_URL', 'Fallback database connection string (used if internal URL not set).', required=False, is_secret=True, note='Render automatically injects DATABASE_URL. Mirror DATABASE_INTERNAL_URL when both exist.'),
                _make_item('SQLALCHEMY_DISABLE_CREATE_ALL', 'Disable db.create_all() safety switch. Set to 1 in production.', required=False, recommended='1 (enabled)', note='Prevents accidental schema drift on boot.'),
                _make_item('SQLALCHEMY_ENABLE_CREATE_ALL', 'Local dev-only override to run db.create_all(). Leave unset in production.', required=False, recommended='unset'),
                _make_item('SQLALCHEMY_POOL_SIZE', 'SQLAlchemy connection pool size.', required=False, recommended='5', allow_config=True, note='Keep small on starter instances; raise only when CPU/memory allows more concurrency.'),
                _make_item('SQLALCHEMY_MAX_OVERFLOW', 'Burst connections beyond the base pool.', required=False, recommended='5', allow_config=True, note='Match this to pool size for predictable ceilings.'),
                _make_item('SQLALCHEMY_POOL_TIMEOUT', 'Seconds to wait for a pooled connection before erroring.', required=False, recommended='5', allow_config=True, note='Lower values surface saturation symptoms quickly.'),
                _make_item('SQLALCHEMY_POOL_RECYCLE', 'Seconds before idle connections recycle.', required=False, recommended='1800', allow_config=True),
            ]
        },
        {
            'title': 'Caching & Rate Limits',
            'note': 'Provision a managed Redis instance (Render Redis, Upstash, ElastiCache). Use a single connection URI for caching, Flask sessions, and rate limiting.',
            'section_items': [
                _make_item(
                    'REDIS_URL',
                    'Redis connection string for caching, sessions, and rate limit storage.',
                    required=True,
                    recommended='redis://',
                    note='Create the service, copy the full tls-enabled URI, and paste it into your environment. The rate limiter automatically reuses this value—no separate variable needed.',
                    allow_config=True,
                ),
                _make_item('SESSION_TYPE', 'Server-side session backend. Must be "redis" in production.', required=True, recommended='redis', allow_config=True, note='Set to redis so user sessions live in Redis instead of cookies.'),
            ],
        },
        {
            'title': 'Security & Networking',
            'note': 'Enable proxy awareness and security headers behind your load balancer. Set ENABLE_PROXY_FIX=true (or TRUST_PROXY_HEADERS=true on legacy platforms), adjust PROXY_FIX_X_* counts for each proxy hop (defaults assume one), and leave DISABLE_SECURITY_HEADERS unset.',
            'section_items': [
                _make_item('ENABLE_PROXY_FIX', 'Wrap the app in Werkzeug ProxyFix when behind a load balancer.', required=True, recommended='true (production)'),
                _make_item('TRUST_PROXY_HEADERS', 'Legacy toggle equivalent to ENABLE_PROXY_FIX for older configs.', required=False, recommended='true (only if ENABLE_PROXY_FIX is unavailable)'),
                _make_item('PROXY_FIX_X_FOR', 'Number of X-Forwarded-For headers to trust.', required=False, recommended='1 (single proxy)'),
                _make_item('PROXY_FIX_X_PROTO', 'Number of X-Forwarded-Proto headers to trust.', required=False, recommended='1 (single proxy)'),
                _make_item('PROXY_FIX_X_HOST', 'Number of X-Forwarded-Host headers to trust.', required=False, recommended='1'),
                _make_item('PROXY_FIX_X_PORT', 'Number of X-Forwarded-Port headers to trust.', required=False, recommended='1'),
                _make_item('PROXY_FIX_X_PREFIX', 'Number of X-Forwarded-Prefix headers to trust.', required=False, recommended='0 unless using path prefixes'),
                _make_item('FORCE_SECURITY_HEADERS', 'Force security headers even when the app thinks it is non-production (e.g., staging).', required=False, recommended='true (staging) / unset (production)'),
                _make_item('DISABLE_SECURITY_HEADERS', 'Emergency kill-switch for security headers. Leave unset in production.', required=False, recommended='unset'),
                _make_item('CONTENT_SECURITY_POLICY', 'Override default Content-Security-Policy header with a custom policy.', required=False, allow_config=True, note='Leave unset to use the built-in CSP; override only after testing.'),
                _make_item('SECURITY_HEADERS', 'JSON/YAML mapping to override default security headers.', required=False, note='Optional advanced override for header values. Configure through app config if preferred.'),
            ]
        },
        {
            'title': 'Email & Notifications',
            'note': 'Configure exactly one provider for transactional email and confirm DNS (SPF/DKIM).',
            'section_items': [
                _make_item('EMAIL_PROVIDER', 'Email provider selector: smtp | sendgrid | postmark | mailgun.', required=True, allow_config=True, recommended='sendgrid / postmark / mailgun', note='Match this to the provider you configure below.'),
                _make_item('MAIL_SERVER', 'SMTP server hostname.', required=False, note='Only needed for the SMTP option (e.g., smtp.sendgrid.net).'),
                _make_item('MAIL_PORT', 'SMTP port (587 for TLS, 465 for SSL).', required=False),
                _make_item('MAIL_USE_TLS', 'Enable STARTTLS for SMTP.', required=False, recommended='true'),
                _make_item('MAIL_USE_SSL', 'Enable implicit TLS for SMTP.', required=False, recommended='false unless port 465'),
                _make_item('MAIL_USERNAME', 'SMTP username / login.', required=False, is_secret=True),
                _make_item('MAIL_PASSWORD', 'SMTP password or app-specific password.', required=False, is_secret=True),
                _make_item('MAIL_DEFAULT_SENDER', 'Default from-address for outbound email.', required=True, allow_config=True, recommended='verified domain address', note='Use a domain whose DNS records include SPF/DKIM.'),
                _make_item('SENDGRID_API_KEY', 'SendGrid API key (if using SendGrid).', required=False, is_secret=True, note='Create in SendGrid dashboard → Email API → API Keys.'),
                _make_item('POSTMARK_SERVER_TOKEN', 'Postmark server token (if using Postmark).', required=False, is_secret=True, note='Copy from Postmark Server Settings → API Tokens.'),
                _make_item('MAILGUN_API_KEY', 'Mailgun REST API key (if using Mailgun).', required=False, is_secret=True, note='Available in Mailgun dashboard under API Security.'),
                _make_item('MAILGUN_DOMAIN', 'Mailgun sending domain (if using Mailgun).', required=False, note='Use the exact domain you verified in Mailgun.'),
            ]
        },
        {
            'title': 'Billing & Payments',
            'note': 'Switch to live Stripe keys and webhook secrets before you charge real customers.',
            'section_items': [
                _make_item('STRIPE_SECRET_KEY', 'Stripe secret key (live).', required=True, is_secret=True, note='Stripe Dashboard → Developers → API Keys → Secret key. Use the live key, not test, for production.'),
                _make_item('STRIPE_PUBLISHABLE_KEY', 'Stripe publishable key (live).', required=True, is_secret=True, note='Paired with the secret key for Checkout/Elements.'),
                _make_item('STRIPE_WEBHOOK_SECRET', 'Stripe webhook signing secret.', required=True, is_secret=True, note='Create a webhook endpoint pointing to /billing/webhooks/stripe then copy the signing secret.'),
            ]
        },
        {
            'title': 'AI Studio & BatchBot',
            'note': 'These keys and knobs control Batchley (paid bot), the public help bot, and refill economics. Set limits here so support knows how refills/unlimited tiers behave.',
            'section_items': [
                _make_item('FEATURE_BATCHBOT', 'Master toggle for exposing Batchley endpoints.', required=False, recommended='true', allow_config=True, note='Set to false to completely disable the AI copilot and its routes.'),
                _make_item('GOOGLE_AI_API_KEY', 'Gemini API key used by Batchley + public bot.', required=True, is_secret=True, note='Create in Google AI Studio → API Key. Rotate if compromised.'),
                _make_item('GOOGLE_AI_DEFAULT_MODEL', 'Fallback Gemini model when per-bot overrides are unset.', required=False, recommended='gemini-1.5-flash'),
                _make_item('GOOGLE_AI_BATCHBOT_MODEL', 'Model used by the paid Batchley bot.', required=False, recommended='gemini-1.5-pro'),
                _make_item('GOOGLE_AI_PUBLICBOT_MODEL', 'Model used by the public help bot.', required=False, recommended='gemini-1.5-flash'),
                _make_item('GOOGLE_AI_ENABLE_SEARCH', 'Enable Google Search grounding for Batchley.', required=False, recommended='true'),
                _make_item('GOOGLE_AI_ENABLE_FILE_SEARCH', 'Enable File Search (uploaded docs) for prompts.', required=False, recommended='true'),
                _make_item('GOOGLE_AI_SEARCH_TOOL', 'Search tool identifier sent to Gemini.', required=False, recommended='google_search'),
                _make_item('BATCHBOT_REQUEST_TIMEOUT_SECONDS', 'Gemini request timeout. Increase for long-running jobs.', required=False, recommended='45'),
                _make_item('BATCHBOT_DEFAULT_MAX_REQUESTS', 'Base allowance per org per window. Use -1 for unlimited tiers.', required=True, note='Tier-specific overrides live on Subscription Tiers → Max BatchBot Requests.'),
                _make_item('BATCHBOT_REQUEST_WINDOW_DAYS', 'Length of the usage window (credits reset after this).', required=True, recommended='30'),
                _make_item('BATCHBOT_CHAT_MAX_MESSAGES', 'Max chat-only prompts per window (guides informal Q&A usage).', required=False, recommended='60', note='60 prompts ≈ 15 conversations (4 prompts each). Raise for higher tiers or set -1 for unlimited.'),
                _make_item('BATCHBOT_COST_PER_MILLION_INPUT', 'Reference compute cost for inbound tokens (USD).', required=False, recommended='0.35'),
                _make_item('BATCHBOT_COST_PER_MILLION_OUTPUT', 'Reference compute cost for outbound tokens (USD).', required=False, recommended='0.53'),
                _make_item('BATCHBOT_SIGNUP_BONUS_REQUESTS', 'Promo credits granted to new orgs (stack with tier limit).', required=False, recommended='20'),
                _make_item('BATCHBOT_REFILL_LOOKUP_KEY', 'Stripe price lookup key for the default Batchley refill add-on.', required=False, recommended='batchbot_refill_100', note='Must match the Stripe price ID tied to the refill add-on. Used when generating one-time checkout links.'),
            ]
        },
        {
            'title': 'OAuth & Marketplace',
            'note': 'Optional integrations for single sign-on and marketplace licensing.',
            'section_items': [
                _make_item('GOOGLE_OAUTH_CLIENT_ID', 'Google OAuth 2.0 client ID for login.', required=False, is_secret=True),
                _make_item('GOOGLE_OAUTH_CLIENT_SECRET', 'Google OAuth 2.0 client secret.', required=False, is_secret=True),
                _make_item('WHOP_API_KEY', 'Whop API key (if using Whop for licensing).', required=False, is_secret=True),
                _make_item('WHOP_APP_ID', 'Whop app ID (if using Whop).', required=False, is_secret=True),
            ]
        },
        {
            'title': 'Maintenance & Utilities',
            'note': 'Rarely used toggles for seeding or one-off maintenance scripts.',
            'section_items': [
                _make_item('SEED_PRESETS', 'Enable preset data seeding during migrations (internal tooling).', required=False, recommended='unset'),
            ]
        }
    ]

    config_matrix = []
    for section in launch_env_sections:
        for item in section['section_items']:
            config_matrix.append(
                {
                    'category': section['title'],
                    'key': item['key'],
                    'present': item['present'],
                    'required': item['required'],
                    'recommended': item.get('recommended'),
                    'description': item['description'],
                    'note': item.get('note'),
                    'is_secret': item.get('is_secret', False),
                    'source': item.get('source', 'missing'),
                }
            )

    rate_limiters = [
        {
            'endpoint': 'GET/POST /auth/login',
            'limit': '30/minute',
            'source': 'app/blueprints/auth/routes.py::login',
            'notes': 'Primary credential-based login form.',
        },
        {
            'endpoint': 'GET /auth/oauth/google',
            'limit': '20/minute',
            'source': 'app/blueprints/auth/routes.py::oauth_google',
            'notes': 'Google OAuth initiation endpoint.',
        },
        {
            'endpoint': 'GET /auth/oauth/callback',
            'limit': '30/minute',
            'source': 'app/blueprints/auth/routes.py::oauth_callback',
            'notes': 'OAuth callback handler (Google).',
        },
        {
            'endpoint': 'GET /auth/callback',
            'limit': '30/minute',
            'source': 'app/blueprints/auth/routes.py::oauth_callback_compat',
            'notes': 'Legacy alias for the OAuth callback.',
        },
        {
            'endpoint': 'GET/POST /auth/signup',
            'limit': '20/minute',
            'source': 'app/blueprints/auth/routes.py::signup',
            'notes': 'Self-serve signup + tier selection.',
        },
        {
            'endpoint': 'POST /billing/webhooks/stripe',
            'limit': '60/minute',
            'source': 'app/blueprints/billing/routes.py::stripe_webhook',
            'notes': 'Stripe webhook ingestion endpoint.',
        },
        {
            'endpoint': 'GLOBAL DEFAULT',
            'limit': '200/day + 50/hour',
            'source': 'app/extensions.py::limiter',
            'notes': 'Applies per remote IP when no route-level override exists.',
        },
    ]

    # Feature flags
    feature_flags = {
        'FEATURE_INVENTORY_ANALYTICS': bool(current_app.config.get('FEATURE_INVENTORY_ANALYTICS', False)),
        'TOOLS_SOAP': bool(current_app.config.get('TOOLS_SOAP', True)),
        'TOOLS_CANDLES': bool(current_app.config.get('TOOLS_CANDLES', True)),
        'TOOLS_LOTIONS': bool(current_app.config.get('TOOLS_LOTIONS', True)),
        'TOOLS_HERBAL': bool(current_app.config.get('TOOLS_HERBAL', True)),
        'TOOLS_BAKING': bool(current_app.config.get('TOOLS_BAKING', True)),
    }

    # Logging/PII
    logging_status = {
        'LOG_LEVEL': current_app.config.get('LOG_LEVEL', 'INFO'),
        'LOG_REDACT_PII': current_app.config.get('LOG_REDACT_PII', True),
    }

    # POS/Shopify (stub)
    shopify_status = {
        'status': 'stubbed',
        'notes': 'POS/Shopify integration is stubbed. Enable later via a dedicated adapter.'
    }

    return render_template(
        'developer/integrations.html',
        email_provider=email_provider,
        email_configured=email_configured,
        email_keys=email_keys,
        stripe_status=stripe_status,
        tiers_count=tiers_count,
        feature_flags=feature_flags,
        logging_status=logging_status,
        shopify_status=shopify_status,
        env_core=env_core,
        db_info=db_info,
        cache_info=cache_info,
        oauth_status=oauth_status,
        whop_status=whop_status,
        rate_limiters=rate_limiters,
        config_matrix=config_matrix,
    )


@developer_bp.route('/integrations/test-email', methods=['POST'])
@login_required
def integrations_test_email():
    """Send a test email to current user's email if configured."""
    try:
        from app.services.email_service import EmailService
        if not EmailService.is_configured():
            return jsonify({'success': False, 'error': 'Email is not configured'}), 400
        recipient = getattr(current_user, 'email', None)
        if not recipient:
            return jsonify({'success': False, 'error': 'Current user has no email address'}), 400
        subject = 'BatchTrack Test Email'
        html_body = '<p>This is a test email from BatchTrack Integrations Checklist.</p>'
        ok = EmailService._send_email(recipient, subject, html_body, 'This is a test email from BatchTrack Integrations Checklist.')
        if ok:
            return jsonify({'success': True, 'message': f'Test email sent to {recipient}'})
        return jsonify({'success': False, 'error': 'Failed to send email'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/test-stripe', methods=['POST'])
@login_required
def integrations_test_stripe():
    """Test Stripe connectivity (no secrets shown)."""
    try:
        from app.services.billing_service import BillingService
        ok = BillingService.ensure_stripe()
        if not ok:
            return jsonify({'success': False, 'error': 'Stripe secret not configured'}), 400
        # Try a harmless list call
        import stripe
        try:
            prices = stripe.Price.list(limit=1)
            return jsonify({'success': True, 'message': f"Stripe reachable. Prices found: {len(prices.data)}"})
        except Exception as e:
            return jsonify({'success': False, 'error': f"Stripe API error: {e}"}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/stripe-events', methods=['GET'])
@login_required
def integrations_stripe_events():
    """Summarize recent Stripe webhook events from the database."""
    try:
        from app.models.stripe_event import StripeEvent
        total = StripeEvent.query.count()
        last = StripeEvent.query.order_by(StripeEvent.id.desc()).first()
        payload = {'total_events': total}
        if last:
            payload.update({
                'last_event_id': last.event_id,
                'last_event_type': last.event_type,
                'last_status': last.status,
                'last_processed_at': getattr(last, 'processed_at', None).isoformat() if getattr(last, 'processed_at', None) else None
            })
        return jsonify({'success': True, 'data': payload})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/feature-flags/set', methods=['POST'])
@login_required
def integrations_set_feature_flags():
    """Set feature flags via AJAX"""
    from app.models.feature_flag import FeatureFlag
    from app.extensions import db

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        # Update feature flags in database
        for flag_key, enabled in data.items():
            feature_flag = FeatureFlag.query.filter_by(key=flag_key).first()
            if feature_flag:
                feature_flag.enabled = bool(enabled)
            else:
                # Create new feature flag if it doesn't exist
                feature_flag = FeatureFlag(
                    key=flag_key,
                    enabled=bool(enabled),
                    description=f"Auto-created flag for {flag_key}"
                )
                db.session.add(feature_flag)

        db.session.commit()

        return jsonify({'success': True})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@developer_bp.route('/integrations/check-webhook', methods=['GET'])
@login_required
def integrations_check_webhook():
    """Verify webhook endpoint HTTP reachability (does not validate Stripe signature)."""
    try:
        from flask import current_app
        import requests
        base = request.host_url.rstrip('/')
        # Use our known webhook path
        url = f"{base}/billing/webhooks/stripe"
        # Send a harmless GET to see if the route 405s (expected) or 404s
        try:
            resp = requests.get(url, timeout=5)
            status = resp.status_code
            message = 'reachable (method not allowed expected)' if status == 405 else f'response {status}'
            return jsonify({'success': True, 'url': url, 'status': status, 'message': message})
        except Exception as e:
            return jsonify({'success': False, 'url': url, 'error': f'Connection error: {e}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@developer_bp.route('/analytics-catalog')
@login_required
def analytics_catalog():
    """Developer catalog of analytics data points and domains."""
    from flask import current_app
    from app.services.statistics import AnalyticsCatalogService, AnalyticsCatalogError

    try:
        domains = AnalyticsCatalogService.get_domains()
        summary = AnalyticsCatalogService.get_summary()
    except AnalyticsCatalogError as exc:
        current_app.logger.error("Failed to build analytics catalog: %s", exc, exc_info=True)
        flash('Unable to load the analytics catalog right now. Please try again later.', 'error')
        domains = []
        summary = None

    return render_template('developer/analytics_catalog.html', domains=domains, catalog_summary=summary)


# ProductCategory management
@developer_bp.route('/product-categories')
@login_required
def product_categories():
    categories = ProductCategory.query.order_by(ProductCategory.name.asc()).all()
    return render_template('developer/categories/list.html', categories=categories)


@developer_bp.route('/product-categories/new', methods=['GET', 'POST'])
@login_required
def create_product_category():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        is_typically_portioned = True if request.form.get('is_typically_portioned') == 'on' else False
        sku_name_template = (request.form.get('sku_name_template') or '').strip() or None
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('developer.create_product_category'))
        exists = ProductCategory.query.filter(ProductCategory.name.ilike(name)).first()
        if exists:
            flash('Category name already exists', 'error')
            return redirect(url_for('developer.create_product_category'))
        cat = ProductCategory(name=name, is_typically_portioned=is_typically_portioned, sku_name_template=sku_name_template)
        from app.extensions import db
        db.session.add(cat)
        db.session.commit()
        flash('Product category created', 'success')
        return redirect(url_for('developer.product_categories'))
    return render_template('developer/categories/new.html')


@developer_bp.route('/product-categories/<int:cat_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_product_category(cat_id):
    cat = ProductCategory.query.get_or_404(cat_id)
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        is_typically_portioned = True if request.form.get('is_typically_portioned') == 'on' else False
        sku_name_template = (request.form.get('sku_name_template') or '').strip() or None
        if not name:
            flash('Name is required', 'error')
            return redirect(url_for('developer.edit_product_category', cat_id=cat_id))
        conflict = ProductCategory.query.filter(ProductCategory.id != cat_id).filter(ProductCategory.name.ilike(name)).first()
        if conflict:
            flash('Another category with that name exists', 'error')
            return redirect(url_for('developer.edit_product_category', cat_id=cat_id))
        cat.name = name
        cat.is_typically_portioned = is_typically_portioned
        cat.sku_name_template = sku_name_template
        from app.extensions import db
        db.session.commit()
        flash('Product category updated', 'success')
        return redirect(url_for('developer.product_categories'))
    return render_template('developer/categories/edit.html', category=cat)


@developer_bp.route('/product-categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_product_category(cat_id):
    from app.extensions import db
    cat = ProductCategory.query.get_or_404(cat_id)
    # Prevent delete if in use
    from app.models.product import Product
    from app.models.recipe import Recipe
    in_use = db.session.query(Product).filter_by(category_id=cat.id).first() or db.session.query(Recipe).filter_by(category_id=cat.id).first()
    if in_use:
        flash('Cannot delete category that is used by products or recipes', 'error')
        return redirect(url_for('developer.product_categories'))
    db.session.delete(cat)
    db.session.commit()
    flash('Product category deleted', 'success')
    return redirect(url_for('developer.product_categories'))

@developer_bp.route('/waitlist-statistics')
@require_developer_permission('system_admin')
def waitlist_statistics():
    """View waitlist statistics and data"""
    from app.services.statistics import AnalyticsDataService

    force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
    stats = AnalyticsDataService.get_waitlist_statistics(force_refresh=force_refresh)
    return render_template(
        'developer/waitlist_statistics.html',
        waitlist_data=stats.get('entries', []),
        total_signups=stats.get('total', 0),
        generated_at=stats.get('generated_at'),
    )

# Customer support filtering routes
@developer_bp.route('/select-org/<int:org_id>')
@login_required
def select_organization(org_id):
    """Select an organization to view as developer (customer support)"""
    org = Organization.query.get_or_404(org_id)
    session['dev_selected_org_id'] = org_id
    flash(f'Now viewing data for: {org.name} (Customer Support Mode)', 'info')
    return redirect(url_for('app_routes.dashboard'))



# Modified routes for developer masquerading
@developer_bp.route('/view-as-organization/<int:org_id>')
@login_required
@permission_required('dev.system_admin')
def view_as_organization(org_id):
    """Set session to view as a specific organization (customer support)"""
    organization = Organization.query.get_or_404(org_id)

    # Clear any existing masquerade data first
    session.pop('dev_selected_org_id', None)
    session.pop('dev_masquerade_context', None)

    # Store in session for middleware to use
    session['dev_selected_org_id'] = org_id
    session['dev_masquerade_context'] = {
        'org_name': organization.name,
        'started_at': TimezoneUtils.utc_now().isoformat()
    }
    session.permanent = True

    flash(f'Now viewing as organization: {organization.name}. Landing on user dashboard.', 'info')
    return redirect(url_for('app_routes.dashboard'))  # Land on user dashboard, not org dashboard

@developer_bp.route('/clear-organization-filter')
@login_required
@permission_required('dev.system_admin')
def clear_organization_filter():
    """Clear the organization filter and return to developer view"""
    org_name = None
    if 'dev_selected_org_id' in session:
        org_id = session['dev_selected_org_id']
        org = db.session.get(Organization, org_id)
        org_name = org.name if org else 'Unknown'

    # Clear all masquerade-related session data
    session.pop('dev_selected_org_id', None)
    session.pop('dev_masquerade_context', None)

    # Also clear any organization-scoped data that might be cached
    session.pop('dismissed_alerts', None)  # Clear dismissed alerts from customer view

    message = f'Cleared organization filter and session data'
    if org_name:
        message += f' (was viewing: {org_name})'

    flash(message, 'info')
    return redirect(url_for('developer.dashboard'))


# API endpoints for dashboard
@developer_bp.route('/api/stats')
@login_required
def api_stats():
    """API endpoint for dashboard statistics"""
    from app.services.statistics import AnalyticsDataService

    force_refresh = (request.args.get('refresh') or '').lower() in ('1', 'true', 'yes')
    overview = AnalyticsDataService.get_system_overview(force_refresh=force_refresh)

    tier_counts = overview.get('tiers') or {}

    stats = {
        'organizations': {
            'total': overview.get('total_organizations', 0),
            'active': overview.get('active_organizations', 0),
            'by_tier': tier_counts
        },
        'users': {
            'total': overview.get('total_users', 0),
            'active': overview.get('active_users', 0)
        }
    }

    # Subscription tier breakdown - get from SubscriptionTier model
    from app.models.subscription_tier import SubscriptionTier
    # Ensure all known tiers appear even if zero (to maintain API contract)
    for tier in ['exempt', 'free', 'solo', 'team', 'enterprise']:
        stats['organizations']['by_tier'].setdefault(tier, 0)

    return jsonify(stats)

# Enhanced User Management API Endpoints

@developer_bp.route('/api/user/<int:user_id>')
@login_required
def get_user_details(user_id):
    """Get detailed user information for editing"""
    try:
        user = User.query.get_or_404(user_id)

        # Don't allow developers to edit other developer accounts through this endpoint
        if user.user_type != 'developer':
            user_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'user_type': user.user_type,
                'is_active': user.is_active,
                'organization_id': user.organization_id,
                'organization_name': user.organization.name if user.organization else None,
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
                'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None
            }
            return jsonify({'success': True, 'user': user_data})
        else:
            return jsonify({'success': False, 'error': 'Cannot edit developer users through this endpoint'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/developer-user/<int:user_id>')
@login_required
def get_developer_user_details(user_id):
    """Get detailed developer user information for editing"""
    try:
        user = User.query.get_or_404(user_id)

        if user.user_type == 'developer':
            # Get available developer roles
            from app.models.developer_role import DeveloperRole
            from app.models.user_role_assignment import UserRoleAssignment

            all_dev_roles = DeveloperRole.query.filter_by(is_active=True).all()
            user_role_assignments = UserRoleAssignment.query.filter_by(
                user_id=user_id,
                is_active=True
            ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()

            assigned_role_ids = [assignment.developer_role_id for assignment in user_role_assignments]

            roles_data = []
            for role in all_dev_roles:
                roles_data.append({
                    'id': role.id,
                    'name': role.name,
                    'description': role.description,
                    'assigned': role.id in assigned_role_ids
                })

            user_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'phone': user.phone,
                'is_active': user.is_active,
                'last_login': user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else None,
                'created_at': user.created_at.strftime('%Y-%m-%d') if user.created_at else None,
                'roles': roles_data
            }
            return jsonify({'success': True, 'user': user_data})
        else:
            return jsonify({'success': False, 'error': 'User is not a developer'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/user/update', methods=['POST'])
@login_required
def update_user():
    """Update user information"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        user = User.query.get_or_404(user_id)

        # Don't allow editing developer users through this endpoint
        if user.user_type == 'developer':
            return jsonify({'success': False, 'error': 'Cannot edit developer users through this endpoint'})

        # Update user fields
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.user_type = data.get('user_type', user.user_type)
        user.is_active = data.get('is_active', user.is_active)

        # Handle organization owner flag with single owner constraint and role transfer
        if 'is_organization_owner' in data:
            new_owner_status = data['is_organization_owner']
            transfer_role = data.get('transfer_owner_role', False)

            if new_owner_status and not user.is_organization_owner:
                # User is being made an organization owner
                # First, remove organization owner status and role from all other users in this org
                other_owners = User.query.filter(
                    User.organization_id == user.organization_id,
                    User.id != user.id,
                    User._is_organization_owner == True
                ).all()

                from app.models.role import Role
                org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()

                for other_owner in other_owners:
                    print(f"Removing owner status from user {other_owner.id} ({other_owner.username})")
                    other_owner.is_organization_owner = False
                    # Remove the organization owner role from other owners
                    if org_owner_role:
                        other_owner.remove_role(org_owner_role)

                # Now set this user as the owner and assign the role
                user.is_organization_owner = True
                print(f"Setting user {user.id} ({user.username}) as organization owner")

                # Ensure the organization owner role is assigned
                if org_owner_role:
                    user.assign_role(org_owner_role, assigned_by=current_user)
                    print(f"Assigned organization_owner role to user {user.id}")

            elif not new_owner_status and user.is_organization_owner:
                # User is being removed as organization owner
                print(f"Removing organization owner status from user {user.id} ({user.username})")
                user.is_organization_owner = False

                # Remove the organization owner role
                from app.models.role import Role
                org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
                if org_owner_role:
                    user.remove_role(org_owner_role)
                    print(f"Removed organization_owner role from user {user.id}")

        db.session.commit()

        return jsonify({'success': True, 'message': 'User updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/developer-user/update', methods=['POST'])
@login_required
def update_developer_user():
    """Update developer user information"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        user = User.query.get_or_404(user_id)

        if user.user_type != 'developer':
            return jsonify({'success': False, 'error': 'User is not a developer'})

        # Update user fields
        user.first_name = data.get('first_name', user.first_name)
        user.last_name = data.get('last_name', user.last_name)
        user.email = data.get('email', user.email)
        user.phone = data.get('phone', user.phone)
        user.is_active = data.get('is_active', user.is_active)

        # Update developer role assignments
        from app.models.user_role_assignment import UserRoleAssignment

        # Deactivate existing developer role assignments
        existing_assignments = UserRoleAssignment.query.filter_by(
            user_id=user_id,
            is_active=True
        ).filter(UserRoleAssignment.developer_role_id.isnot(None)).all()

        for assignment in existing_assignments:
            assignment.is_active = False

        # Add new role assignments
        new_role_ids = data.get('roles', [])
        for role_id in new_role_ids:
            # Check if assignment already exists
            existing = UserRoleAssignment.query.filter_by(
                user_id=user_id,
                developer_role_id=role_id
            ).first()

            if existing:
                existing.is_active = True
                existing.assigned_at = datetime.now(timezone.utc)
                existing.assigned_by = current_user.id
            else:
                new_assignment = UserRoleAssignment(
                    user_id=user_id,
                    developer_role_id=role_id,
                    assigned_by=current_user.id,
                    is_active=True
                )
                db.session.add(new_assignment)

        db.session.commit()

        return jsonify({'success': True, 'message': 'Developer user updated successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/user/reset-password', methods=['POST'])
@login_required
def reset_user_password():
    """Reset user password"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        new_password = data.get('new_password')

        if not new_password:
            return jsonify({'success': False, 'error': 'New password is required'})

        user = User.query.get_or_404(user_id)
        user.set_password(new_password)
        db.session.commit()

        return jsonify({'success': True, 'message': 'Password reset successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/user/soft-delete', methods=['POST'])
@login_required
def soft_delete_user():
    """Soft delete a user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')

        user = User.query.get_or_404(user_id)

        # Don't allow soft deleting developer users
        if user.user_type == 'developer':
            return jsonify({'success': False, 'error': 'Cannot soft delete developer users'})

        user.soft_delete(current_user)

        return jsonify({'success': True, 'message': 'User soft deleted successfully'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})



@developer_bp.route('/api/user/<int:user_id>')
@login_required
def get_user_api(user_id):
    """Get user data for management modal"""
    try:
        user = User.query.get_or_404(user_id)

        # Get the actual organization owner status
        is_org_owner = getattr(user, 'is_organization_owner', False)

        user_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'user_type': user.user_type,
            'is_organization_owner': is_org_owner,
            '_is_organization_owner': getattr(user, '_is_organization_owner', False),  # Also include the private field
            'is_active': user.is_active,
            'display_role': user.display_role,  # Include display role for additional context
            'created_at': user.created_at.strftime('%Y-%m-%d %H:%M:%S') if user.created_at else None,
            'last_login': user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else None,
            'organization': {
                'id': user.organization.id,
                'name': user.organization.name
            } if user.organization else None
        }

        # Debug logging
        print(f"API returning user {user_id} with is_organization_owner: {is_org_owner}")

        return jsonify({'success': True, 'user': user_data})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@developer_bp.route('/api/container-options')
@login_required  
def api_container_options():
    """Get curated container options for dropdowns"""
    try:
        curated_lists = load_curated_container_lists()
        return jsonify({
            'success': True,
            'options': curated_lists
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})