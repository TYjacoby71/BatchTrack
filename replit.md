# BatchTrack

## Overview

BatchTrack is a multi-tenant production and inventory management SaaS application designed for small-batch makers (soap makers, candle makers, artisans). The application provides batch tracking, FIFO inventory management, recipe scaling, and subscription-based organization management. Built with Flask and PostgreSQL, it follows a service-oriented architecture where each domain service has single responsibility and authority over its data.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Core Design Pattern: Service Authority Model
The application follows a strict service authority pattern where specific services are the single source of truth for their domains:
- **FIFO Service**: Authoritative for all inventory deductions using first-in-first-out logic
- **Inventory Adjustment Service**: Single source of truth for inventory changes
- **Unit Conversion Service**: Handles all unit conversions between measurement systems
- **Stock Check Service**: Real-time availability validation

**Critical Rule**: Never bypass service layers. All database operations for a domain must go through its authoritative service.

### Backend Architecture
- **Framework**: Flask 3.x with Flask-SQLAlchemy ORM
- **Database**: PostgreSQL (via psycopg2-binary)
- **Migrations**: Flask-Migrate with Alembic
- **Session Management**: Flask-Session with Redis backend
- **Authentication**: Flask-Login with Flask-Bcrypt for password hashing
- **Rate Limiting**: Flask-Limiter with per-user/IP rate limiting
- **Caching**: Flask-Caching with Redis support

### Blueprint Organization
The application uses a modular blueprint architecture with three categories:
1. **Core Blueprints**: auth, admin, developer, inventory, recipes, batches, organization, billing, onboarding, settings, timers, expiration, conversion, production-planning
2. **API Blueprints**: public API, main API, drawer API
3. **Route Blueprints**: app routes, legal, bulk stock, fault log, tag manager, global library, recipe library, waitlist, help, tools, exports, products

### Multi-Tenancy Model
- Organizations are the primary tenant boundary
- All user data is scoped to `organization_id`
- Subscription tiers control feature access
- Developer users have cross-organization access for platform administration

### Key Domain Models
- **Organization**: Tenant container with subscription status
- **User**: Belongs to organization with role-based permissions
- **Recipe**: Production formulas with ingredient relationships
- **Batch**: Production runs linked to recipes with status tracking
- **InventoryItem**: Stock items with FIFO lot tracking
- **Product**: Finished goods with SKU management
- **GlobalItem**: Shared ingredient library across organizations

### Permission System
- Role-based access control with hierarchical permissions
- Subscription tier-based feature gating
- Developer-specific permissions for platform tools

### Timezone Handling
**Critical**: Storage timezone differs from display timezone. All timestamps stored in UTC; display conversions happen at the presentation layer using `TimezoneUtils`.

## External Dependencies

### Database
- **PostgreSQL**: Primary data store (production)
- **SQLite**: Local development fallback
- **Redis**: Session storage, caching, and rate limiting backend

### Third-Party Services
- **Stripe**: Payment processing and subscription management via webhooks
- **Whop**: Alternative payment/subscription provider
- **Google Auth**: OAuth authentication provider
- **OpenAI**: AI features for recipe optimization (optional feature flag)
- **Google Generative AI**: Additional AI capabilities

### Infrastructure
- **Gunicorn**: WSGI server with gevent workers for production
- **Flask-Mail**: Email notifications (optional feature)

### Feature Flags
The application uses JSON-based feature flags (`settings.json`) to toggle functionality:
- FIFO tracking, barcode scanning, recipe variations
- Cost tracking, expiration tracking
- AI features, integrations, marketplace features
- Craft-specific tools (soap, candles, lotions, baking)

### Environment Configuration
- `FLASK_ENV`: Environment mode (development/staging/production)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection for sessions/cache
- `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`: Payment processing
- `SECRET_KEY`: Flask session encryption