"""Read-only staging file checker: doesn't connect to Stripe or emit secrets."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import dotenv_values
from staging_setup import validate_staging_config


def main():
    path = ROOT / '.env.staging'
    if not path.exists():
        raise SystemExit('PENDING: .env.staging not found. Run scripts/setup_staging.py on the staging host.')
    errors = validate_staging_config({key:value or '' for key,value in dotenv_values(path).items()})
    if errors:
        for err in errors:
            print('PENDING:',err)
        raise SystemExit(1)
    print('PASS: Staging configuration looks consistent (no credentials displayed).')
    print('PASS: Payment and email integrations remain disabled.')
    print('Reminder: DNS, TLS, firewall, image persistence, and hosting still need live verification.')

if __name__ == '__main__':
    main()
