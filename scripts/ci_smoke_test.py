import sys
import os
from pathlib import Path

def main():
    # check python version
    if sys.version_info < (3, 11):
        print("ERROR: Python 3.11+ required for smoke test")
        return 2

    root = Path.cwd()
    # basic repo sanity
    req = root / 'requirements.txt'
    if not req.exists():
        print('ERROR: requirements.txt missing')
        return 2

    # check essential directories
    upload_dir = root / 'data' / 'uploads'
    index_dir = root / 'db' / 'faiss_index'
    print(f'Found upload dir: {upload_dir.exists()}')
    print(f'Found index dir: {index_dir.exists()}')

    # lightweight checks passed
    print('SMOKE TEST: OK')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
