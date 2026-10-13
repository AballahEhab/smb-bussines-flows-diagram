"""Author -> checked graph.json -> Graphviz SVGs -> self-contained offline viewer."""
import argparse
import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
from flow_builder import Builder, PACKAGE, ROOTS
from validate import validate

sys.path.insert(0, str(PACKAGE))


def baseline():
    result = {}
    for repo, root in ROOTS.items():
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()
        result[repo] = {'root': str(root), 'head': git('rev-parse', 'HEAD'),
                        'branch': git('branch', '--show-current'), 'status': git('status', '--short')}
    return result


def reconcile(b):
    """Account for every index candidate; unresolved is deliberately not 'dead'."""
    rows = {}
    def add(repo, path, symbol, category, original=''):
        key = f'{repo}|{path}|{symbol}'
        if key in rows:
            return
        mapped = next((n for n in b.nodes.values() if n['key'] == key), None)
        boundary_edges = [e for e in b.edges if any(re.search(r'\b' + re.escape(symbol) + r'\b', s['excerpt']) for s in e['sources'])] if category in ('route', 'channel', 'native-handler') else []
        if not mapped and boundary_edges:
            mapped = b.nodes[boundary_edges[0]['to']]
        status = 'mapped' if mapped else 'unresolved'
        reason = ('Placed in source-supported journey.' if mapped else
                  'Reference candidate; a complete navigation chain is not established in this map. Not claimed inactive.')
        if category in ('route', 'channel', 'native-handler') and not mapped:
            status, reason = 'registered-only', 'Registry/call surface; registration alone does not prove a reachable screen.'
        if repo == 'F' and symbol == 'ChangeSlotScreen' and not mapped:
            status, reason = 'non-ui', 'Static-content model, not a Flutter widget or navigation screen.'
        if 'Outside the entrypoint import closure' in original:
            status, reason = 'unreachable-candidate', 'Existing static entrypoint audit places this candidate outside its import closure; no mapped active path.'
        if symbol in ('LoginActivity', 'IndividualLoginActivity', 'LoginVC', 'LoginViewController') and repo != 'F':
            status, reason = 'obsolete', 'Native login is excluded by the requested Flutter-login starting point; legacy source may remain.'
        if mapped:
            status = 'in-page-content' if mapped['kind'] == 'content' else 'mapped'
            reason = ('Mapped rendering variant/content inside its owning screen.' if status == 'in-page-content' else
                      'Navigation boundary traced in: ' + ', '.join(sorted({e['journey'] for e in boundary_edges})) if boundary_edges else
                      'Placed in source-supported journey.')
        rows[key] = {'id': key, 'repo': repo, 'path': path, 'symbol': symbol,
                     'category': category, 'status': status, 'reason': reason,
                     'node': mapped['id'] if mapped else None, 'audit_note': original[:700],
                     'journeys': sorted({e['journey'] for e in boundary_edges})}
    # Keep the broad pre-existing census, preserving qualified duplicate class names.
    index = (ROOTS['F'] / 'docs/flutter_screen_reference_index.md').read_text()
    for line in index.splitlines():
        match = re.match(r'\| `([^`]+)` \|.*?\]\(\.\./(lib/[^:)]+)(?::\d+)?\)', line)
        if match:
            add('F', match[2], match[1], 'widget', line)
    for repo in ('F', 'A', 'I'):
        b._index(repo)
        for symbol, locations in b._classes[repo].items():
            for path, _line in locations:
                if repo == 'F':
                    candidate = bool(re.search(r'(Screen|View|Page|BottomSheet|Dialog)$', symbol))
                    category = 'widget'
                else:
                    header = '\n'.join(b.text(repo, path).splitlines()[_line - 1:_line + 7])
                    candidate = bool(re.search(r'(Activity(?:Bulk)?|Fragment|Dialog|BottomSheet|ViewController|VC)$', symbol) or
                                     re.search(r'(?:extends|:)\s*(?:UI(?:TableView|CollectionView)?Controller|UIViewController|[\w]*BaseActivity|AppCompatActivity)\b', header))
                    category = 'native-screen-candidate'
                if candidate:
                    add(repo, path, symbol, category)
    # Current Flutter inbound/named registries and outbound channel declarations.
    paths = ['lib/core/routes/navigation_handler.dart',
             'lib/core/routes/flutter_navigation/app_routes_map.dart',
             'lib/core/routes/named_routes/route_generator.dart']
    for path in paths:
        content = b.text('F', path)
        for symbol in sorted(set(re.findall(r'(?:ChannelMethodConstants|AppRoutes)\.(\w+)', content))):
            add('F', path, symbol, 'route')
    channel = b.text('F', 'lib/channel_controller.dart')
    for symbol in re.findall(r'static\s+(?:Future[^\n{]*?|void|dynamic|bool)\s+(\w+)\s*\(', channel):
        add('F', 'lib/channel_controller.dart', symbol, 'channel')
    # Plist handler mappings are not screen declarations.
    for path in ROOTS['I'].rglob('*.plist'):
        if 'Pods' in path.parts or 'FlutterFW' not in path.parts:
            continue
        content = path.read_text(errors='replace')
        if 'Link' not in content:
            continue
        for symbol in sorted(set(re.findall(r'<string>(\w+Link)</string>', content))):
            add('I', str(path.relative_to(ROOTS['I'])), symbol, 'native-handler')
    for node in b.nodes.values():
        if node['repo']:
            add(node['repo'], node['path'], node['symbol'],
                'rendering-content' if node['kind'] == 'content' else 'visible-ui')
    return sorted(rows.values(), key=lambda r: (r['repo'], r['category'], r['path'], r['symbol']))


