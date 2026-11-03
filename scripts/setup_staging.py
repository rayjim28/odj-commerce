"""Create isolated .env.staging WITHOUT overwriting local .env.

Run only for a NEW private staging host/project; do not publish this file.
Usage: python scripts/setup_staging.py --domain preview.example.com
"""
import argparse
from getpass import getpass
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from staging_setup import generate_staging_config, render_env, valid_hostname


def main():
    p = argparse.ArgumentParser(description='Create ODJ private staging configuration; no payments or email.')
    p.add_argument('--domain', required=True, help='DNS hostname such as preview.example.com')
    p.add_argument('--staging-user', default='odj-review')
    args = p.parse_args()
    path = ROOT / '.env.staging'
    if path.exists():
        raise SystemExit('.env.staging already exists. Existing credentials were NOT changed.')
    if not valid_hostname(args.domain):
        raise SystemExit('Please supply a valid public DNS hostname (no http://, ports or paths).')
    print('ODJ private staging: choose TWO different passwords. Nothing is sent online.')
    admin_pwd = getpass('New staging ADMIN password (12+ chars): ')
    admin_confirmation = getpass('Confirm staging admin password: ')
    site_pwd = getpass('Private staging SITE password (20+ chars): ')
    site_confirmation = getpass('Confirm staging site password: ')
    if admin_pwd != admin_confirmation or site_pwd != site_confirmation:
        raise SystemExit('Passwords did not match. No configuration was saved.')
    try:
        config = generate_staging_config(args.domain, admin_pwd, args.staging_user, site_pwd)
        content = render_env(config)
    except ValueError as error:
        raise SystemExit(str(error))
    # 'x' refuses overwrite even if file appears between checks.
    old_umask = os.umask(0o077)
    try:
        with path.open('x', encoding='utf-8') as stream:
            stream.write(content)
        path.chmod(0o600)
    finally:
        os.umask(old_umask)
    print('PRIVATE .env.staging created. No secret values were displayed.')
    print('Keep your normal Mac .env file separate; both are ignored by Git.')
    print('Next: python scripts/check_staging.py')
    print('Then: docker compose --env-file .env.staging -p odj-staging -f compose.staging.yaml up -d --build')

if __name__ == '__main__':
    main()
