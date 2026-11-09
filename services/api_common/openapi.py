"""Write or check the OpenAPI snapshots of the role-application APIs."""

import argparse
import json
from pathlib import Path


SNAPSHOT_DIR = Path(__file__).resolve().parents[1] / 'openapi'


def snapshots() -> dict[str, str]:
    from services.authoring_api.app import schema_app
    apps = {'authoring.json': schema_app}
    return {name: json.dumps(factory().openapi(), ensure_ascii=False, sort_keys=True, indent=2) + '\n'
            for name, factory in apps.items()}


def check_snapshots(directory: Path = SNAPSHOT_DIR) -> bool:
    expected = snapshots()
    directory = Path(directory)
    return ({p.name for p in directory.glob('*.json')} == set(expected) and all(
        (directory / name).read_text(encoding='utf-8') == text for name, text in expected.items()))


def write_snapshots(directory: Path = SNAPSHOT_DIR) -> None:
    expected = snapshots()
    directory = Path(directory)
    if directory.exists() and {p.name for p in directory.glob('*.json')} - set(expected):
        raise ValueError('Output contains unexpected JSON files; use a clean snapshot directory')
    directory.mkdir(parents=True, exist_ok=True)
    for name, text in expected.items():
        (directory / name).write_text(text, encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=SNAPSHOT_DIR)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    if args.check:
        if not check_snapshots(args.output):
            parser.exit(1, 'OpenAPI snapshots differ; regenerate and review services/openapi.\n')
    else:
        write_snapshots(args.output)


if __name__ == '__main__':
    main()
