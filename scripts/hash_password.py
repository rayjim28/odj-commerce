import sys
from getpass import getpass
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from security import make_password_hash
password = getpass('Choose a strong admin password: ')
if len(password) < 12:
    raise SystemExit('Use at least 12 characters.')
print('\nAdd this to your .env file (not to GitHub):')
print('ADMIN_PASSWORD_HASH=' + make_password_hash(password))
