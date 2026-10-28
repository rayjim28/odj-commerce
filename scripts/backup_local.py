"""Backup local SQLite and uploaded product photos without exposing them to GitHub.
Usage: python scripts/backup_local.py
"""
import sqlite3
import zipfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / 'store.db'
MEDIA = ROOT / 'media'
BACKUPS = ROOT / 'backups'

if __name__ == '__main__':
    if not DB.exists():
        raise SystemExit('No local store.db found. For PostgreSQL, use provider-managed database backups.')
    BACKUPS.mkdir(exist_ok=True)
    name = 'odj-local-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%SZ') + '.zip'
    target = BACKUPS / name
    with tempfile.TemporaryDirectory() as temp:
        staged = Path(temp) / 'store.db'
        source = sqlite3.connect(f'file:{DB}?mode=ro', uri=True)
        try:
            backup = sqlite3.connect(staged)
            try:
                source.backup(backup)
            finally:
                backup.close()
        finally:
            source.close()
        with zipfile.ZipFile(target, 'w', compression=zipfile.ZIP_DEFLATED) as output:
            output.write(staged, 'store.db')
            if MEDIA.exists():
                for f in MEDIA.rglob('*'):
                    if f.is_file() and not f.is_symlink():
                        output.write(f, 'media/' + f.relative_to(MEDIA).as_posix())
    target.chmod(0o600)
    print('Created PRIVATE local backup:', target)
    print('Contains customer data. Keep it private, secure it, and NEVER add it to GitHub.')
