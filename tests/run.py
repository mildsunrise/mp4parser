#!/usr/bin/env python3

from subprocess import run
import os
import sys
from collections import Counter

def delete_if_present(fname: str):
	try:
		os.remove(fname)
	except FileNotFoundError:
		pass

os.chdir(os.path.dirname(__file__))

case_exts = { '.mp4', '.heif', '.m4a', '.mov' }
is_case = lambda f: any(f.endswith(ext) for ext in case_exts)
cases = sorted(filter(is_case, os.listdir()))

# we'll be using --append, so make sure to start with an empty dataset
delete_if_present('.coverage')

out_file = lambda x: x + '.txt'
global_diff = ''
failures = set()

for i, case in enumerate(cases):
	print(f'[{i:2}/{len(cases):2}] running {case}... ', end='', flush=True)
	res = run(['coverage', 'run', '--append', '../mp4parser.py', case],
		check=True, capture_output=True, encoding='utf-8')
	assert not res.stderr, f'found stderr: {repr(res.stderr)}'

	with open(out_file(case), 'w') as f:
		f.write(res.stdout)

	diff = run(['git', 'diff', '--exit-code', out_file(case)],
		check=False, capture_output=True, encoding='utf-8')
	assert not res.stderr, f'found stderr: {repr(res.stderr)}'
	if not diff.returncode:
		assert not diff.stdout, f'found stdout: {repr(res.stdout)}'
		print(end='\r\x1b[J')
		continue

	global_diff += diff.stdout
	diffstats = Counter(line[0] for line in diff.stdout.splitlines()[4:] if line[0] in {'+', '-'})
	print(f'output differs: \x1b[31m-{diffstats["-"]} \x1b[32m+{diffstats["+"]}\x1b[m')
	failures.add(case)

print((
	('\x1b[31m' + f'{len(failures)} of {len(cases)} tests failed.') if failures else
	('\x1b[32m' + 'All tests passed.')
) + '\x1b[m\n', flush=True)

with open('tests.diff', 'w') as f:
	f.write(global_diff)

run(['coverage', 'report'], check=True, cwd='..', env={
	**os.environb,
	b'COVERAGE_FILE': b'tests/.coverage',
	b'COVERAGE_RCFILE': b'tests/.coveragerc',
})

if failures: exit(1)
