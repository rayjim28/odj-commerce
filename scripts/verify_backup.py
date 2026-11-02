"""Inspect ODJ local backup ZIP, check SQLite integrity and optional manifest.

Does not restore or overwrite the live store. Safe to run against existing V7 backups:
    python scripts/verify_backup.py backups/odj-local-*.zip
"""
import argparse
import hashlib
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path


def verify(path: Path):
    if not path.is_file():
        raise ValueError('Backup archive not found.')
    with zipfile.ZipFile(path) as z:
        if z.testzip() is not None:
            raise ValueError('Backup contains a corrupted ZIP entry.')
        files = [i for i in z.infolist() if not i.is_dir()]
        names = [i.filename for i in files]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP file entries found.')
        if any(i.filename.startswith('/') or '..' in Path(i.filename).parts or '\\' in i.filename
               for i in files):
            raise ValueError('Unsafe archive path detected.')
        if 'store.db' not in names:
            raise ValueError('Archive has no store.db snapshot.')
        with tempfile.TemporaryDirectory(prefix='odj-verify-') as temp:
            database_file = Path(temp) / 'verify.db'
            with z.open('store.db') as src, database_file.open('wb') as dst:
                import shutil
                shutil.copyfileobj(src, dst)
            db = sqlite3.connect(f'file:{database_file}?mode=ro', uri=True)
            try:
                status = db.execute('PRAGMA quick_check').fetchone()[0]
                tables = {name for (name,) in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            finally:
                db.close()
            if status != 'ok' or not {'products', 'customers', 'orders'}.issubset(tables):
                raise ValueError('Database integrity or required tables check failed.')
        manifest_checked = False
        if 'manifest.json' in names:
            manifest = json.loads(z.read('manifest.json'))
            hashes = manifest.get('sha256', {})
            if not hashes or set(hashes) != (set(names) - {'manifest.json'}):
                raise ValueError('Manifest does not match backup contents.')
            for name, expected in hashes.items():
                with z.open(name) as part:
                    h = hashlib.sha256()
                    for chunk in iter(lambda: part.read(1024 * 1024), b''):
                        h.update(chunk)
                    if h.hexdigest() != expected:
                        raise ValueError('Manifest verification failed for ' + name)
            manifest_checked = True
    return {'database_integrity': 'ok', 'files': len(files) - ('manifest.json' in names),
            'hash_manifest_verified': manifest_checked}


def main():
    parser = argparse.ArgumentParser(description='Verify a PRIVATE local ODJ backup without restoring it.')
    parser.add_argument('archive', type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.archive)
    except (ValueError, OSError, zipfile.BadZipFile, sqlite3.DatabaseError) as exc:
        raise SystemExit('BACKUP FAILED VERIFICATION: ' + str(exc))
    print('BACKUP CHECK PASSED: SQLite integrity and essential tables. Files:', result['files'])
    print('SHA-256 manifest:', 'verified' if result['hash_manifest_verified'] else 'not present (older backup)')
    print('No customer information was displayed. No files were restored.')

if __name__ == '__main__':
    main()