def overview(b):
    groups = {}
    for j in list(b.journeys):
        groups.setdefault(j['family'], []).append(j)
    login = next(n['id'] for n in b.nodes.values() if n['symbol'] == 'MainLoginScreen')
    source = b.nodes[login]['sources']
    b.journey('overview', 'Start here · all business journeys', 'Overview',
              'Start at Flutter login. Choose a family to explore screen-by-screen navigation. Each detailed journey states its own entry and conditions.')
    b.entry(login)
    b.nodes[login]['targets'] = [j['id'] for j in b.journeys if j['family'] == 'Login & registration']
    for family, journeys in groups.items():
        hub = b.portal('family-' + family, family, journeys[0]['id'], source,
                       notes='Overview index link. Not a mandatory navigation step; detailed diagrams provide executable source evidence.')
        b.nodes[hub]['targets'] = [j['id'] for j in journeys]
        b.edge(login, hub, 'Explore journeys', source, kind='reference',
               notes='Documentation grouping, not an app transition.')
    b.journeys.insert(0, b.journeys.pop())


def author():
    b = Builder()
    for path in sorted((PACKAGE / 'flows').glob('*.py')):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.build(b)
    families = ['Login & registration', 'Home & accounts', 'Billing & payment',
                'Identity & users', 'Shop', 'Internet orders', 'Manage',
                'Subscriptions', 'Support', 'Orders', 'Notifications', 'Profile & settings']
    b.journeys.sort(key=lambda j: families.index(j['family']) if j['family'] in families else len(families))
    overview(b)
    data = b.payload()
    data.update({'schema_version': 1, 'generated_at': datetime.now(ZoneInfo('Africa/Cairo')).isoformat(),
                 'baseline': baseline(), 'root': next(n['id'] for n in b.nodes.values() if n['symbol'] == 'MainLoginScreen'),
                 'reconciliation': reconcile(b),
                 'limitations': ['Source-supported navigation, not measured production usage.',
                  'Remote portal pages, backend-only menu values and device-only execution are not enumerated as verified screens.',
                  'Unresolved reference candidates are searchable in the inventory; they are not silently declared dead.',
                  'Native login fallbacks are classified obsolete by the requested Flutter-login starting point.']})
    return data


def quote(text):
    return json.dumps(str(text), ensure_ascii=False)


def wrapped(text, width=31):
    return '\n'.join(textwrap.wrap(text, width=width, break_long_words=False, break_on_hyphens=False))


