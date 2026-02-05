# Add-ons & Entitlements

## Synopsis
Add-ons extend subscription tiers with optional entitlements. They can grant **RBAC permissions** (`permission_name`) or toggle **feature logic** (`function_key`) without permissions.

---

## Glossary
- **Add-on**: Optional entitlement that can be purchased or included by a tier.
- **Permission add-on**: Add-on that grants an RBAC permission when active.
- **Function-key add-on**: Add-on enforced in service logic (no RBAC permission).

---

## 1. Data Model
- **Addon** (`app/models/addon.py`): catalog entry with `permission_name` and/or `function_key`.
- **OrganizationAddon**: active purchases by organization (Stripe/Whop metadata).
- **SubscriptionTier**: owns `allowed_addons` and `included_addons` relationships.

---

## 2. Entitlement Types
### Permission-based add-ons (`permission_name`)
- Grant RBAC entitlements when:
  - **Included** on the tier, or
  - **Purchased** by the organization (`OrganizationAddon.active=True`).
- These permissions are **hidden from the tier permission picker** until the add-on is selected.
- When displayed, they are **read-only** (checked + disabled) to prevent drift.

### Function-key add-ons (`function_key`)
- No RBAC permission; enforced in service logic (example: retention).
- The add-on still appears under **Allowed/Included** on tier forms for entitlement tracking.

---

## 3. Allowed vs Included
- **Allowed add-on**: available for purchase, no permission granted until active purchase.
- **Included add-on**: granted automatically for all orgs on the tier (billing bypassed).

---

## 4. Update Scripts (Idempotent)
- `flask update-permissions` → refresh permissions from consolidated JSON.
- `flask update-addons` → seed add-ons and **backfill tier entitlements**.
- `flask update-subscription-tiers` → update tier limits and static tier metadata.

Backfill rules (run during `update-addons`):
- If a tier already has an add-on permission, the add-on is marked **Included**.
- If a tier includes or allows an add-on but lacks its permission, the permission is attached.
- If a tier’s `retention_policy == subscribed`, the retention add-on is **Included**.

---

## 5. Routes (Add-on System)
1. **/developer/addons/** – List add-on catalog.
2. **/developer/addons/create** – Create add-on (permission or function key).
3. **/developer/addons/edit/<id>** – Edit add-on wiring.
4. **/developer/addons/delete/<id>** – Delete add-on.
5. **/developer/subscription-tiers/** – View tiers and entitlements.
6. **/developer/subscription-tiers/create** – Create tier + add-on availability.
7. **/developer/subscription-tiers/edit/<id>** – Edit tier entitlements.
8. **/billing/addons/start/<addon_key>** – Start add-on checkout.
9. **/billing/storage** – Legacy storage add-on checkout.
10. **/billing/webhooks/stripe** – Activate add-ons from Stripe events.

---

## 6. Services (Add-on System)
1. **addon_seeder.py** – Seed add-ons + backfill permissions on tiers.
2. **permissions.py** – Tier permissions exclude add-on perms unless included/purchased.
3. **billing_service.py** – Stripe webhooks create OrganizationAddon records.
4. **retention_service.py** – Uses `function_key="retention"` for retention logic.
5. **batchbot_credit_service.py** – Applies refill add-ons to org credits.

---

## 7. References
- [USERS_AND_PERMISSIONS.md](USERS_AND_PERMISSIONS.md)
- [BILLING.md](BILLING.md)
- [docs/permissions/route-access.md](../permissions/route-access.md)
