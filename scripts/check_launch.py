"""Read the application's launch checklist without printing secrets or customer data."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

from launch_readiness import launch_readiness


def main():
    data = launch_readiness()
    labels = {'ready': 'PASS', 'todo': 'SETUP', 'review': 'REVIEW'}
    print(f"ODJ launch checks: {data['ready_count']}/{data['total_count']} configured")
    for check in data['checks']:
        print(f"  [{labels[check['status']]}] {check['title']} — {check['note']}")
    print(f"Owner reviews: {data.get('owner_confirmed_count', 0)}/{data.get('owner_total_count', 0)} confirmed")
    print("Checkout:", "OPEN" if data.get('sales_open') else "CLOSED")
    print("Note: configuration checks and owner attestations do not replace payment-provider tests.")


if __name__ == '__main__':
    main()
