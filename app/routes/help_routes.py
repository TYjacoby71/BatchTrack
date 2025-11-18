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
