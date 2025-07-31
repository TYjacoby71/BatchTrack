#!/usr/bin/env python3

import os
import sys
import re
from flask import Flask
from app import create_app
from app.models import *
from app.extensions import db

def main():
    """Main debug function - consolidates all debug functionality"""
    if len(sys.argv) > 1:
        # Command line usage
        command = sys.argv[1].lower()
        org_arg = sys.argv[2] if len(sys.argv) > 2 else None

        app = create_app()
        with app.app_context():
            if command == 'orgs':
                if org_arg == 'org_all':
                    check_all_organizations()
                elif org_arg and org_arg.isdigit():
                    check_specific_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py orgs [org_id|org_all]")
            elif command == 'users':
                if org_arg == 'org_all':
                    check_all_users_permissions()
                elif org_arg and org_arg.isdigit():
                    check_users_for_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py users [org_id|org_all]")
            elif command == 'inventory':
                if org_arg == 'org_all':
                    check_inventory_by_org()
                elif org_arg and org_arg.isdigit():
                    check_inventory_for_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py inventory [org_id|org_all]")
            elif command == 'templates':
                check_template_conditionals()
            elif command == 'js':
                check_javascript_includes()
            elif command == 'roles':
                if org_arg == 'org_all':
                    check_role_assignments()
                elif org_arg and org_arg.isdigit():
                    check_roles_for_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py roles [org_id|org_all]")
            else:
                print_usage()
    else:
        # Interactive mode
        app = create_app()
        with app.app_context():
            interactive_debug()

def print_usage():
    """Print command line usage"""
    print("🐛 BATCHTRACK DEBUG CONSOLE")
    print("=" * 50)
    print("\nUsage:")
    print("  python debug_consolidated.py <command> [org_id|org_all]")
    print("\nCommands:")
    print("  orgs      - Check organizations")
    print("  users     - Check users and permissions")
    print("  inventory - Check inventory")
    print("  templates - Check template conditionals")
    print("  js        - Check JavaScript includes")
    print("  roles     - Check role assignments")
    print("\nExamples:")
    print("  python debug_consolidated.py orgs org_all")
    print("  python debug_consolidated.py orgs 8")
    print("  python debug_consolidated.py users org_all")
    print("  python debug_consolidated.py users 1")

def interactive_debug():
    """Interactive debug mode"""
    print("🐛 BATCHTRACK DEBUG CONSOLE")
    print("=" * 50)

    # Show available debug functions
    print("\nAvailable debug functions:")
    print("1. Check all organizations")
    print("2. Check all users and permissions")
    print("3. Check inventory by organization")
    print("4. Check subscription tiers")
    print("5. Check template conditionals")
    print("6. Check specific organization issues")
    print("7. Check JavaScript includes")
    print("8. Check role assignments")
    print("9. Exit")

    while True:
        choice = input("\nEnter your choice (1-9): ").strip()

        if choice == '1':
            check_all_organizations()
        elif choice == '2':
            check_all_users_permissions()
        elif choice == '3':
            check_inventory_by_org()
        elif choice == '4':
            check_subscription_tiers()
        elif choice == '5':
            check_template_conditionals()
        elif choice == '6':
            org_id = input("Enter organization ID (or 'all' for all orgs): ").strip()
            if org_id.lower() == 'all':
                check_all_organizations()
            elif org_id.isdigit():
                check_specific_org(int(org_id))
            else:
                print("Invalid organization ID")
        elif choice == '7':
            check_javascript_includes()
        elif choice == '8':
            check_role_assignments()
        elif choice == '9':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

def check_specific_org(org_id=None):
    """Check specific organization for issues"""
    if org_id is None:
        org_id_input = input("Enter organization ID: ").strip()
        if not org_id_input.isdigit():
            print("Invalid organization ID")
            return
        org_id = int(org_id_input)

    org = Organization.query.get(org_id)

    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    print(f"\n=== Organization {org_id}: {org.name} ===")
    print(f"Active: {org.is_active}")
    print(f"Subscription tier: {org.effective_subscription_tier}")
    print(f"Users count: {len(org.users)}")
    print(f"Active users: {org.active_users_count}")

    # Check users and permissions
    check_users_for_org(org_id)

    # Check ingredients for this organization
    check_inventory_for_org(org_id)

