"""Read-only HTTPS smoke check for an ALREADY deployed private staging host.

Never prints credentials, makes purchases, or sends email. It first checks
that unauthenticated visitors are blocked, then uses staging HTTP Basic auth.
Run: python scripts/probe_staging.py
"""
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit
from dotenv import dotenv_values
import base64
import ssl
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from staging_setup import validate_staging_config

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward Basic auth to another hostname.


def fetch(opener, url, authorization=None):
    headers = {'User-Agent':'ODJ-Staging-SmokeTest/1.0'}
    if authorization:
        headers['Authorization'] = authorization
    req = Request(url, headers=headers, method='GET')
    try:
        with opener.open(req, timeout=12) as response:
            return response.status, dict(response.headers.items()), response.read(8192).decode('utf-8','replace')
    except HTTPError as error:
        return error.code, dict(error.headers.items()), error.read(8192).decode('utf-8','replace')


def evaluate(base_url, opener, username, password):
    """Returns (bool, messages). Only access expected HTTPS staging host."""
    u = urlsplit(base_url)
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.path not in ('', '/') or u.query or u.fragment:
        raise ValueError('Only an HTTPS staging root URL is accepted.')
    token = base64.b64encode((username + ':' + password).encode('utf-8')).decode('ascii')
    auth = 'Basic ' + token
    checks = []
    for path, credentials, expected in [
        ('/', False, 401),
        ('/api/products', False, 401),
        ('/static/style.css', False, 401),
        ('/', True, 200),
        ('/admin', True, 200),
        ('/api/admin/products', True, 401),
        ('/static/style.css', True, 200),
        ('/robots.txt', True, 200),
    ]:
        status, headers, body = fetch(opener, base_url.rstrip('/') + path, auth if credentials else None)
        good = status == expected
        if credentials and path == '/':
            good &= 'noindex' in headers.get('X-Robots-Tag',headers.get('X-robots-tag','')).lower()
        if credentials and path == '/robots.txt':
            good &= 'Disallow: /' in body
        label = ('authorized ' if credentials else 'anonymous ') + path
        checks.append((good, label, status, expected))
    return all(c[0] for c in checks), checks


def main():
    path = ROOT / '.env.staging'
    if not path.exists():
        raise SystemExit('No .env.staging; run this from the staging checkout with private credentials.')
    config = {k:v or '' for k,v in dotenv_values(path).items()}
    if validate_staging_config(config):
        raise SystemExit('Staging configuration is incomplete; run scripts/check_staging.py.')
    root = config['PUBLIC_BASE_URL']
    if root != 'https://' + config['DOMAIN']:
        raise SystemExit('Staging HTTPS URL does not match configured hostname.')
    opener = build_opener(NoRedirect())
    try:
        ok, results = evaluate(root, opener, config['STAGING_ACCESS_USER'], config['STAGING_ACCESS_PASSWORD'])
    except (URLError, TimeoutError, OSError) as err:
        raise SystemExit('Could not reach staging over HTTPS. Check DNS, firewall, TLS, and whether containers are running.')
    print('ODJ V7.6 protected staging smoke check (no secrets or customer data)')
    for good,label,status,expected in results:
        print(('PASS' if good else 'FAIL') + f': {label} (HTTP {status}, expected {expected})')
    if not ok:
        raise SystemExit('FAILED: Do not share the staging URL until all checks pass.')
    print('PASS: Staging gate works. Not a production-security audit or payment test.')

if __name__ == '__main__':
    main()
