"""Billing domain package.

Synopsis:
Organizes billing behavior into explicit orchestrators and shared helpers so
auth, settings, public signup, and provisioning flows stay consistent.

Glossary:
- Orchestrator: Facade that coordinates one billing workflow area.
- Helper: Reusable low-level utility for tier/status normalization.
- Core model: Shared typed data shape used by orchestrators.
"""

from .orchestrators.account_provisioning_orchestrator import (
    AccountProvisioningOrchestrator,
)
from .orchestrators.auth_billing_orchestrator import AuthBillingOrchestrator
from .orchestrators.public_signup_orchestrator import PublicSignupOrchestrator
from .orchestrators.settings_billing_orchestrator import SettingsBillingOrchestrator

__all__ = [
    "AccountProvisioningOrchestrator",
    "AuthBillingOrchestrator",
    "PublicSignupOrchestrator",
    "SettingsBillingOrchestrator",
]
