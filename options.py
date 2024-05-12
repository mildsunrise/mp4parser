'''
Configuration / CLI arg parsing.
'''

import argparse

parser = argparse.ArgumentParser(
	prog='mp4parser',
	description='Portable ISOBMFF dissector / parser for your terminal.',
)

parser.add_argument('filename')

parser.add_argument('-C', '--color',
	action=argparse.BooleanOptionalAction,
	help='Colorize the output [default: only if stdout is a terminal]')
parser.add_argument('-r', '--rows',
	type=int, default=7, metavar='N',
	help='Maximum amount of lines to show in tables / lists / hexdumps')
parser.add_argument('--offsets',
	action=argparse.BooleanOptionalAction, default=True,
	help='Show file offsets of boxes / blobs')
parser.add_argument('--lengths',
	action=argparse.BooleanOptionalAction, default=True,
	help='Show byte sizes of boxes / blobs')
parser.add_argument('--descriptions',
	action=argparse.BooleanOptionalAction, default=True,
	help='Show meanings of numerical field values')
parser.add_argument('--defaults',
	action=argparse.BooleanOptionalAction, default=False,
	help='Show all fields, even those with default values')
parser.add_argument('--indent',
	type=int, default=4, metavar='N',
	help='Amount of spaces to indent each level by')
parser.add_argument('--bytes-per-line',
	type=int, default=16, metavar='N',
	help='Bytes per line in hexdumps')

