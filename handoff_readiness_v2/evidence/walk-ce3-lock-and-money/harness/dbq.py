"""Ad-hoc read of this pass's disposable database: dbq.py '<python expr file>'.

Usage: python3 dbq.py <script.py>   or   python3 dbq.py -c '<statements>'
"""
import os
import pathlib
import sys

SCRATCH = pathlib.Path(__file__).resolve().parent
WT = SCRATCH.parents[3]

for line in (SCRATCH / 'dbenv').read_text().splitlines():
    if line.startswith('export '):
        key, _, value = line[len('export '):].partition('=')
        os.environ[key] = value

sys.path.insert(0, str(WT / 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'globalstrat.settings')

import django  # noqa: E402
django.setup()

if sys.argv[1] == '-c':
    exec(sys.argv[2])
else:
    exec(pathlib.Path(sys.argv[1]).read_text())