def check_users_for_org(org_id):
    """Check users for a specific organization"""
    org = Organization.query.get(org_id)
    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    print(f"\n=== Users in Organization {org_id} ({org.name}) ===")
    for user in org.users:
        print(f"ID {user.id}: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  User Type: {user.user_type}")
        print(f"  Active: {user.is_active}")
        print(f"  Organization Owner: {user.is_organization_owner}")

        # Check role assignments
        assignments = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()
        print(f"  Active Role Assignments: {len(assignments)}")
        for assignment in assignments:
            role = Role.query.get(assignment.role_id)
            print(f"    - Role: {role.name if role else 'UNKNOWN'} (ID: {assignment.role_id})")

        # Check permissions
        print(f"  Key Permissions:")
        for perm in ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit']:
            has_perm = user.has_permission(perm)
            status = "✅" if has_perm else "❌"
            print(f"    {status} {perm}")
        print()

def check_inventory_for_org(org_id):
    """Check inventory for a specific organization"""
    org = Organization.query.get(org_id)
    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    ingredients = InventoryItem.query.filter(
        ~InventoryItem.type.in_(['product', 'product-reserved']),
        InventoryItem.organization_id == org_id
    ).all()
    print(f"\n=== Organization {org_id} ({org.name}) Inventory ===")
    print(f"Ingredients: {len(ingredients)}")
    if len(ingredients) > 0:
        for ing in ingredients[:5]:
            print(f"   - {ing.name} (Type: {ing.type})")
        if len(ingredients) > 5:
            print(f"   ... and {len(ingredients) - 5} more")
    print()

def check_roles_for_org(org_id):
    """Check role assignments for a specific organization"""
    org = Organization.query.get(org_id)
    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    print(f"\n=== Role Assignments for Organization {org_id} ({org.name}) ===")

    # Check organization owner role exists
    owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    if not owner_role:
        print("❌ CRITICAL: organization_owner system role does not exist!")
    else:
        print(f"✅ organization_owner role exists with {len(owner_role.permissions)} permissions")

        # Check if anyone has this role in this org
        owner_assignments = UserRoleAssignment.query.filter_by(
            role_id=owner_role.id,
            organization_id=org_id,
            is_active=True
        ).all()

        if not owner_assignments:
            print(f"❌ NO ONE has organization_owner role in {org.name}!")
        else:
            print(f"✅ {len(owner_assignments)} users have organization_owner role")
            for assignment in owner_assignments:
                user = User.query.get(assignment.user_id)
                print(f"   - {user.username if user else 'UNKNOWN'}")

    # Show all role assignments for this org
    all_assignments = UserRoleAssignment.query.filter_by(
        organization_id=org_id,
        is_active=True
    ).all()

    print(f"\nAll active role assignments: {len(all_assignments)}")
    for assignment in all_assignments:
        user = User.query.get(assignment.user_id)
        role = Role.query.get(assignment.role_id)
        print(f"   {user.username if user else 'UNKNOWN'} -> {role.name if role else 'UNKNOWN'}")

def check_template_conditionals():
    """Find all template files with subscription tier conditionals"""
    print("\n=== SCANNING FOR SUBSCRIPTION TIER CONDITIONALS ===")

    template_dirs = [
        'app/templates',
        'app/blueprints'
    ]

    conditional_patterns = [
        r'subscription_tier\s*[!=><]+',
        r'current_user\.organization\.subscription',
        r'organization\.subscription',
        r'tier\s*[!=><]+\s*[\'"]exempt[\'"]',
        r'exempt.*tier',
        r'{% if.*tier.*%}',
        r'{% if.*subscription.*%}'
    ]

    found_files = []

    for template_dir in template_dirs:
        if os.path.exists(template_dir):
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith(('.html', '.py')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()

                            for pattern in conditional_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    found_files.append((file_path, pattern, matches))
                                    print(f"🔍 {file_path}")
                                    print(f"   Pattern: {pattern}")
                                    print(f"   Matches: {matches}")

                                    # Show context around matches
                                    lines = content.split('\n')
                                    for i, line in enumerate(lines):
                                        if re.search(pattern, line, re.IGNORECASE):
                                            start = max(0, i-2)
                                            end = min(len(lines), i+3)
                                            print(f"   Context (lines {start+1}-{end}):")
                                            for j in range(start, end):
                                                marker = ">>> " if j == i else "    "
                                                print(f"   {marker}{j+1}: {lines[j]}")
                                    print()
                        except Exception as e:
                            pass

    print(f"\n📊 Found {len(found_files)} files with subscription tier conditionals")
    return found_files

def check_javascript_includes():
    """Check for JavaScript file inclusions in templates"""
    print("\n=== JAVASCRIPT INCLUSION PATTERNS ===")

    js_patterns = [
        r'<script.*src.*ingredient.*\.js',
        r'<script.*src.*recipe.*\.js', 
        r'<script.*src.*modal.*\.js',
        r'{% if.*%}.*<script',
        r'<script.*addIngredient',
        r'function addIngredient'
    ]

    template_files = []
    for root, dirs, files in os.walk('app/templates'):
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))

    found_issues = 0
    for template_file in template_files:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            for pattern in js_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    print(f"📄 {template_file}")
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            print(f"   Line {i+1}: {line.strip()}")
                            found_issues += 1
                    print()
        except Exception as e:
            pass

    print(f"📊 Found {found_issues} JavaScript inclusion patterns")

