"""The checked-in development realm and identity map agree and hold no secret (S03, D9)."""

import json
from pathlib import Path
import re
import unittest

from services.api_common.identity import load_identity_map


ROOT = Path(__file__).resolve().parents[2]
REALM = ROOT / 'infra/keycloak/alm-dev-realm.json'
IDENTITY_MAP = ROOT / 'infra/keycloak/identity-map.dev.json'
POLICY = ROOT / 'tests/fixtures/alm/trusted-policy.json'
ISSUER = 'http://127.0.0.1:58080/realms/alm-dev'
PLACEHOLDER = re.compile(r'\$\{[A-Z0-9_]+\}')


class DevIdentityTest(unittest.TestCase):
    def setUp(self):
        self.realm = json.loads(REALM.read_text(encoding='utf-8'))
        self.identities = load_identity_map(IDENTITY_MAP)

    def test_mapped_identities_are_realm_users_with_policy_subjects(self):
        users = {user['id']: user['username'] for user in self.realm['users']}
        subjects = json.loads(POLICY.read_text(encoding='utf-8'))['subjects']
        self.assertEqual({(e.issuer, users.get(e.subject), e.subject_key) for e in self.identities.identities},
                         {(ISSUER, 'dev-admin', 'admin'), (ISSUER, 'dev-learner', 'learner')})
        self.assertLessEqual({e.subject_key for e in self.identities.identities}, set(subjects))
        self.assertIn('dev-unmapped', users.values())

    def test_realm_holds_placeholders_instead_of_secrets(self):
        [client] = self.realm['clients']
        self.assertRegex(client['secret'], PLACEHOLDER)
        for user in self.realm['users']:
            for credential in user['credentials']:
                self.assertRegex(credential['value'], PLACEHOLDER)
        self.assertNotIn('roles', self.realm)

    def test_client_uses_the_code_flow_with_pkce_only(self):
        [client] = self.realm['clients']
        self.assertEqual((client['publicClient'], client['standardFlowEnabled'], client['implicitFlowEnabled'],
                          client['directAccessGrantsEnabled'], client['serviceAccountsEnabled']),
                         (False, True, False, False, False))
        self.assertEqual(client['attributes']['pkce.code.challenge.method'], 'S256')
        self.assertEqual(client['redirectUris'], ['http://127.0.0.1:58000/auth/callback'])


if __name__ == '__main__':
    unittest.main()
