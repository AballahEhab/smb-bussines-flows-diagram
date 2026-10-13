"""Acceptance checks for the user-requested root, platform and conditional cases."""
import json
from flow_builder import PACKAGE


def check(data):
    nodes = {n['id']: n for n in data['nodes']}
    symbols = {n['symbol'] for n in nodes.values()}
    text = '\n'.join(str(n.get('predicate', '')) + ' ' + n.get('notes', '') for n in nodes.values())
    text += '\n' + '\n'.join(e.get('condition', '') + ' ' + e.get('notes', '') for e in data['edges'])
    selector_ids = {n['id'] for n in nodes.values() if n['symbol'] == 'AccountWithPartyIdScreen'}
    native_gates = {e['to'] for e in data['edges'] if nodes[e['from']]['repo'] == 'A' and nodes[e['to']]['kind'] == 'decision'}
    into_selector = [e for e in data['edges'] if e['to'] in selector_ids and
                     (nodes[e['from']]['repo'] == 'A' or e['from'] in native_gates)]
    from_selector = [e for e in data['edges'] if e['from'] in selector_ids and nodes[e['to']]['repo'] == 'A' and e['kind'] == 'return']
    checks = {
        'flutter_login_root': nodes[data['root']]['symbol'] == 'MainLoginScreen' and nodes[data['root']]['repo'] == 'F',
        'obsolete_native_login_absent': not any(n['repo'] in ('A', 'I') and n['symbol'] in ('LoginActivity', 'IndividualLoginActivity', 'LoginVC', 'LoginViewController') for n in nodes.values()),
        'all_three_ui_platforms': {'F', 'A', 'I'}.issubset({n['repo'] for n in nodes.values()}),
        'sdk_services_are_distinct': all(n['platform'] == 'Service' for n in nodes.values() if n['kind'] == 'service'),
        'old_and_new_pay_layouts': {'AdminPayTabOldScreenBody', 'AdminPayTabScreenBody'}.issubset(symbols) and 'isLegacyPayTabEnabled' in text,
        'legacy_dashboard_complete_predicate': 'isLegacyDashboardEnabled' in text and 'ownerAcceptingRequestId.isEmpty' in text and 'isMigratedUser' in text,
        'runtime_registration_condition': 'bssOnboardingEnabled' in text,
        'guest_shop_configuration': 'isShopTabEnabled' in text and 'discoverInShopTabEnabled' in text,
        'quick_access_and_prepaid': 'QUICK_ACCESS' in text and {'PrepaidHomeScreen', 'IndividualDashboardScreen', 'AdminDashboardScreen'}.issubset(symbols),
        'backend_menu_gates': all(f'menu.id == {value}' in text for value in (11, 3, 7)),
        'role_based_manage_alternatives': {'AdminManageMenuScreen', 'IndividualManageScreen'}.issubset(symbols),
        'bfm_product_branch': 'BFM' in text,
        'device_native_flutter_round_trip': bool(into_selector) and bool(from_selector),
        'notification_alternate_entries': any('notification' in j['id'] for j in data['journeys']),
        'url_alternate_entries': any('url' in j['id'] or 'deeplink' in j['id'] for j in data['journeys']),
        'explicit_unresolved_destinations': any(n['kind'] == 'unresolved' for n in nodes.values()),
        'inventory_fully_classified': bool(data['reconciliation']) and all(r['status'] and r['reason'] for r in data['reconciliation']),
    }
    report = {'passed': all(checks.values()), 'checks': checks,
              'largest_journey_nodes': max(len(j['nodes']) for j in data['journeys'])}
    return report


if __name__ == '__main__':
    data = json.loads((PACKAGE / 'graph.json').read_text())
    report = check(data)
    (PACKAGE / 'qa/acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