def check_all_organizations():
    """Debug all organizations in the system"""
    print("=== DEBUGGING ALL ORGANIZATIONS ===")

    all_orgs = Organization.query.all()
    print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

    if len(all_orgs) == 0:
        print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
        return

    for org in all_orgs:
        print(f"\nID {org.id}: {org.name}")
        print(f"   Active: {org.is_active}")
        print(f"   Subscription tier: {org.effective_subscription_tier}")
        print(f"   Users: {len(org.users)}")
        print(f"   Active users: {org.active_users_count}")

        # Show users in this org
        for user in org.users:
            print(f"     - {user.username} (type: {user.user_type}, active: {user.is_active})")

    # Show all users and their org assignments
    all_users = User.query.all()
    print(f"\n=== ALL USERS IN DATABASE ({len(all_users)}) ===")
    for user in all_users:
        print(f"ID {user.id}: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   Organization ID: {user.organization_id}")
        print(f"   User Type: {user.user_type}")
        print(f"   Active: {user.is_active}")
        if user.organization_id:
            org = Organization.query.get(user.organization_id)
            print(f"   Organization Name: {org.name if org else 'NOT FOUND'}")

    # Check for dev users wrongly assigned to organizations
    print(f"\n=== DEV USER ISSUES CHECK ===")
    dev_users = User.query.filter_by(user_type='developer').all()
    for dev_user in dev_users:
        if dev_user.organization_id is not None:
            print(f"❌ PROBLEM: Dev user '{dev_user.username}' is assigned to organization {dev_user.organization_id}!")
            print("   Dev users should have organization_id = None")
        else:
            print(f"✅ Dev user '{dev_user.username}' correctly has no organization assignment")

    # Check permissions existence
    print(f"\n=== PERMISSION EXISTENCE CHECK ===")
    required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit', 'dashboard.view', 'batches.view']
    for perm_name in required_perms:
        perm = Permission.query.filter_by(name=perm_name).first()
        if perm:
            print(f"✅ {perm_name} exists and is {'active' if perm.is_active else 'inactive'}")
        else:
            print(f"❌ {perm_name} MISSING from database!")

def check_all_users_permissions():
    """Debug all users and their permissions in the system"""
    print("=== DEBUGGING ALL USERS AND PERMISSIONS ===")

    all_users = User.query.all()
    print(f"\n=== ALL USERS IN DATABASE ({len(all_users)}) ===")

    if len(all_users) == 0:
        print("❌ NO USERS FOUND IN DATABASE!")
        return

    for user in all_users:
        print(f"\nID {user.id}: {user.username}")
        print(f"   Email: {user.email}")
        print(f"   User Type: {user.user_type}")
        print(f"   Active: {user.is_active}")
        print(f"   Organization ID: {user.organization_id}")
        if user.organization_id:
            org = Organization.query.get(user.organization_id)
            print(f"   Organization Name: {org.name if org else 'NOT FOUND'}")

        # Check role assignments
        assignments = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()
        print(f"   Active Role Assignments: {len(assignments)}")
        for assignment in assignments:
            role = Role.query.get(assignment.role_id)
            print(f"    - Role: {role.name if role else 'UNKNOWN'} (ID: {assignment.role_id})")

        # Check permissions
        print(f"  Key Permissions:")
        for perm in ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit', 'dashboard.view', 'batches.view']:
            has_perm = user.has_permission(perm)
            status = "✅" if has_perm else "❌"
            print(f"    {status} {perm}")
        print()

