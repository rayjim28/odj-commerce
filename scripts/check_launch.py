"""Run: python scripts/check_launch.py — never prints credentials or customer records."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
except ImportError:
    pass
from launch_readiness import launch_readiness

if __name__ == '__main__':
    data = launch_readiness()
    labels = {'ready':'CONFIGURED', 'todo':'TODO', 'review':'REVIEW'}
    print(f"ODJ · Phase 7 launch preparation: {data['ready_count']}/{data['total_count']} configured")
    for check in data['checks']:
        print(f"  [{labels[check['status']]}] {check['title']} — {check['note']}")
    print('\nNo payment credentials were tested; real launch is NOT authorized by this report.')
