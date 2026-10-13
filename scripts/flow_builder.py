"""Small, source-checking vocabulary for authoring the business flow map."""
from pathlib import Path
import hashlib
import re

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
ROOTS = {
    'F': ROOT,
    'A': ROOT.parent / 'smb_android-cherry-pick-compatibility-2026-09-24',
    'I': ROOT.parent / 'smb_ios-cherry-pick-compatibility-2026-09-24',
}


def stable_id(value):
    return 'n_' + hashlib.sha256(value.encode()).hexdigest()[:16]


def friendly(symbol):
    value = re.sub(r'(Screen|ViewController|Activity|View|VC|Widget)$', '', symbol)
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', ' ', value).replace('_', ' ').strip()


class Builder:
    def __init__(self):
        self.nodes = {}
        self.journeys = []
        self.edges = []
        self.current = None
        self._text = {}
        self._classes = {}

    def text(self, repo, path):
        key = (repo, path)
        if key not in self._text:
            self._text[key] = (ROOTS[repo] / path).read_text(errors='replace')
        return self._text[key]

    def ev(self, repo, path, needle, occurrence=1):
        """Require the quoted source text to exist; retain its current line."""
        lines = self.text(repo, path).splitlines()
        matches = [i for i, value in enumerate(lines, 1) if needle in value]
        if len(matches) < occurrence:
            raise ValueError(f'No source match {repo}:{path}: {needle!r} ({occurrence})')
        line = matches[occurrence - 1]
        return {'repo': repo, 'path': path, 'line': line,
                'excerpt': lines[line - 1].strip()[:350]}

    def _index(self, repo):
        if repo in self._classes:
            return
        index = {}
        folders = [ROOTS[repo] / 'lib'] if repo == 'F' else [ROOTS[repo]]
        extensions = {'.dart'} if repo == 'F' else {'.kt', '.java', '.swift', '.h', '.m'}
        for folder in folders:
            for file in sorted(folder.rglob('*')):
                if file.suffix not in extensions or any(p in file.parts for p in ('Pods', '.git', 'build', '.dart_tool', 'node_modules')):
                    continue
                path = str(file.relative_to(ROOTS[repo]))
                content = self.text(repo, path)
                # Preserve newlines for source locations; comments and ObjC
                # @class forward declarations are not concrete screen types.
                searchable = re.sub(r'/\*[\s\S]*?\*/', lambda m: '\n' * m.group().count('\n'), content)
                searchable = re.sub(r'//[^\n]*', '', searchable)
                for match in re.finditer(r'(?<!@)\b(?:class|struct|enum|interface)\s+(\w+)|@interface\s+(\w+)', searchable):
                    if match.group(2) and searchable[match.end():].lstrip().startswith('('):
                        continue  # ObjC category/private extension, not another class.
                    symbol = match.group(1) or match.group(2)
                    line = searchable[:match.start()].count('\n') + 1
                    index.setdefault(symbol, []).append((path, line))
        self._classes[repo] = index

    def journey(self, key, title, family, description='', entry=None):
        if any(j['id'] == key for j in self.journeys):
            raise ValueError(f'Duplicate journey {key}')
        self.current = {'id': key, 'title': title, 'family': family,
                        'description': description, 'nodes': [], 'edges': [],
                        'entries': [], 'notes': []}
        self.journeys.append(self.current)
        if entry:
            self.use(entry)
            self.current['entries'].append(entry)
        return self.current

    def use(self, node):
        if self.current is None:
            raise ValueError('Create a journey before adding nodes')
        if node not in self.current['nodes']:
            self.current['nodes'].append(node)
        return node

    def screen(self, repo, symbol, hint='', label=None, kind='screen', notes=''):
        self._index(repo)
        matches = [(p, l) for p, l in self._classes[repo].get(symbol, []) if hint in p]
        if len(matches) != 1:
            raise ValueError(f'Ambiguous/missing {repo}:{symbol} hint={hint!r}: {matches}')
        path, line = matches[0]
        key = f'{repo}|{path}|{symbol}'
        node = stable_id(key)
        platform = {'F': 'Flutter', 'A': 'Android native', 'I': 'iOS native'}[repo]
        if node not in self.nodes:
            self.nodes[node] = {'id': node, 'key': key, 'label': label or friendly(symbol),
                                'symbol': symbol, 'kind': kind, 'platform': platform,
                                'repo': repo, 'path': path, 'notes': notes,
                                'sources': [{'repo': repo, 'path': path, 'line': line,
                                  'excerpt': self.text(repo, path).splitlines()[line - 1].strip()[:350]}]}
        elif notes and notes not in self.nodes[node]['notes']:
            self.nodes[node]['notes'] += '\n' + notes
        return self.use(node)

    def f(self, symbol, hint='', **kw):
        return self.screen('F', symbol, hint, **kw)

    def a(self, symbol, hint='', **kw):
        return self.screen('A', symbol, hint, **kw)

    def i(self, symbol, hint='', **kw):
        return self.screen('I', symbol, hint, **kw)

    def special(self, key, label, kind, sources, notes='', predicate='', default=None, target=None):
        if kind not in ('decision', 'service', 'unresolved', 'portal', 'entry', 'terminal'):
            raise ValueError(kind)
        scoped_key = f'{kind}|{self.current["id"]}|{key}'
        node = stable_id(scoped_key)
        self.nodes[node] = {'id': node, 'key': scoped_key, 'label': label, 'symbol': '',
                            'kind': kind, 'platform': 'Service' if kind == 'service' else '',
                            'repo': '', 'path': '', 'sources': sources, 'notes': notes,
                            'predicate': predicate, 'default': default, 'target': target}
        return self.use(node)

    def decision(self, key, label, predicate, sources, default=None, notes=''):
        return self.special(key, label, 'decision', sources, notes, predicate, default)

    def service(self, key, label, sources, notes=''):
        return self.special(key, label, 'service', sources, notes)

    def unresolved(self, key, label, sources, notes=''):
        return self.special(key, label, 'unresolved', sources, notes)

    def portal(self, key, label, target, sources, notes=''):
        return self.special(key, label, 'portal', sources, notes, target=target)

    def edge(self, start, end, label, sources, condition='', kind='navigation', default=None, notes=''):
        if not sources:
            raise ValueError(f'Edge {label!r} needs source evidence')
        self.use(start)
        self.use(end)
        index = len(self.edges)
        edge = {'id': f'e_{index:05d}', 'from': start, 'to': end, 'label': label,
                'sources': sources, 'condition': condition, 'kind': kind,
                'default': default, 'notes': notes, 'journey': self.current['id']}
        self.edges.append(edge)
        self.current['edges'].append(edge['id'])
        return edge

    def note(self, text):
        self.current['notes'].append(text)

    def entry(self, node):
        self.use(node)
        if node not in self.current['entries']:
            self.current['entries'].append(node)

    def payload(self):
        return {'nodes': list(self.nodes.values()), 'edges': self.edges,
                'journeys': self.journeys}