def render_svg(journey, nodes, edges):
    compact = journey['id'] == 'overview'
    spacing = '0.22' if compact else '0.42'
    fontsize = 16 if compact else 13
    dot = ['digraph journey {', f'graph [rankdir=LR, bgcolor="transparent", pad="0.35", nodesep="{spacing}", ranksep="0.75", splines=polyline, fontname="Arial"];',
           f'node [fontname="Arial", fontsize={fontsize}, margin="0.16,0.10", style="filled,rounded", shape=box, penwidth=1.5];',
           'edge [fontname="Arial", fontsize=11, color="#64748b", fontcolor="#334155", arrowsize=0.8];']
    colors = {'Flutter': ('#dbeafe', '#2563eb'), 'Android native': ('#ffedd5', '#c2410c'), 'iOS native': ('#ffedd5', '#c2410c')}
    for key in journey['nodes']:
        n = nodes[key]
        fill, stroke = colors.get(n['platform'], ('#f1f5f9', '#64748b'))
        shape = 'box'
        suffix = n['platform'] or n['kind'].capitalize()
        if n['kind'] == 'decision':
            fill, stroke, shape, suffix = '#fef3c7', '#b45309', 'diamond', 'CONDITION'
        elif n['kind'] == 'service':
            fill, stroke, shape, suffix = '#ede9fe', '#7c3aed', 'ellipse', 'SDK / SERVICE'
        elif n['kind'] == 'portal':
            shape, suffix = 'folder', 'OPEN JOURNEY'
        elif n['kind'] == 'unresolved':
            shape, suffix = 'octagon', 'UNRESOLVED'
        elif n['kind'] in ('sheet', 'content'):
            suffix += ' · ' + ('sheet/dialog' if n['kind'] == 'sheet' else 'in-page content')
        label = wrapped(n['label']) + ('' if compact and n['kind'] == 'portal' else '\n' + suffix)
        if n.get('default') is not None:
            label += '\nDefault: ' + str(n['default'])
        dot.append(f'{key} [id="{key}", label={quote(label)}, fillcolor="{fill}", color="{stroke}", fontcolor="#172033", shape="{shape}", tooltip={quote(n["label"])}];')
    if compact:
        # Three short columns keep the family index readable at ordinary desktop
        # widths instead of fitting twelve tiny labels into one tall column.
        hubs = [key for key in journey['nodes'] if nodes[key]['kind'] == 'portal']
        columns = [hubs[i:i + 4] for i in range(0, len(hubs), 4)]
        for column in columns:
            dot.append('{ rank=same; ' + '; '.join(column) + '; }')
        anchors = [journey['entries'][0]] + [column[0] for column in columns]
        for start, end in zip(anchors, anchors[1:]):
            dot.append(f'{start} -> {end} [style=invis, weight=100];')
    for key in journey['edges']:
        e = edges[key]
        style = 'dashed' if e['kind'] in ('service', 'reference') else 'solid'
        color = '#7c3aed' if e['kind'] == 'service' else ('#0f766e' if e['kind'] == 'return' else '#64748b')
        label = '' if compact else wrapped(e['label'], 36)
        if not compact and e.get('condition'):
            condition = e['condition']
            condition = condition.replace('platform == Android', 'Android only').replace('platform == iOS', 'iOS only').replace('platform == A', 'Android only').replace('platform == I', 'iOS only')
            if condition.lower() not in e['label'].lower():
                short = condition if len(condition) <= 110 else condition[:107] + '…'
                label += '\n' + wrapped('When: ' + short, 36)
        if e.get('default') is True:
            label += '\n[current flag default]'
        elif e.get('default') is False:
            label += '\n[configured alternative]'
        dot.append(f'{e["from"]} -> {e["to"]} [id="{key}", label={quote(label)}, style="{style}", color="{color}", penwidth={2 if e.get("default") is True else 1.1}, constraint={"false" if compact else "true"}, tooltip={quote(e.get("condition") or e["label"])}];')
    dot.append('}')
    source = '\n'.join(dot)
    result = subprocess.run(['dot', '-Tsvg'], input=source, text=True, capture_output=True, check=True, timeout=15)
    svg = re.sub(r'^.*?(?=<svg)', '', result.stdout, flags=re.S)
    return svg, source


def build(data):
    report = validate(data)
    (PACKAGE / 'qa/validation.json').write_text(json.dumps(report, indent=2) + '\n')
    if report['errors']:
        raise SystemExit('\n'.join(report['errors']))
    nodes = {n['id']: n for n in data['nodes']}
    edges = {e['id']: e for e in data['edges']}
    svgs = {}
    (PACKAGE / 'diagrams').mkdir(exist_ok=True)
    for journey in data['journeys']:
        svg, dot = render_svg(journey, nodes, edges)
        svgs[journey['id']] = svg
        (PACKAGE / 'diagrams' / (journey['id'] + '.svg')).write_text(svg)
        (PACKAGE / 'diagrams' / (journey['id'] + '.dot')).write_text(dot)
    template = (PACKAGE / 'scripts/viewer.html').read_text()
    payload = dict(data, diagrams=svgs, validation=report)
    encoded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    (PACKAGE / 'index.html').write_text(template.replace('__FLOW_DATA__', encoded))
    print(json.dumps({'viewer': str(PACKAGE / 'index.html'), **report['counts'],
                      'warnings': len(report['warnings']), 'classification': report['classification_counts']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh-data', action='store_true', help='Re-trace authored flow modules and reconcile current source candidates.')
    args = parser.parse_args()
    target = PACKAGE / 'graph.json'
    if args.refresh_data or not target.exists():
        data = author()
        target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    else:
        data = json.loads(target.read_text())
    build(data)
