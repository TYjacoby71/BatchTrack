from flask import Blueprint, render_template

help_bp = Blueprint("help_routes", __name__)


@help_bp.route("/help")
@help_bp.route("/help/how-it-works")
def help_overview():
    sections = [
        {
            "slug": "getting-started",
            "title": "Getting Started",
            "points": [
                "Follow the first-login checklist to choose whether you add inventory or recipes first.",
                "Provision your workspace (install deps, migrate, seed) so every teammate sees the same baseline data.",
                "Set up organizations, roles, and permissions so each user only sees what their subscription tier allows.",
            ],
            "details": [
                {
                    "title": "First Login Checklist",
                    "body": """
<ol>
  <li><strong>Decide your starting path.</strong> Inventory-first teams populate ingredients/containers so costs and conversions work; recipe-first teams can create formulas immediately but should link every line to inventory.</li>
  <li><strong>Follow the dashboard ribbons.</strong> The blank state surfaces “Add Inventory” and “Add Recipe” buttons, each linking back to these instructions.</li>
  <li><strong>Repeat this flow for staging/preview.</strong> Seed each environment the same way so teammates always see consistent data.</li>
</ol>
                    """,
                },
                {
                    "title": "Provision & Seed the Workspace",
                    "body": """
<ol>
  <li><code>pip install -r requirements.txt</code> to install dependencies.</li>
  <li>Run <code>flask db upgrade</code> to apply migrations.</li>
  <li>Seed core data with <code>flask init-production</code> (or individual commands like <code>flask seed-units</code>).</li>
  <li>Set <code>FLASK_APP=run.py</code> (or use the Makefile) and start the server with <code>python run.py</code>.</li>
  <li>Document any feature flags/env vars so future teammates can recreate the environment quickly.</li>
</ol>
                    """,
                },
                {
                    "title": "Manage Organizations, Roles, and Permissions",
                    "body": """
<ul>
  <li>Developers never receive an <code>organization_id</code>; org owners and team members always do.</li>
  <li>Create custom roles from <strong>Organization → Dashboard</strong>, assign permissions, and invite teammates.</li>
  <li>Guard UI/actions with <code>has_permission(...)</code> and <code>has_subscription_feature(...)</code> so tiers stay respected.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Blank dashboard with Add Inventory / Add Recipe CTAs",
                "Screenshot: Provisioning checklist or CLI output after seeding",
            ],
        },
        {
            "slug": "inventory",
            "title": "Inventory & Global Items",
            "points": [
                "Use the global drawer when adding inventory to keep identity data clean—global items are curated, org items stay editable.",
                "From the inventory list you can quick-adjust, open the modal for stats/history/lots, or edit to recount and recast.",
                "Assign custom densities, categories, and ownership when needed; every restock/deduction routes through the Inventory Adjustment Service.",
            ],
            "details": [
                {
                    "title": "Global vs Org-Owned Items",
                    "body": """
<p>The add-inventory drawer searches the global library. Selecting a global item locks identity fields (name, default unit, density) so every org speaks the same language. Typing past the suggestions creates an org-owned item that you can edit freely.</p>
                    """,
                },
                {
                    "title": "Step-by-Step: Add Inventory",
                    "body": """
<ol>
  <li><strong>Open</strong> <em>Inventory → Add Inventory Item</em> or use the quick-add drawer on the list page.</li>
  <li><strong>Search & select</strong> a global item or confirm creation of a new org-owned record. The banner shows whether it’s “Global-Locked” or “Org-Owned.”</li>
  <li><strong>Complete the form:</strong> category, default unit, density override, perishable defaults, quantity, cost, supplier, lot, expiration, and storage location.</li>
  <li><strong>Save.</strong> The confirmation modal offers an immediate restock dialog so you can add the first FIFO lot right away.</li>
</ol>
                    """,
                },
                {
                    "title": "Manage Inventory from the List Page",
                    "body": """
<ol>
  <li><strong>Quick Adjust</strong> opens a compact restock/spoil/recount form that still logs through Inventory Adjustment Service.</li>
  <li><strong>Detail modal</strong> shows overview, stats, history, and lots tabs with buttons to restock or deduct.</li>
  <li><strong>Edit screen</strong> unlocks recounts, recasts (adjust by a measured delta), density overrides, category assignments, and ownership toggles.</li>
  <li><strong>History & attachments</strong> keep every adjustment auditable with supplier docs or COAs.</li>
</ol>
                    """,
                },
                {
                    "title": "Restock, Deduct, and Audit",
                    "body": """
<ul>
  <li>All adjustments call Inventory Adjustment Service, which logs history + FIFO lots.</li>
  <li>Drawer payloads explain missing density/unit data so users can resolve issues without leaving the flow.</li>
  <li>FIFO lots show remaining quantity, expiration, and cost so audits are straightforward.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Inventory quick-add drawer highlighting global suggestions",
                "Screenshot: Inventory list modal showing stats/history/lots tabs",
                "Screenshot: Inventory edit form with recount/recast controls",
            ],
        },
        {
            "slug": "recipes",
            "title": "Recipes & Variations",
            "points": [
                "Create recipes with ingredients, consumables, and container shortlists; store SOPs so they surface during planning.",
                "Understand bulk vs portioned yields—bulk is container-defined (lotions, candles), portioned is self-defined (bars of soap).",
                "Clone and unlock recipes to manage variations without rebuilding everything from scratch.",
            ],
            "details": [
                {
                    "title": "Step-by-Step: Create a Recipe",
                    "body": """
<ol>
  <li><strong>Open</strong> <em>Recipes → New Recipe</em> and choose a production category (soap, candle, lotion, etc.).</li>
  <li><strong>Set basics:</strong> name, description, yield, unit, and whether the batch is <em>Bulk</em> (container-defined) or <em>Portioned</em> (self-defined items like bars).</li>
  <li><strong>Add lines:</strong> link ingredients to inventory/global items, log consumables, and shortlist containers/packaging that this recipe actually uses.</li>
  <li><strong>Store instructions/SOPs</strong> so they appear in PlanSnapshot and batch records.</li>
  <li><strong>Save</strong> and run a stock check from Production Planning when you’re ready to make a batch.</li>
</ol>
                    """,
                },
                {
                    "title": "Variations, Clones, and Unlocking",
                    "body": """
<ul>
  <li><strong>Clone</strong> a recipe to create new scents, colors, or volumes without rebuilding lines.</li>
  <li><strong>Variations</strong> inherit containers and instructions but can override ingredients or yields.</li>
  <li><strong>Unlock</strong> a recipe to edit it (actions are logged for traceability).</li>
  <li><strong>Container shortlist</strong> ensures only relevant vessels appear during planning (no lipstick tubes when you’re making lotion).</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Recipe form highlighting ingredients/consumables/containers tabs",
                "Screenshot: Variation list showing clones vs parents",
            ],
        },
        {
            "slug": "planning",
            "title": "Planning & Batches",
            "points": [
                "Plan Production builds an immutable PlanSnapshot, including intermediate components and target SKUs.",
                "Container auto-selection converts projected yield into vessel capacity; you can override it manually at any time.",
                "Batch screens track timers, extras, notes, costing, and the finish/cancel/fail workflows that control deductions.",
            ],
            "details": [
                {
                    "title": "Plan Config Options",
                    "body": """
<ul>
  <li><strong>Batch type:</strong> choose <em>Product</em> (outputs sellable SKUs) or <em>Intermediate</em> (restocks component inventory like dough or syrups).</li>
  <li><strong>Intermediate ingredients:</strong> add component batches that scale alongside the main batch.</li>
  <li><strong>Product tab:</strong> pick the SKU/variant this batch will replenish.</li>
  <li><strong>Containers required:</strong> auto-selection fills enough vessels to hold 100% of projected yield; you can disable auto and select manually.</li>
  <li><strong>Unit alignment:</strong> ensure recipe yield units match container capacity units for precise auto-fill math.</li>
  <li><strong>Stock check:</strong> must pass (or be explicitly bypassed) before starting the batch; drawer modals help resolve shortages.</li>
</ul>
                    """,
                },
                {
                    "title": "Plan & Start Production",
                    "body": """
<ol>
  <li>Open <em>Production Planning</em> from the recipe page or sidebar.</li>
  <li>Select the recipe/variation, choose batch type, and set the scale factor.</li>
  <li>Configure intermediates, target SKUs, and container selections.</li>
  <li>Run the stock check; fix shortages or bypass with intent.</li>
  <li>Review the PlanSnapshot preview and submit to start the batch.</li>
</ol>
                    """,
                },
                {
                    "title": "Batch In-Progress Page",
                    "body": """
<ul>
  <li><strong>Header metrics</strong> show projected vs actual yields, portions, and container counts.</li>
  <li><strong>Timers</strong> track curing/proofing tasks and alert the dashboard.</li>
  <li><strong>Extras</strong> deduct additional ingredients/consumables/containers mid-run with reason codes.</li>
  <li><strong>Notes & attachments</strong> capture QC observations.</li>
  <li><strong>Costing pane</strong> breaks down ingredients, packaging, and (optional) labor.</li>
</ul>
                    """,
                },
                {
                    "title": "Finish, Cancel, or Fail",
                    "body": """
<ul>
  <li><strong>Finish:</strong> prompts for actual yield, container counts, portion data, and how inventory/product SKUs should be replenished.</li>
  <li><strong>Cancel:</strong> rolls back all deductions and deletes batch rows.</li>
  <li><strong>Fail:</strong> ends the batch but keeps deductions (for waste tracking) and requires a note.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Production Planning config card (batch type, intermediates, containers)",
                "Screenshot: Stock check modal with drawer prompt",
                "Screenshot: Batch in-progress page showing timers/extras",
                "Screenshot: Finish batch modal highlighting container confirmation",
            ],
        },
        {
            "slug": "products",
            "title": "Products, SKUs, & Reservations",
            "points": [
                "Define products and variants, then link batches to restock SKUs automatically.",
                "Reservations hold finished goods for wholesale/subscription orders so you never oversell.",
                "Store external IDs (Shopify/Square) on SKUs to keep ecommerce channels in sync.",
            ],
            "details": [
                {
                    "title": "Create Product Variants",
                    "body": """
<ol>
  <li>Open <em>Products → All Products</em> and create/select a base product.</li>
  <li>Add variants (size, scent, color) and map each to the containers/ingredients it consumes.</li>
  <li>Set reorder targets/thresholds so alerts fire before you run out.</li>
  <li>Link batches to variants when finishing production so finished goods automatically restock the right SKU.</li>
  <li>Use the reservations tab to hold finished goods for specific orders.</li>
</ol>
                    """,
                },
                {
                    "title": "SKUs & Sales System Hooks",
                    "body": """
<ul>
  <li>A SKU = Product + Variant + Package Size + Quantity.</li>
  <li>When a batch finishes as “Product,” SKU inventory increases and ecommerce integrations can sync.</li>
  <li>Store Shopify/Square IDs on SKUs so connectors update the correct listings.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Product detail with variants tab",
                "Screenshot: SKU builder showing external ID field",
                "Screenshot: Reservations list for a product",
            ],
        },
        {
            "slug": "public-tools",
            "title": "Public Tools & Help",
            "points": [
                "Share the /tools calculators so prospects can draft recipes before signing up.",
                "Drafts persist through /tools/draft and prefill /recipes/new once users authenticate.",
                "Use this page and the FAQ as the public knowledge base until the full onboarding tour ships.",
            ],
            "details": [
                {
                    "title": "Draft Recipes via Public Tools",
                    "body": """
<ol>
  <li>Visit <code>/tools</code> and pick a calculator (soap, candle, lotion, herbal, baker).</li>
  <li>Use the inline typeahead to pull global ingredients/containers and enter quantities.</li>
  <li>Click <strong>Save to BatchTrack</strong>; the payload posts to <code>/tools/draft</code>.</li>
  <li>After signup or login, <code>/recipes/new</code> detects the draft and pre-populates every line.</li>
</ol>
                    """,
                },
                {
                    "title": "Integrate via APIs & Webhooks",
                    "body": """
<ul>
  <li>Authenticated APIs rely on Flask-Login sessions; developer-only endpoints support org impersonation.</li>
  <li>Drawer endpoints (<code>/api/drawer-actions/... </code>) return the data needed to resolve density/unit issues.</li>
  <li>Public APIs expose unit listings, unit conversion, and global-item search for calculators.</li>
</ul>
                    """,
                },
                {
                    "title": "Billing, Tiers, and Feature Flags",
                    "body": """
<ul>
  <li>Stripe webhook updates the Billing Snapshot; Billing Service enforces feature access and seat counts.</li>
  <li>Use <code>has_subscription_feature(...)</code> to hide premium functionality in templates.</li>
  <li>Developer feature flags live in <code>settings.json</code> so experiments stay scoped.</li>
</ul>
                    """,
                },
                {
                    "title": "Deployments, Migrations, and Monitoring",
                    "body": """
<ul>
  <li>Every schema change needs an Alembic migration—never bypass services.</li>
  <li>Middleware enforces security headers and logs anonymous hits; monitor logs plus <code>docs/changelog</code>.</li>
  <li>Update this help page and the FAQ whenever flows change so onboarding stays current.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Public tools landing cards",
                "Screenshot: Draft saved modal prompting signup/login",
            ],
        },
    ]
    return render_template("help/how_it_works.html", sections=sections)


@help_bp.route("/help/system-faq")
def help_faq():
    faqs = [
        {
            "question": "What should I do right after signing up?",
            "answer": "Open the dashboard, decide whether you want to add inventory or a recipe first, and follow the in-app ribbon that links to the first-login checklist.",
            "link": ("First Login Checklist", "help_routes.help_overview", "first-login"),
        },
        {
            "question": "How do I add ingredients, containers, consumables, or packaging?",
            "answer": "Use the inventory drawer to select a global item or create an org-owned item, then capture quantity, cost, and storage details.",
            "link": ("Add Inventory", "help_routes.help_overview", "inventory-creation"),
        },
        {
            "question": "How do I plan and start a batch?",
            "answer": "Use Production Planning to select recipes, configure intermediate ingredients, auto-fill containers, and submit the PlanSnapshot.",
            "link": ("Plan & Start Production", "help_routes.help_overview", "plan-production"),
        },
        {
            "question": "Where do I see timers, extras, and final yields?",
            "answer": "The batch in-progress screen keeps projected vs actual data, timers, extras, and the finish modal in one place.",
            "link": ("Batch In-Progress", "help_routes.help_overview", "batch-in-progress"),
        },
        {
            "question": "How do products, SKUs, and reservations work?",
            "answer": "Define variants on the product page, link batches to SKUs, and hold finished goods for wholesale or subscription orders.",
            "link": ("Product Variants & SKUs", "help_routes.help_overview", "product-variants"),
        },
        {
            "question": "Can prospects try BatchTrack without an account?",
            "answer": "Yes—share the public tools so they can draft recipes, then save to BatchTrack when they’re ready to create an account.",
            "link": ("Public Tools", "help_routes.help_overview", "public-tools"),
        },
    ]
    return render_template("help/system_faq.html", faqs=faqs)
