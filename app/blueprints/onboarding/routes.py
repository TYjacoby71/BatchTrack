from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from flask_login import login_required, current_user

from ...extensions import db
from ...utils.timezone_utils import TimezoneUtils

onboarding_bp = Blueprint('onboarding', __name__, url_prefix='/onboarding')


@onboarding_bp.route('/welcome', methods=['GET', 'POST'])
@login_required
def welcome():
    """Guided landing checklist right after signup."""
    user = current_user
    organization = getattr(user, 'organization', None)

    if not organization:
        flash('No organization found for your account.', 'error')
        return redirect(url_for('app_routes.dashboard'))

    if request.method == 'POST':
        org_name = (request.form.get('org_name') or organization.name or '').strip()
        org_contact_email = (request.form.get('org_contact_email') or organization.contact_email or '').strip()
        user_first = (request.form.get('first_name') or user.first_name or '').strip()
        user_last = (request.form.get('last_name') or user.last_name or '').strip()
        user_phone = (request.form.get('user_phone') or user.phone or '').strip()

        organization.name = org_name or organization.name
        organization.contact_email = org_contact_email or organization.contact_email
        user.first_name = user_first
        user.last_name = user_last
        user.phone = user_phone or None
        user.last_login = user.last_login or TimezoneUtils.utc_now()

        db.session.commit()
        flash('Setup details saved.', 'success')

        if request.form.get('complete_checklist') == 'true':
            session.pop('onboarding_welcome', None)
            return redirect(url_for('app_routes.dashboard'))
    else:
        if session.pop('onboarding_welcome', None):
            flash('Thanks for joining BatchTrack! Let’s finish setting up your workspace.', 'success')

    team_size = len([member for member in organization.users if member.is_active and member.user_type != 'developer'])
    show_team_step = bool(organization.subscription_tier_obj and organization.subscription_tier_obj.user_limit not in (None, 1))

    checklist = [
        {
            'key': 'org_name',
            'label': 'Name your workspace',
            'description': 'Give your organization a friendly name so teammates know they are in the right place.',
            'complete': bool(organization.name and organization.name.strip()),
        },
        {
            'key': 'contact_info',
            'label': 'Confirm your contact info',
            'description': 'Make sure we have the best email so invoices and alerts reach you.',
            'complete': bool(organization.contact_email),
        },
        {
            'key': 'profile',
            'label': 'Tell us about you',
            'description': 'Add your name and phone number so support can reach you quickly.',
            'complete': bool(user.first_name and user.last_name),
        },
    ]

    if show_team_step:
        checklist.append({
            'key': 'team',
            'label': 'Plan your team seats',
            'description': 'Invite a teammate or confirm how many users you need on this tier.',
            'complete': team_size > 1,
        })

    return render_template(
        'onboarding/welcome.html',
        organization=organization,
        checklist=checklist,
        show_team_step=show_team_step,
        team_size=team_size,
    )
