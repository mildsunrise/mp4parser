#!/usr/bin/env python3

import re
import os
from subprocess import run

os.chdir(os.path.dirname(__file__))
os.chdir('..')

# we could also import options.py and do parser.format_help(), but I like the wrapping...
helpstr = run(["./mp4parser.py", "--help"],
    check=True, capture_output=True, encoding="utf-8").stdout

helpstr = f'```\n{helpstr}```\n'

with open('README.md', 'r+') as f:
    text = list(f)
    idx1 = text.index('<!-- BEGIN USAGE -->\n')
    idx2 = text.index('<!-- END USAGE -->\n')
    assert idx1 < idx2
    text = text[:idx1+1] + [helpstr] + text[idx2:]
    f.seek(0)
    f.truncate(0)
    f.write(''.join(text))