def check_inventory_by_org():
    """Debug inventory for all organizations"""
    print("=== DEBUGGING INVENTORY BY ORGANIZATION ===")

    all_orgs = Organization.query.all()
    print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

    if len(all_orgs) == 0:
        print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
        return

    for org in all_orgs:
        print(f"\n=== Organization {org.id}: {org.name} ===")
        check_inventory_for_org(org.id)

def check_subscription_tiers():
    """Debug subscription tiers"""
    print("=== DEBUGGING SUBSCRIPTION TIERS ===")

    all_orgs = Organization.query.all()
    print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

    if len(all_orgs) == 0:
        print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
        return

    for org in all_orgs:
        print(f"\n=== Organization {org.id}: {org.name} ===")
        print(f"Subscription tier: {org.effective_subscription_tier}")
        print(f"Active: {org.is_active}")
        print(f"Users count: {len(org.users)}")
        print(f"Active users: {org.active_users_count}")

def check_role_assignments():
    """Debug role assignments for all organizations"""
    print("=== DEBUGGING ROLE ASSIGNMENTS ===")

    all_orgs = Organization.query.all()
    print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

    if len(all_orgs) == 0:
        print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
        return

    for org in all_orgs:
        print(f"\n=== Organization {org.id}: {org.name} ===")
        check_roles_for_org(org.id)

if __name__ == "__main__":
    main()

The code has been modified to consolidate debug functionality into a single script with interactive and command-line options, including organization selection and various checks.
#!/usr/bin/env python3

import os
import sys
import re
from flask import Flask
from app import create_app
from app.models import *
from app.extensions import db

def main():
    """Main debug function - consolidates all debug functionality"""
    if len(sys.argv) > 1:
        # Command line usage
        command = sys.argv[1].lower()
        org_arg = sys.argv[2] if len(sys.argv) > 2 else None

        app = create_app()
        with app.app_context():
            if command == 'orgs':
                if org_arg == 'org_all':
                    check_all_organizations()
                elif org_arg and org_arg.isdigit():
                    check_specific_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py orgs [org_id|org_all]")
            elif command == 'users':
                if org_arg == 'org_all':
                    check_all_users_permissions()
                elif org_arg and org_arg.isdigit():
                    check_users_for_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py users [org_id|org_all]")
            elif command == 'inventory':
                if org_arg == 'org_all':
                    check_inventory_by_org()
                elif org_arg and org_arg.isdigit():
                    check_inventory_for_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py inventory [org_id|org_all]")
            elif command == 'templates':
                check_template_conditionals()
            elif command == 'js':
                check_javascript_includes()
            elif command == 'roles':
                if org_arg == 'org_all':
                    check_role_assignments()
                elif org_arg and org_arg.isdigit():
                    check_roles_for_org(int(org_arg))
                else:
                    print("Usage: python debug_consolidated.py roles [org_id|org_all]")
            else:
                print_usage()
    else:
        # Interactive mode
        app = create_app()
        with app.app_context():
            interactive_debug()

def print_usage():
    """Print command line usage"""
    print("🐛 BATCHTRACK DEBUG CONSOLE")
    print("=" * 50)
    print("\nUsage:")
    print("  python debug_consolidated.py <command> [org_id|org_all]")
    print("\nCommands:")
    print("  orgs      - Check organizations")
    print("  users     - Check users and permissions")
    print("  inventory - Check inventory")
    print("  templates - Check template conditionals")
    print("  js        - Check JavaScript includes")
    print("  roles     - Check role assignments")
    print("\nExamples:")
    print("  python debug_consolidated.py orgs org_all")
    print("  python debug_consolidated.py orgs 8")
    print("  python debug_consolidated.py users org_all")
    print("  python debug_consolidated.py users 1")

