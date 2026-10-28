"""Interactive first-run config for macOS/Linux."""
import sys, secrets
from pathlib import Path
from getpass import getpass
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from security import make_password_hash
root=Path(__file__).resolve().parents[1]
env=root/'.env'
if env.exists():
    raise SystemExit('.env already exists; will not overwrite your secrets.')
pwd=getpass('Choose a new ODJ admin password (12+ characters): ')
confirm=getpass('Confirm admin password: ')
if len(pwd)<12 or pwd != confirm:
    raise SystemExit('Passwords must match and contain at least 12 characters.')
s=(root/'.env.example').read_text()
s=s.replace('SESSION_SECRET=\n','SESSION_SECRET='+secrets.token_urlsafe(48)+'\n')
s=s.replace('ADMIN_PASSWORD_HASH=\n','ADMIN_PASSWORD_HASH='+make_password_hash(pwd)+'\n')
env.write_text(s)
env.chmod(0o600)
print('Created private .env file. Local SQLite is ready; payments still need Stripe keys.')
print('Next: python scripts/seed.py && uvicorn main:app --reload')
