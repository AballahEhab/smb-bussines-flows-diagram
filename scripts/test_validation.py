"""Ensure the map cannot silently accept missing sources or corrupted links."""
import copy
import unittest
from flow_builder import Builder
from validate import validate


class GraphValidationTests(unittest.TestCase):
    def setUp(self):
        b = Builder()
        b.journey('test-login', 'Login example', 'Test')
        login = b.f('MainLoginScreen', '/main_login_screen.dart')
        b.entry(login)
        self.source = b.ev('F', 'lib/core/config/global/feature_config.dart', 'isLegacyPayTabEnabled')
        self.decision = b.decision('pay-config', 'Legacy Pay enabled?', 'isLegacyPayTabEnabled', [self.source])
        b.edge(login, self.decision, 'Inspect configuration', [self.source])
        result = b.special('result', 'Continue', 'terminal', [self.source])
        b.edge(self.decision, result, 'Yes', [self.source], condition='isLegacyPayTabEnabled == true')
        self.data = b.payload()

    def test_valid_graph_passes(self):
        self.assertTrue(validate(self.data)['passed'])

    def test_duplicate_identity_is_rejected(self):
        broken = copy.deepcopy(self.data)
        broken['nodes'].append(copy.deepcopy(broken['nodes'][0]))
        self.assertFalse(validate(broken)['passed'])

    def test_dangling_endpoint_is_rejected(self):
        broken = copy.deepcopy(self.data)
        broken['edges'][0]['to'] = 'missing-node'
        self.assertFalse(validate(broken)['passed'])

    def test_stale_source_is_rejected(self):
        broken = copy.deepcopy(self.data)
        broken['edges'][0]['sources'][0]['excerpt'] = 'Source text no longer exists'
        self.assertFalse(validate(broken)['passed'])

    def test_decision_without_branch_is_rejected(self):
        broken = copy.deepcopy(self.data)
        broken['edges'] = broken['edges'][:1]
        broken['journeys'][0]['edges'] = broken['journeys'][0]['edges'][:1]
        self.assertFalse(validate(broken)['passed'])

    def test_native_login_is_rejected(self):
        broken = copy.deepcopy(self.data)
        broken['nodes'][0].update({'symbol': 'LoginActivity', 'repo': 'A'})
        self.assertFalse(validate(broken)['passed'])

    def test_broken_cross_diagram_link_is_rejected(self):
        broken = copy.deepcopy(self.data)
        broken['nodes'][0]['target'] = 'missing-journey'
        self.assertFalse(validate(broken)['passed'])


if __name__ == '__main__':
    unittest.main()
