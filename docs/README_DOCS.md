# BatchTrack Documentation Index

## Developer Guides

### 📋 New Feature Development
1. **[Error Message Protocol](ERROR_MESSAGE_PROTOCOL.md)** - Complete guide to error handling
   - How to add new error messages
   - Error handling patterns
   - Scalability considerations
   - Testing your errors

2. **[Route Development Guide](ROUTE_DEVELOPMENT_GUIDE.md)** - Template for creating new routes
   - Quick start template
   - HTML vs API route patterns
   - Validation patterns
   - Security checklist

3. **[Quick Reference Card](QUICK_REFERENCE_ERRORS.md)** - Cheat sheet
   - Copy-paste examples
   - Common patterns
   - Status codes
   - Testing snippets

### 🎯 Quick Links

**Need to add a new route?**
→ Start with [Route Development Guide](ROUTE_DEVELOPMENT_GUIDE.md)

**Need to add error messages?**
→ See [Error Message Protocol](ERROR_MESSAGE_PROTOCOL.md)

**Need quick examples?**
→ Check [Quick Reference Card](QUICK_REFERENCE_ERRORS.md)

### 📦 Key Files

- `app/utils/error_messages.py` - All user-facing messages
- `app/utils/api_responses.py` - Standardized API responses
- `app/templates/layout.html` - Flash message rendering

### 🔍 Code Examples

See existing features for reference:
- `app/blueprints/inventory/routes.py` - Complete CRUD example
- `app/blueprints/batches/routes.py` - Complex business logic
- `app/blueprints/api/` - API-only routes

---

## Other Documentation

For other docs, check the main `/docs` directory.
