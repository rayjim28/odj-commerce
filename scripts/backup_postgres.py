"""Create a PRIVATE PostgreSQL custom-format backup using pg_dump.

Requires PostgreSQL client tools installed and a valid DATABASE_URL. The dump contains
customer information. No URL, password, host or customer data is printed.
This does NOT include product media; back up MEDIA_DIR separately.
"""
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
from sqlalchemy.engine import make_url

ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT/'.env')


def main():
    url_string = os.getenv('DATABASE_URL','')
    if not url_string.startswith(('postgresql://','postgresql+psycopg://','postgres://')):
        raise SystemExit('This script is only for PostgreSQL. Use backup_local.py for local SQLite.')
    if url_string.startswith('postgres://'):
        url_string = 'postgresql://' + url_string[len('postgres://'):]
    try:
        db = make_url(url_string)
    except Exception:
        raise SystemExit('Unable to parse DATABASE_URL; check it privately.')
    if not db.database:
        raise SystemExit('Database name is missing.')
    target_dir=ROOT/'backups'
    target_dir.mkdir(exist_ok=True)
    target=target_dir/('odj-postgres-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ')+'.dump')
    environment=os.environ.copy()
    environment['PGPASSWORD']=db.password or ''
    command=['pg_dump','--format=custom','--no-owner','--no-acl',
             '--file',str(target),'-h',db.host or 'localhost',
             '-p',str(db.port or 5432),'-U',db.username or 'postgres','-d',db.database]
    try:
        completed=subprocess.run(command,env=environment,stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE,timeout=240)
    except FileNotFoundError:
        raise SystemExit('pg_dump not found. Install the PostgreSQL client tools on the backup machine.')
    except subprocess.TimeoutExpired:
        target.unlink(missing_ok=True)
        raise SystemExit('PostgreSQL backup timed out; no verified backup was created.')
    if completed.returncode != 0 or not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise SystemExit('PostgreSQL backup failed. Verify database access and storage capacity privately.')
    target.chmod(0o600)
    print('Created private PostgreSQL backup:',target)
    print('Verify with pg_restore --list against this file, then rehearse restoration to a separate database.')
    print('Product media is NOT included. Back up your persistent MEDIA_DIR separately.')

if __name__=='__main__': main()
