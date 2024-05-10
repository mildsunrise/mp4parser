#!/usr/bin/env python3

from subprocess import run
import os
import sys

os.chdir(os.path.dirname(__file__))

case_exts = { '.mp4', '.heif' }
is_case = lambda f: any(f.endswith(ext) for ext in case_exts)
cases = sorted(filter(is_case, os.listdir()))

# we'll be using --append, so make sure to start with an empty dataset
try:
	os.remove('.coverage')
except FileNotFoundError:
	pass

failures = set()

for i, case in enumerate(cases):
	print('\r\x1b[J' + f'[{i:2}/{len(cases):2}] running {case}... ', end='', flush=True)
	res = run(['coverage', 'run', '--append', '../mp4parser.py', case],
		check=True, capture_output=True, encoding='utf-8')
	assert not res.stderr, f'found stderr: {repr(res.stderr)}'

	ref_file = case + '.ref.txt'
	out_file = case + '.out.txt'
	diff_file = case + '.diff'

	try:
		with open(ref_file) as f:
			refout = f.read()
	except FileNotFoundError:
		with open(ref_file, 'w') as f:
			f.write(res.stdout)
		continue

	if res.stdout == refout:
		continue

	with open(out_file, 'w') as f:
		f.write(res.stdout)
	diff = run(['git', 'diff', '--no-index', ref_file, out_file],
		check=False, capture_output=True, encoding='utf-8')
	with open(diff_file, 'w') as f:
		f.write(diff.stdout)

	print('output differs: ')
	failures.add(case)

print('\r\x1b[J' + (
	('\x1b[31m' + f'{len(failures)} of {len(cases)} tests failed.') if failures else
	('\x1b[32m' + 'All tests passed.')
) + '\x1b[m\n')

run(['coverage', 'report'], check=True, cwd='..', env={
	'COVERAGE_FILE': 'tests/.coverage',
	'COVERAGE_RCFILE': 'tests/.coveragerc',
})

if failures: exit(1)
