from unittest.mock import patch


def test_stripe_webhook_valid_signature_dispatches(app, client):
    payload = b'{"id": "evt_123", "type": "test.event"}'

    with app.app_context():
        app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test'

    with patch('app.services.billing_service.BillingService.construct_event') as mock_construct, \
            patch('app.services.billing_service.BillingService.handle_webhook_event') as mock_handle:

        mock_event = {'id': 'evt_123', 'type': 'test.event'}
        mock_construct.return_value = mock_event
        mock_handle.return_value = 204

        response = client.post(
            '/billing/webhooks/stripe',
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'Stripe-Signature': 't=123,v1=test'
            }
        )

        assert response.status_code == 204
        mock_construct.assert_called_once_with(payload, 't=123,v1=test', 'whsec_test')
        mock_handle.assert_called_once_with('stripe', mock_event)


def test_stripe_webhook_returns_400_when_signature_invalid(app, client):
    with app.app_context():
        app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test'

    with patch('app.services.billing_service.BillingService.construct_event', side_effect=Exception('bad signature')) as mock_construct, \
            patch('app.services.billing_service.BillingService.handle_webhook_event') as mock_handle:

        response = client.post(
            '/billing/webhooks/stripe',
            data=b'{}',
            headers={'Stripe-Signature': 'bad'}
        )

        assert response.status_code == 400
        mock_construct.assert_called_once()
        mock_handle.assert_not_called()


def test_stripe_webhook_returns_500_when_secret_missing(app, client):
    with app.app_context():
        app.config.pop('STRIPE_WEBHOOK_SECRET', None)

    response = client.post('/billing/webhooks/stripe', data=b'{}')

    assert response.status_code == 500