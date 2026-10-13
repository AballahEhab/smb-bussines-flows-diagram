"""Record tracked-state fingerprints without writing to any application checkout."""
import hashlib
import json
import subprocess
import sys
from flow_builder import ROOTS, PACKAGE


def capture():
    result = {}
    for alias, root in ROOTS.items():
        def git(*args):
            return subprocess.check_output(['git', '-C', str(root), *args])
        result[alias] = {
            'head': git('rev-parse', 'HEAD').decode().strip(),
            'tracked_status': git('status', '--short', '--untracked-files=no').decode(),
            'tracked_diff_sha256': hashlib.sha256(git('diff', 'HEAD', '--binary')).hexdigest(),
        }
    return result


if __name__ == '__main__':
    name = 'source_after.json' if '--after' in sys.argv else 'source_before.json'
    result = capture()
    (PACKAGE / 'qa' / name).write_text(json.dumps(result, indent=2) + '\n')
    if '--after' in sys.argv:
        before = json.loads((PACKAGE / 'qa/source_before.json').read_text())
        if before != result:
            raise SystemExit('Tracked application or pre-existing changes changed; inspect source snapshots.')
    print('Tracked state recorded and unchanged.' if '--after' in sys.argv else 'Tracked baseline recorded.')
