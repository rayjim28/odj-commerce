"""Safe, opt-in Stripe TEST configuration diagnostic. Never prints keys or Stripe account data.

Run from project root: python scripts/diagnose_stripe.py
Optional read-only network test: python scripts/diagnose_stripe.py --verify-test-key
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    print('Install project requirements to read .env (pip install -r requirements.txt).')
    sys.exit(2)


def key_kind(key):
    """Return a non-sensitive key classification; do not return or log the input."""
    if not key:
        return 'missing'
    upper = key.upper()
    if any(x in upper for x in ('YOUR_', 'PLACEHOLDER', 'EXAMPLE', 'REPLACE_ME')):
        return 'placeholder'
    if key.startswith('sk_test_') and len(key) >= 24:
        return 'test'
    if key.startswith('sk_live_') and len(key) >= 24:
        return 'live'
    if key.startswith('rk_test_'):
        return 'restricted-test'
    if key.startswith('pk_'):
        return 'publishable'
    return 'invalid'


def inspect_settings(env):
    """No secrets in output. This checks shapes only, not remote validity."""
    mode = env.get('PAYMENT_MODE', 'demo').strip().lower()
    stage = env.get('APP_ENV', 'development').strip().lower()
    kind = key_kind(env.get('STRIPE_SECRET_KEY', '').strip())
    hook = env.get('STRIPE_WEBHOOK_SECRET', '').strip()
    hook_ok = hook.startswith('whsec_') and len(hook) >= 20 and not any(
        s in hook.upper() for s in ('YOUR_', 'PLACEHOLDER', 'EXAMPLE'))
    checks = []
    if mode == 'demo':
        checks.append(('INFO', 'PAYMENT_MODE=demo. Checkout will stay in demo mode even if a test key is present.'))
    elif mode == 'stripe':
        checks.append(('OK', 'Stripe checkout is selected in the local configuration.'))
    else:
        checks.append(('FIX', 'PAYMENT_MODE must be demo or stripe.'))
    if kind == 'test':
        checks.append(('OK', 'A test secret key is configured; actual validity has not been checked.'))
    elif kind == 'live':
        checks.append(('STOP', 'A LIVE secret key is configured. Never test with it locally; switch back to a test key.'))
    elif kind == 'publishable':
        checks.append(('FIX', 'This looks like a publishable key, not the required test secret key.'))
    elif kind == 'restricted-test':
        checks.append(('FIX', 'This is a restricted key. Use an authorized test secret key for the existing integration.'))
    else:
        checks.append(('FIX', 'STRIPE_SECRET_KEY is missing, a placeholder, or not a valid-looking test secret.'))
    if hook_ok:
        checks.append(('INFO', 'A webhook signing secret is configured; signature validation still needs a real test event.'))
    else:
        checks.append(('FIX', 'Configure a test webhook signing secret from the Stripe CLI; it differs from the API key.'))
    if stage == 'production':
        checks.append(('STOP', 'APP_ENV=production. Use development for local test checkout.'))
    else:
        checks.append(('OK', 'Running outside production mode.'))
    return checks, kind == 'test' and stage != 'production'


def verify_test_key(secret):
    """Read-only Stripe account API call; returns a generalized message, never raw response bodies."""
    try:
        import httpx
        with httpx.Client(timeout=12) as client:
            response = client.get('https://api.stripe.com/v1/account',
                                  headers={'Authorization': 'Bearer ' + secret})
        status = response.status_code
        if status == 200:
            return 'PASS: Stripe accepted the test API key. No payment was created.'
        if status == 401:
            return 'FAIL: Stripe rejected the key (HTTP 401). Check that it is the correct test secret key.'
        if status == 403:
            return 'FAIL: Stripe denied access (HTTP 403). Check account permissions and key restrictions.'
        if status == 429:
            return 'RETRY: Stripe rate limit reached (HTTP 429). Try again later.'
        return 'INCONCLUSIVE: Stripe returned HTTP ' + str(status) + '. Check the test-mode API request logs.'
    except Exception:
        return 'INCONCLUSIVE: Could not reach Stripe. Check internet access and try again.'


def main():
    parser = argparse.ArgumentParser(description='Stripe TEST setup check without showing secret values')
    parser.add_argument('--verify-test-key', action='store_true',
                        help='Make one read-only Stripe API request using the locally configured TEST key')
    args = parser.parse_args()
    checks, safe_to_verify = inspect_settings(os.environ)
    print('ODJ | Stripe TEST setup check (no credentials shown)')
    for status, message in checks:
        print('[' + status + '] ' + message)
    if args.verify_test_key:
        if safe_to_verify:
            print(verify_test_key(os.environ.get('STRIPE_SECRET_KEY', '')))
        else:
            print('SKIPPED: Only valid-looking TEST keys in non-production mode may be verified.')
    else:
        print('Optional read-only credential check: python scripts/diagnose_stripe.py --verify-test-key')
    print('This tool does not test checkout, tax, refunds, or webhook delivery. It never enables live payments.')


if __name__ == '__main__':
    main()
