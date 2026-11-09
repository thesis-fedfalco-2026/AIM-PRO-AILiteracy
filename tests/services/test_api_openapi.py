"""The checked-in OpenAPI snapshot is the API contract; ``--check`` fails on drift (S03)."""

from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import unittest

from services.api_common.openapi import SNAPSHOT_DIR, main, snapshots, write_snapshots
from tests.services.oidc_fixtures import NO_NETWORK
from tests.store_backends import block_network


class OpenApiSnapshotTest(unittest.TestCase):
    def setUp(self):
        block_network(self, NO_NETWORK)

    def run_main(self, *args):
        output = StringIO()
        with redirect_stdout(output), redirect_stderr(output):
            try:
                main(list(args))
            except SystemExit as exit:
                return exit.code or 0, output.getvalue()
        return 0, output.getvalue()

    def test_checked_in_snapshot_matches_the_app(self):
        self.assertEqual(self.run_main('--check'), (0, ''))
        self.assertEqual(sorted(p.name for p in SNAPSHOT_DIR.glob('*.json')), ['authoring.json'])

    def test_snapshot_lists_only_the_skeleton_endpoints(self):
        schema = json.loads((SNAPSHOT_DIR / 'authoring.json').read_text(encoding='utf-8'))
        self.assertEqual(schema['info']['title'], 'ALM Authoring API')
        self.assertEqual({path: sorted(methods) for path, methods in schema['paths'].items()},
                         {'/health': ['get'], '/auth/login': ['get'], '/auth/callback': ['get'],
                          '/auth/session': ['get'], '/auth/logout': ['post']})

    def test_rendering_is_deterministic(self):
        self.assertEqual(snapshots(), snapshots())
        for text in snapshots().values():
            self.assertTrue(text.endswith('}\n'))

    def test_check_fails_on_drift_missing_or_extra_snapshots(self):
        changes = {
            'changed': lambda d: (d / 'authoring.json').write_text(
                (d / 'authoring.json').read_text(encoding='utf-8').replace('ALM Authoring API', 'Other'), encoding='utf-8'),
            'reformatted': lambda d: (d / 'authoring.json').write_text(
                json.dumps(json.loads((d / 'authoring.json').read_text(encoding='utf-8'))), encoding='utf-8'),
            'missing': lambda d: (d / 'authoring.json').unlink(),
            'extra': lambda d: (d / 'learner.json').write_text('{}\n', encoding='utf-8'),
        }
        for name, change in changes.items():
            with self.subTest(name), TemporaryDirectory() as tmp:
                directory = Path(tmp) / 'openapi'
                shutil.copytree(SNAPSHOT_DIR, directory)
                self.assertEqual(self.run_main('--check', '--output', str(directory))[0], 0)
                change(directory)
                status, output = self.run_main('--check', '--output', str(directory))
                self.assertEqual(status, 1)
                self.assertIn('OpenAPI snapshots differ', output)

    def test_write_then_check(self):
        with TemporaryDirectory() as tmp:
            directory = Path(tmp) / 'openapi'
            self.assertEqual(self.run_main('--output', str(directory)), (0, ''))
            self.assertEqual(self.run_main('--check', '--output', str(directory)), (0, ''))
            self.assertEqual((directory / 'authoring.json').read_text(encoding='utf-8'),
                             (SNAPSHOT_DIR / 'authoring.json').read_text(encoding='utf-8'))
            (directory / 'stale.json').write_text('{}\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                write_snapshots(directory)


if __name__ == '__main__':
    unittest.main()
