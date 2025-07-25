def seed_system_roles():
    """Seed system roles with their permissions"""
    print("=== Seeding System Roles ===")

    # Organization Owner Role
    org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
    if not org_owner_role:
        org_owner_role = Role(
            name='organization_owner',
            description='Organization owner with full access to their organization',
            is_system_role=True,
            is_active=True
        )
        db.session.add(org_owner_role)

        # Give organization owner all customer permissions
        customer_permissions = Permission.query.filter(
            Permission.category.in_(['app', 'organization'])
        ).all()
        org_owner_role.permissions = customer_permissions

        db.session.commit()
        print(f"✅ Created organization_owner role with {len(customer_permissions)} permissions")
    else:
        print("ℹ️  organization_owner role already exists")

    # Admin Role
    admin_role = Role.query.filter_by(name='admin', is_system_role=True).first()
    if not admin_role:
        admin_role = Role(
            name='admin',
            description='System administrator with full access',
            is_system_role=True,
            is_active=True
        )
        db.session.add(admin_role)

        # Give admin all permissions
        all_permissions = Permission.query.all()
        admin_role.permissions = all_permissions

        db.session.commit()
        print(f"✅ Created admin role with {len(all_permissions)} permissions")
    else:
        print("ℹ️  admin role already exists")

    print("✅ System roles seeded successfully!")