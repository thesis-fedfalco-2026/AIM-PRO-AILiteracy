"""One-way copy of a SQLite learning store into an empty PostgreSQL store.

    python -m learning.copy_store --from state.sqlite --to postgresql://...

The source is opened read-only. The copy keeps every row and its insertion
order, refuses a target that already holds rows, and commits only when the row
count and SHA-256 digest of every table match the source. It prints those
digests as JSON; it never prints the target URL.
"""

from __future__ import annotations

import argparse
import json
import sys

from learning.store import copy_store, database_errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Copy a SQLite learning store into an empty PostgreSQL store')
    parser.add_argument('--from', dest='source', required=True, help='SQLite learning database (file or sqlite:///path)')
    parser.add_argument('--to', dest='target', required=True, help='postgresql:// URL of an empty learning store')
    args = parser.parse_args(argv)
    try:
        digests = copy_store(args.source, args.target)
    except ValueError as error:
        print(f'Copy not performed: {error}', file=sys.stderr)
        return 2
    except (OSError, *database_errors()):
        print('Copy not performed: check the source file and the target database.', file=sys.stderr)
        return 2
    print(json.dumps({table: digest._asdict() for table, digest in digests.items()}, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
