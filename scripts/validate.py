"""Validate source evidence and structural integrity; never changes app files."""
import json
import re
from pathlib import Path
from collections import Counter, deque
from flow_builder import PACKAGE, ROOTS


def validate(data, check_sources=True):
    errors = []
    warnings = []
    nodes = {n['id']: n for n in data['nodes']}
    edges = {e['id']: e for e in data['edges']}
    journeys = {j['id']: j for j in data['journeys']}
    for title, values in [('node', data['nodes']), ('edge', data['edges']), ('journey', data['journeys'])]:
        for key, count in Counter(v['id'] for v in values).items():
            if count != 1:
                errors.append(f'Duplicate {title}: {key}')
        for value in values:
            pattern = r'[a-z0-9]+(?:-[a-z0-9]+)*' if title == 'journey' else r'[a-zA-Z_][a-zA-Z0-9_]*'
            if not re.fullmatch(pattern, value['id']):
                errors.append(f'Unsafe {title} identity: {value["id"]}')
    if len({n['key'] for n in data['nodes']}) != len(nodes):
        errors.append('Duplicate canonical node identity')
    allowed = {'screen', 'sheet', 'content', 'decision', 'service', 'unresolved', 'portal', 'entry', 'terminal'}
    evidence = []
    for node in nodes.values():
        if node['kind'] not in allowed:
            errors.append(f'Unknown kind {node["id"]}: {node["kind"]}')
        if not node['sources']:
            errors.append(f'Missing node source: {node["label"]}')
        evidence.extend(node['sources'])
        if node['kind'] == 'decision' and not node.get('predicate'):
            errors.append(f'Missing decision predicate: {node["label"]}')
        if node.get('target') and node['target'] not in journeys:
            errors.append(f'Broken journey link: {node["target"]}')
        for target in node.get('targets', []):
            if target not in journeys:
                errors.append(f'Broken family journey link: {target}')
        if node['repo'] in ('A', 'I') and node['symbol'] in ('LoginActivity', 'IndividualLoginActivity', 'LoginViewController', 'LoginVC'):
            errors.append(f'Obsolete native login in active diagram: {node["symbol"]}')
    for edge in edges.values():
        if edge['from'] not in nodes or edge['to'] not in nodes:
            errors.append(f'Broken edge endpoints: {edge["id"]}')
        if edge['journey'] not in journeys:
            errors.append(f'Unknown edge journey: {edge["id"]}')
        if not edge['sources'] or not edge['label'].strip():
            errors.append(f'Missing edge evidence/label: {edge["id"]}')
        if edge.get('kind') not in ('navigation', 'decision', 'service', 'return', 'reference'):
            errors.append(f'Unknown edge kind: {edge["id"]}')
        evidence.extend(edge['sources'])
    for journey in journeys.values():
        members = set(journey['nodes'])
        if not members:
            errors.append(f'Empty journey {journey["id"]}')
        if not journey['entries']:
            errors.append(f'Journey without entry: {journey["id"]}')
        adjacency = {}
        for key in journey['edges']:
            if key not in edges:
                errors.append(f'Unknown edge {key} in {journey["id"]}')
                continue
            edge = edges[key]
            if edge['from'] not in members or edge['to'] not in members:
                errors.append(f'Edge outside journey {key}')
            adjacency.setdefault(edge['from'], []).append(edge['to'])
        visited = set(journey['entries'])
        pending = deque(visited)
        while pending:
            for end in adjacency.get(pending.popleft(), []):
                if end not in visited:
                    visited.add(end)
                    pending.append(end)
        for node_id in members - visited:
            warnings.append(f'No directed entry path in {journey["id"]}: {nodes[node_id]["label"]}')
        for node_id in members:
            node = nodes[node_id]
            if node['kind'] == 'decision':
                outgoing = [edges[k] for k in journey['edges'] if edges[k]['from'] == node_id]
                if not outgoing:
                    errors.append(f'Decision without branches: {journey["id"]}/{node["label"]}')
    seen = set()
    cache = {}
    if check_sources:
        for source in evidence:
            key = (source['repo'], source['path'], source['line'], source['excerpt'])
            if key in seen:
                continue
            seen.add(key)
            relative = Path(source['path'])
            if source['repo'] not in ROOTS or relative.is_absolute() or '..' in relative.parts:
                errors.append(f'Invalid source boundary: {source["repo"]}:{source["path"]}')
                continue
            file = ROOTS[source['repo']] / relative
            if not file.is_file():
                errors.append(f'Missing source: {file}')
                continue
            if file not in cache:
                cache[file] = file.read_text(errors='replace').splitlines()
            lines = cache[file]
            if source['line'] < 1 or source['line'] > len(lines):
                errors.append(f'Invalid source line: {file}:{source["line"]}')
            elif lines[source['line'] - 1].strip()[:350] != source['excerpt']:
                errors.append(f'Stale source excerpt: {file}:{source["line"]}')
    reconciliation = data.get('reconciliation', [])
    for item in reconciliation:
        if not item.get('status') or not item.get('reason'):
            errors.append(f'Unclassified inventory candidate: {item.get("symbol")}')
        if item.get('node') and item['node'] not in nodes:
            errors.append(f'Invalid reconciliation node: {item["node"]}')
    report = {'passed': not errors, 'errors': errors, 'warnings': warnings,
              'counts': {'journeys': len(journeys), 'nodes': len(nodes), 'edges': len(edges),
                         'source_locations': len(seen), 'inventory_candidates': len(reconciliation)},
              'classification_counts': dict(Counter(i['status'] for i in reconciliation))}
    return report


if __name__ == '__main__':
    data = json.loads((PACKAGE / 'graph.json').read_text())
    report = validate(data)
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report['passed'] else 1)