def interactive_debug():
    """Interactive debug mode"""
    print("🐛 BATCHTRACK DEBUG CONSOLE")
    print("=" * 50)

    # Show available debug functions
    print("\nAvailable debug functions:")
    print("1. Check all organizations")
    print("2. Check all users and permissions")
    print("3. Check inventory by organization")
    print("4. Check subscription tiers")
    print("5. Check template conditionals")
    print("6. Check specific organization issues")
    print("7. Check JavaScript includes")
    print("8. Check role assignments")
    print("9. Exit")

    while True:
        choice = input("\nEnter your choice (1-9): ").strip()

        if choice == '1':
            check_all_organizations()
        elif choice == '2':
            check_all_users_permissions()
        elif choice == '3':
            check_inventory_by_org()
        elif choice == '4':
            check_subscription_tiers()
        elif choice == '5':
            check_template_conditionals()
        elif choice == '6':
            org_id = input("Enter organization ID (or 'all' for all orgs): ").strip()
            if org_id.lower() == 'all':
                check_all_organizations()
            elif org_id.isdigit():
                check_specific_org(int(org_id))
            else:
                print("Invalid organization ID")
        elif choice == '7':
            check_javascript_includes()
        elif choice == '8':
            check_role_assignments()
        elif choice == '9':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

def check_specific_org(org_id=None):
    """Check specific organization for issues"""
    if org_id is None:
        org_id_input = input("Enter organization ID: ").strip()
        if not org_id_input.isdigit():
            print("Invalid organization ID")
            return
        org_id = int(org_id_input)

    org = Organization.query.get(org_id)

    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    print(f"\n=== Organization {org_id}: {org.name} ===")
    print(f"Active: {org.is_active}")
    print(f"Subscription tier: {org.effective_subscription_tier}")
    print(f"Users count: {len(org.users)}")
    print(f"Active users: {org.active_users_count}")

    # Check users and permissions
    check_users_for_org(org_id)

    # Check ingredients for this organization
    check_inventory_for_org(org_id)

def check_users_for_org(org_id):
    """Check users for a specific organization"""
    org = Organization.query.get(org_id)
    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    print(f"\n=== Users in Organization {org_id} ({org.name}) ===")
    for user in org.users:
        print(f"ID {user.id}: {user.username}")
        print(f"  Email: {user.email}")
        print(f"  User Type: {user.user_type}")
        print(f"  Active: {user.is_active}")
        print(f"  Organization Owner: {user.is_organization_owner}")

        # Check role assignments
        assignments = UserRoleAssignment.query.filter_by(
            user_id=user.id,
            is_active=True
        ).all()
        print(f"  Active Role Assignments: {len(assignments)}")
        for assignment in assignments:
            role = Role.query.get(assignment.role_id)
            print(f"    - Role: {role.name if role else 'UNKNOWN'} (ID: {assignment.role_id})")

        # Check permissions
        print(f"  Key Permissions:")
        for perm in ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit']:
            has_perm = user.has_permission(perm)
            status = "✅" if has_perm else "❌"
            print(f"    {status} {perm}")
        print()

def check_inventory_for_org(org_id):
    """Check inventory for a specific organization"""
    org = Organization.query.get(org_id)
    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    ingredients = InventoryItem.query.filter(
        ~InventoryItem.type.in_(['product', 'product-reserved']),
        InventoryItem.organization_id == org_id
    ).all()
    print(f"\n=== Organization {org_id} ({org.name}) Inventory ===")
    print(f"Ingredients: {len(ingredients)}")
    if len(ingredients) > 0:
        for ing in ingredients[:5]:
            print(f"   - {ing.name} (Type: {ing.type})")
        if len(ingredients) > 5:
            print(f"   ... and {len(ingredients) - 5} more")
    print()

def check_roles_for_org(org_id):
    """Check role assignments for a specific organization"""
    org = Organization.query.get(org_id)
    if not org:
        print(f"❌ Organization {org_id} not found!")
        return

    print(f"\n=== Role Assignments for Organization {org_id} ({org.name}) ===")

    # Check organization owner role exists
    owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    if not owner_role:
        print("❌ CRITICAL: organization_owner system role does not exist!")
    else:
        print(f"✅ organization_owner role exists with {len(owner_role.permissions)} permissions")

        # Check if anyone has this role in this org
        owner_assignments = UserRoleAssignment.query.filter_by(
            role_id=owner_role.id,
            organization_id=org_id,
            is_active=True
        ).all()

        if not owner_assignments:
            print(f"❌ NO ONE has organization_owner role in {org.name}!")
        else:
            print(f"✅ {len(owner_assignments)} users have organization_owner role")
            for assignment in owner_assignments:
                user = User.query.get(assignment.user_id)
                print(f"   - {user.username if user else 'UNKNOWN'}")

    # Show all role assignments for this org
    all_assignments = UserRoleAssignment.query.filter_by(
        organization_id=org_id,
        is_active=True
    ).all()

    print(f"\nAll active role assignments: {len(all_assignments)}")
    for assignment in all_assignments:
        user = User.query.get(assignment.user_id)
        role = Role.query.get(assignment.role_id)
        print(f"   {user.username if user else 'UNKNOWN'} -> {role.name if role else 'UNKNOWN'}")

