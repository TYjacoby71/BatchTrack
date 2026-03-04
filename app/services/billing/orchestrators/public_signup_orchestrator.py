"""Public signup + Stripe orchestration.

Synopsis:
Encapsulates how public routes prepare signup pricing context and dispatch
checkout submissions to Stripe-backed flows.
"""

from __future__ import annotations

from ...signup_checkout_service import SignupCheckoutService


class PublicSignupOrchestrator:
    """Facade for public signup pricing + checkout flow."""

    @staticmethod
    def build_request_context(*, request, oauth_user_info, allow_live_pricing_network):
        return SignupCheckoutService.build_request_context(
            request=request,
            oauth_user_info=oauth_user_info,
            allow_live_pricing_network=allow_live_pricing_network,
        )

    @staticmethod
    def build_initial_view_state(context):
        return SignupCheckoutService.build_initial_view_state(context)

    @staticmethod
    def build_template_context(
        context,
        view_state,
        *,
        oauth_available,
        oauth_providers,
        canonical_url,
    ):
        return SignupCheckoutService.build_template_context(
            context,
            view_state,
            oauth_available=oauth_available,
            oauth_providers=oauth_providers,
            canonical_url=canonical_url,
        )

    @staticmethod
    def process_submission(*, context, form_data):
        return SignupCheckoutService.process_submission(
            context=context,
            form_data=form_data,
        )
