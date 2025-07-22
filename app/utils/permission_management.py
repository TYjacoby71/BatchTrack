
from ..models import Role, Permission
from ..extensions import db

def update_organization_owner_permissions():
    """Ensure organization owner role has all active permissions"""
    try:
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if not org_owner_role:
            print("⚠️  Organization owner system role not found")
            return False
            
        # Get all active permissions
        all_permissions = Permission.query.filter_by(is_active=True).all()
        
        # Update role with all permissions
        org_owner_role.permissions = all_permissions
        db.session.commit()
        
        print(f"✅ Updated organization owner role with {len(all_permissions)} permissions")
        return True
        
    except Exception as e:
        print(f"❌ Error updating organization owner permissions: {e}")
        db.session.rollback()
        return False

def assign_organization_owner_role(user):
    """Assign organization owner role to a user"""
    try:
        org_owner_role = Role.query.filter_by(name='organization_owner', is_system_role=True).first()
        if not org_owner_role:
            print("⚠️  Organization owner system role not found")
            return False
            
        user.assign_role(org_owner_role)
        return True
        
    except Exception as e:
        print(f"❌ Error assigning organization owner role: {e}")
        return False