def check_template_conditionals():
    """Find all template files with subscription tier conditionals"""
    print("\n=== SCANNING FOR SUBSCRIPTION TIER CONDITIONALS ===")

    template_dirs = [
        'app/templates',
        'app/blueprints'
    ]

    conditional_patterns = [
        r'subscription_tier\s*[!=><]+',
        r'current_user\.organization\.subscription',
        r'organization\.subscription',
        r'tier\s*[!=><]+\s*[\'"]exempt[\'"]',
        r'exempt.*tier',
        r'{% if.*tier.*%}',
        r'{% if.*subscription.*%}'
    ]

    found_files = []

    for template_dir in template_dirs:
        if os.path.exists(template_dir):
            for root, dirs, files in os.walk(template_dir):
                for file in files:
                    if file.endswith(('.html', '.py')):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()

                            for pattern in conditional_patterns:
                                matches = re.findall(pattern, content, re.IGNORECASE)
                                if matches:
                                    found_files.append((file_path, pattern, matches))
                                    print(f"🔍 {file_path}")
                                    print(f"   Pattern: {pattern}")
                                    print(f"   Matches: {matches}")

                                    # Show context around matches
                                    lines = content.split('\n')
                                    for i, line in enumerate(lines):
                                        if re.search(pattern, line, re.IGNORECASE):
                                            start = max(0, i-2)
                                            end = min(len(lines), i+3)
                                            print(f"   Context (lines {start+1}-{end}):")
                                            for j in range(start, end):
                                                marker = ">>> " if j == i else "    "
                                                print(f"   {marker}{j+1}: {lines[j]}")
                                    print()
                        except Exception as e:
                            pass

    print(f"\n📊 Found {len(found_files)} files with subscription tier conditionals")
    return found_files

def check_javascript_includes():
    """Check for JavaScript file inclusions in templates"""
    print("\n=== JAVASCRIPT INCLUSION PATTERNS ===")

    js_patterns = [
        r'<script.*src.*ingredient.*\.js',
        r'<script.*src.*recipe.*\.js', 
        r'<script.*src.*modal.*\.js',
        r'{% if.*%}.*<script',
        r'<script.*addIngredient',
        r'function addIngredient'
    ]

    template_files = []
    for root, dirs, files in os.walk('app/templates'):
        for file in files:
            if file.endswith('.html'):
                template_files.append(os.path.join(root, file))

    found_issues = 0
    for template_file in template_files:
        try:
            with open(template_file, 'r', encoding='utf-8') as f:
                content = f.read()

            for pattern in js_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    print(f"📄 {template_file}")
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if re.search(pattern, line, re.IGNORECASE):
                            print(f"   Line {i+1}: {line.strip()}")
                            found_issues += 1
                    print()
        except Exception as e:
            pass

    print(f"📊 Found {found_issues} JavaScript inclusion patterns")

