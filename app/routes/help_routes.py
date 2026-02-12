from flask import Blueprint, render_template, url_for

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
                "Capture your core inventory or recipe data on day one so dashboards surface real insights.",
                "Invite teammates and assign roles so everyone knows their next action in BatchTrack.",
            ],
            "details": [
                {
                    "title": "First Login Checklist",
                    "body": """
<ol>
  <li><strong>Decide your starting path.</strong> Inventory-first teams populate ingredients/containers so costs and conversions work; recipe-first teams can create formulas immediately but should link every line to inventory.</li>
  <li><strong>Follow the dashboard ribbons.</strong> The blank state surfaces “Add Inventory” and “Add Recipe” buttons, each linking back to these instructions.</li>
    <li><strong>Repeat this flow for every workspace.</strong> Keeping the experience consistent helps teammates share the same reference data.</li>
</ol>
                    """,
                },
                {
                    "title": "Invite Your Team & Set Goals",
                    "body": """
<ol>
  <li><strong>Open</strong> <em>Organization → Teammates</em> to invite coworkers and assign owner/manager roles.</li>
  <li><strong>Decide</strong> which KPIs you want to highlight first—low stock alerts, production throughput, or order readiness.</li>
  <li><strong>Use</strong> the dashboard ribbons to pin those priorities so every login reinforces the same goals.</li>
  <li><strong>Review</strong> the inline help cards in inventory, recipes, and planning for quick reminders while you work.</li>
</ol>
                    """,
                },
                {
                    "title": "Guide Teammates with Roles & Permissions",
                    "body": """
<ul>
  <li>Use <strong>Organization → Roles</strong> to define who can edit inventory, plan production, or finish batches.</li>
  <li>Owners can unlock subscription-tier features, while contributors can stay focused on the tasks they handle every day.</li>
  <li>Pair every new user with a role when they join so navigation only surfaces the workflows they need.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Blank dashboard with Add Inventory / Add Recipe CTAs",
                "Screenshot: Organization teammates list showing role assignments",
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
            "slug": "inventory-adjustments",
            "title": "Inventory Adjustments & Recounts",
            "points": [
                "Restock, spoil, recount, and manual adjustments all flow through the same drawer so FIFO lots stay accurate.",
                "Quick Adjust on the inventory list captures supplier, cost, and reason codes in seconds.",
                "Every adjustment drops a note, attachment, and audit trail entry so you can prove what changed later.",
            ],
            "details": [
                {
                    "title": "Log Every Adjustment with Context",
                    "body": """
<ul>
  <li>Select <strong>Restock</strong>, <strong>Spoil</strong>, <strong>Damage</strong>, or <strong>Recount</strong>; each option prompts for reason codes, lot, and supplier.</li>
  <li>Provide cost per unit when restocking so valuation rolls forward automatically.</li>
  <li>Add notes or attachments (photos, invoices) so auditors see exactly why the change happened.</li>
</ul>
                    """,
                },
                {
                    "title": "Use Quick Adjust from the List",
                    "body": """
<ol>
  <li>Open <em>Inventory</em>, hover a row, and choose <strong>Quick Adjust</strong>.</li>
  <li>Enter the delta (positive, negative, or zero for recount) and confirm the unit BatchTrack should apply.</li>
  <li>Submit to immediately update FIFO lots, unified history, and downstream costing.</li>
</ol>
                    """,
                },
                {
                    "title": "Audit History & Alerts",
                    "body": """
<ul>
  <li>Every adjustment writes to <em>Inventory → History</em> with timestamps, user, quantity, and cost.</li>
  <li>Combined Inventory Alerts surface repeated recounts or spoilage so you can coach teams in real time.</li>
  <li>Expiration and reservation services read the same history, keeping warnings and holds consistent.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Quick Adjust modal with restock/spoil/recount options",
                "Screenshot: Inventory history showing adjustment audit trail",
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
            "slug": "costing",
            "title": "Costing & Profitability",
            "points": [
                "Every restock records cost per unit so FIFO lots always know their value.",
                "When you finish a batch, BatchTrack captures actual ingredient, consumable, and container spend.",
                "Dashboards and exports compare planned vs actual cost so you can price SKUs with confidence.",
            ],
            "details": [
                {
                    "title": "Cost-Informed Restocks",
                    "body": """
<ol>
  <li>When adding inventory or restocking, enter supplier and cost per unit.</li>
  <li>BatchTrack updates the lot value and total quantity immediately, so subsequent deductions pull the right cost.</li>
  <li>Use supplier notes to document negotiated pricing or bulk discounts.</li>
</ol>
                    """,
                },
                {
                    "title": "Plan vs Actual Batch Costs",
                    "body": """
<ul>
  <li>PlanSnapshot holds the estimated recipe cost; the Finish Batch modal collects what really happened.</li>
  <li>Actuals roll into <em>Batch → Costing</em> so you can see ingredient, packaging, and optional labor totals.</li>
  <li>Products inherit their replenishment cost from finished batches, keeping SKU margins realistic.</li>
</ul>
                    """,
                },
                {
                    "title": "Shareable Cost Insights",
                    "body": """
<ul>
  <li>Export batch stats or inventory history when accountants need an audit trail.</li>
  <li>Use Combined Inventory Alerts to highlight items trending toward high spoilage cost.</li>
  <li>Pricing updates can be tied to these reports so sales teams always quote profitable rates.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Inventory restock form with cost per unit field",
                "Screenshot: Batch costing panel comparing plan vs actual",
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
            "slug": "labels-exports",
            "title": "Labels, INCI Sheets, & Exports",
            "points": [
                "Generate INCI, candle, baker, and lotion labels directly from any recipe.",
                "Share HTML, CSV, or PDF exports with vendors, regulators, or production partners.",
                "Public tools mirror the same exports so prospects can preview before they sign up.",
            ],
            "details": [
                {
                    "title": "Recipe-Based Exports",
                    "body": """
<ol>
  <li>Open a recipe and click <strong>Exports</strong>.</li>
  <li>Select the label or sheet you need (soap INCI, candle label, baker sheet, lotion INCI).</li>
  <li>Download as HTML for quick viewing, CSV for spreadsheets, or PDF for print-ready sharing.</li>
</ol>
                    """,
                },
                {
                    "title": "Public Tool Previews",
                    "body": """
<ul>
  <li>Prospects can visit <code>/tools</code>, draft a formula, and jump straight into the matching export.</li>
  <li>They can copy/paste label data during trials, then convert drafts into full recipes once they subscribe.</li>
  <li>Use this flow to collaborate with co-packers who only need the label data, not full app access.</li>
</ul>
                    """,
                },
                {
                    "title": "Keep SKUs & Labels in Sync",
                    "body": """
<ul>
  <li>When batches finish and restock SKUs, the exports reflect the latest ingredient list and notes.</li>
  <li>Reservation records can include label links so fulfillment teams grab the right paperwork.</li>
  <li>Store regulatory notes in recipe instructions so they appear in exports automatically.</li>
</ul>
                    """,
                },
            ],
            "gallery": [
                "Screenshot: Recipe exports menu showing INCI and label options",
                "Screenshot: Candle label PDF preview",
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
                    "title": "Turn Drafts into Ready-to-Produce Recipes",
                    "body": """
<ol>
  <li><strong>Save</strong> a draft after experimenting inside the public calculators.</li>
  <li><strong>Log in</strong> and open <em>Recipes → New Recipe</em>; BatchTrack auto-detects the draft and fills ingredients, consumables, and containers.</li>
  <li><strong>Tune</strong> instructions, notes, and yield, then move directly into production planning when you're satisfied.</li>
</ol>
                    """,
                },
                {
                    "title": "Choose the Right Plan",
                    "body": """
<ul>
  <li>Compare tiers inside <strong>Billing → Plans</strong> to align features with your production volume.</li>
  <li>Seat counts, reservations, and analytics limits are spelled out so you can scale intentionally.</li>
  <li>Invoices and usage snapshots live in the same screen, keeping finance teams informed without exporting data.</li>
</ul>
                    """,
                },
                {
                    "title": "Stay Informed & Get Help",
                    "body": """
<ul>
  <li>Use this help center plus the FAQ for day-to-day workflow questions.</li>
  <li>New feature callouts appear inline, and deeper release notes live under <em>Docs → Changelog</em>.</li>
  <li>If you need human support, submit a ticket from the in-app support link so the team sees your recent activity.</li>
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
    return render_template(
        "help/how_it_works.html",
        sections=sections,
        show_public_header=True,
        page_title="BatchTrack Help Center | How It Works",
        page_description="Learn how BatchTrack handles inventory, recipes, planning, batches, costing, products, and exports.",
        canonical_url=url_for("help_routes.help_overview", _external=True),
    )


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
        {
            "question": "How do I fix counts or recount inventory without breaking FIFO?",
            "answer": "Open Quick Adjust from the inventory list, choose restock/spoil/recount, and BatchTrack logs the change with the right cost and audit trail.",
            "link": ("Inventory Adjustments", "help_routes.help_overview", "inventory-adjustments"),
        },
        {
            "question": "Where can I see actual costing versus my plan?",
            "answer": "Enter costs during restocks, then review the Costing panel when you finish a batch to compare planned vs actual spend.",
            "link": ("Costing & Profitability", "help_routes.help_overview", "costing"),
        },
        {
            "question": "How do I export labels or INCI sheets for my SKUs?",
            "answer": "Use the recipe exports (or public tool previews) to download INCI, candle, baker, or lotion labels in HTML, CSV, or PDF.",
            "link": ("Labels & Exports", "help_routes.help_overview", "labels-exports"),
        },
    ]
    return render_template(
        "help/system_faq.html",
        faqs=faqs,
        show_public_header=True,
        page_title="BatchTrack System FAQ | Production & Inventory",
        page_description="Answers to common BatchTrack questions about setup, inventory adjustments, production planning, SKUs, and exports.",
        canonical_url=url_for("help_routes.help_faq", _external=True),
    )
