import json


def test_subscription_tiers_have_lookup_keys():
    with open('subscription_tiers.json', 'r') as f:
        tiers = json.load(f)

    expected = {
        'batchtrack_solo_monthly',
        'batchtrack_team_monthly',
        'batchtrack_enterprise_monthly',
    }

    found = set()
    for key, tier in tiers.items():
        if isinstance(tier, dict):
            lk = tier.get('stripe_lookup_key')
            if lk:
                found.add(lk)

    # Ensure all expected lookup keys are present in the config
    missing = expected - found
    assert not missing, f"Missing lookup keys in subscription_tiers.json: {missing}"

