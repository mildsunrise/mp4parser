'''
Configuration / CLI arg parsing.
'''

import argparse

# extracted from cpython @ 3185a1b, for compatibility with 3.8
class BooleanOptionalAction(argparse.Action):
	def __init__(self, option_strings, dest, default=None, help=None):
		_option_strings = []
		for option_string in option_strings:
			_option_strings.append(option_string)

			if option_string.startswith('--'):
				option_string = '--no-' + option_string[2:]
				_option_strings.append(option_string)

		if help is not None and default is not None and default is not argparse.SUPPRESS:
			help += " (default: %(default)s)"

		super().__init__(
			option_strings=_option_strings, nargs=0,
			dest=dest, default=default, help=help)

	def __call__(self, parser, namespace, values, option_string=None):
		if option_string in self.option_strings:
			setattr(namespace, self.dest, not option_string.startswith('--no-')) # pyright: ignore

	def format_usage(self):
		return ' | '.join(self.option_strings)

parser = argparse.ArgumentParser(
	prog='mp4parser',
	description='Portable ISOBMFF dissector / parser for your terminal.',
)

parser.add_argument('filename', help='input file to parse')

parser.add_argument('-C', '--color',
	action=BooleanOptionalAction,
	help='Colorize the output [default: only if stdout is a terminal]')
parser.add_argument('-r', '--rows',
	type=int, default=7, metavar='N',
	help='Maximum amount of lines to show in tables / lists / hexdumps')
parser.add_argument('--offsets',
	action=BooleanOptionalAction, default=True,
	help='Show file offsets of boxes / blobs')
parser.add_argument('--lengths',
	action=BooleanOptionalAction, default=True,
	help='Show byte sizes of boxes / blobs')
parser.add_argument('--descriptions',
	action=BooleanOptionalAction, default=True,
	help='Show meanings of numerical field values')
parser.add_argument('--defaults',
	action=BooleanOptionalAction, default=False,
	help='Show all fields, even those with default values')
parser.add_argument('--indent',
	type=int, default=4, metavar='N',
	help='Amount of spaces to indent each level by')
parser.add_argument('--bytes-per-line',
	type=int, default=16, metavar='N',
	help='Bytes per line in hexdumps')

boxargs = parser.add_argument_group('box-specific parsing parameters',
	'Though very uncommon, parsing of some boxes may be dependent '
	'on parameters derived from other boxes. These arguments '
	'allow manually supplying parameters to allow parsing the '
	'boxes. Without them, parsing usually falls back to a hexdump.')
boxargs.add_argument('--senc-per-sample-iv',
	type=int, metavar='N',
	help='Value of Per_Sample_IV_Size when parsing senc boxes')
