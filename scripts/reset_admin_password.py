"""Safely reset only this store's admin credentials on the local machine.
Does not delete products, orders, customers or Stripe settings.
"""
import sys, secrets, os
from pathlib import Path
from getpass import getpass
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security import make_password_hash

root = Path(__file__).resolve().parents[1]
env = root / '.env'
if not env.exists():
    raise SystemExit('No .env found. First run: python scripts/setup_local.py')
password = getpass('New admin password (minimum 12 characters): ')
confirmation = getpass('Confirm new admin password: ')
if len(password) < 12 or password != confirmation:
    raise SystemExit('Passwords must match and be at least 12 characters.')
values = {'ADMIN_PASSWORD_HASH': make_password_hash(password),
          'SESSION_SECRET': secrets.token_urlsafe(48)}
rows = env.read_text().splitlines()
updated = set()
for i, row in enumerate(rows):
    key = row.split('=', 1)[0].strip()
    if key in values and not row.lstrip().startswith('#'):
        rows[i] = key + '=' + values[key]
        updated.add(key)
for key in values:
    if key not in updated:
        rows.append(key + '=' + values[key])
tmp = env.with_name('.env.temp')
tmp.write_text('\n'.join(rows) + '\n')
tmp.chmod(0o600)
os.replace(str(tmp), str(env))
print('Admin password updated. Restart the server, then sign in at http://127.0.0.1:8000/admin')
print('Your customer accounts, inventory and payment settings are unchanged. All existing sessions have been signed out.')