def check_all_organizations():
    """Debug all organizations in the system"""
    app = create_app()

    with app.app_context():
        print("=== DEBUGGING ALL ORGANIZATIONS ===")

        all_orgs = Organization.query.all()
        print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

        if len(all_orgs) == 0:
            print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
            return

        for org in all_orgs:
            print(f"\nID {org.id}: {org.name}")
            print(f"   Active: {org.is_active}")
            print(f"   Subscription tier: {org.effective_subscription_tier}")
            print(f"   Users: {len(org.users)}")
            print(f"   Active users: {org.active_users_count}")

            # Show users in this org
            for user in org.users:
                print(f"     - {user.username} (type: {user.user_type}, active: {user.is_active})")

        # Show all users and their org assignments
        all_users = User.query.all()
        print(f"\n=== ALL USERS IN DATABASE ({len(all_users)}) ===")
        for user in all_users:
            print(f"ID {user.id}: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   Organization ID: {user.organization_id}")
            print(f"   User Type: {user.user_type}")
            print(f"   Active: {user.is_active}")
            if user.organization_id:
                org = Organization.query.get(user.organization_id)
                print(f"   Organization Name: {org.name if org else 'NOT FOUND'}")

        # Check for dev users wrongly assigned to organizations
        print(f"\n=== DEV USER ISSUES CHECK ===")
        dev_users = User.query.filter_by(user_type='developer').all()
        for dev_user in dev_users:
            if dev_user.organization_id is not None:
                print(f"❌ PROBLEM: Dev user '{dev_user.username}' is assigned to organization {dev_user.organization_id}!")
                print("   Dev users should have organization_id = None")
            else:
                print(f"✅ Dev user '{dev_user.username}' correctly has no organization assignment")

        # Check permissions existence
        print(f"\n=== PERMISSION EXISTENCE CHECK ===")
        required_perms = ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit', 'dashboard.view', 'batches.view']
        for perm_name in required_perms:
            perm = Permission.query.filter_by(name=perm_name).first()
            if perm:
                print(f"✅ {perm_name} exists and is {'active' if perm.is_active else 'inactive'}")
            else:
                print(f"❌ {perm_name} MISSING from database!")

def check_all_users_permissions():
    """Debug all users and their permissions in the system"""
    app = create_app()

    with app.app_context():
        print("=== DEBUGGING ALL USERS AND PERMISSIONS ===")

        all_users = User.query.all()
        print(f"\n=== ALL USERS IN DATABASE ({len(all_users)}) ===")

        if len(all_users) == 0:
            print("❌ NO USERS FOUND IN DATABASE!")
            return

        for user in all_users:
            print(f"\nID {user.id}: {user.username}")
            print(f"   Email: {user.email}")
            print(f"   User Type: {user.user_type}")
            print(f"   Active: {user.is_active}")
            print(f"   Organization ID: {user.organization_id}")
            if user.organization_id:
                org = Organization.query.get(user.organization_id)
                print(f"   Organization Name: {org.name if org else 'NOT FOUND'}")

            # Check role assignments
            assignments = UserRoleAssignment.query.filter_by(
                user_id=user.id,
                is_active=True
            ).all()
            print(f"   Active Role Assignments: {len(assignments)}")
            for assignment in assignments:
                role = Role.query.get(assignment.role_id)
                print(f"    - Role: {role.name if role else 'UNKNOWN'} (ID: {assignment.role_id})")

            # Check permissions
            print(f"  Key Permissions:")
            for perm in ['recipes.edit', 'recipes.view', 'inventory.view', 'inventory.edit', 'dashboard.view', 'batches.view']:
                has_perm = user.has_permission(perm)
                status = "✅" if has_perm else "❌"
                print(f"    {status} {perm}")
            print()

def check_inventory_by_org():
    """Debug inventory for all organizations"""
    app = create_app()

    with app.app_context():
        print("=== DEBUGGING INVENTORY BY ORGANIZATION ===")

        all_orgs = Organization.query.all()
        print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

        if len(all_orgs) == 0:
            print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
            return

        for org in all_orgs:
            print(f"\n=== Organization {org.id}: {org.name} ===")
            check_inventory_for_org(org.id)

def check_subscription_tiers():
    """Debug subscription tiers"""
    app = create_app()

    with app.app_context():
        print("=== DEBUGGING SUBSCRIPTION TIERS ===")

        all_orgs = Organization.query.all()
        print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

        if len(all_orgs) == 0:
            print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
            return

        for org in all_orgs:
            print(f"\n=== Organization {org.id}: {org.name} ===")
            print(f"Subscription tier: {org.effective_subscription_tier}")
            print(f"Active: {org.is_active}")
            print(f"Users count: {len(org.users)}")
            print(f"Active users: {org.active_users_count}")

def check_role_assignments():
    """Debug role assignments for all organizations"""
    app = create_app()

    with app.app_context():
        print("=== DEBUGGING ROLE ASSIGNMENTS ===")

        all_orgs = Organization.query.all()
        print(f"\n=== ALL ORGANIZATIONS IN DATABASE ({len(all_orgs)}) ===")

        if len(all_orgs) == 0:
            print("❌ NO ORGANIZATIONS FOUND IN DATABASE!")
            return

        for org in all_orgs:
            print(f"\n=== Organization {org.id}: {org.name} ===")
            check_roles_for_org(org.id)

if __name__ == "__main__":
    main()