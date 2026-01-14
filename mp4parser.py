#!/usr/bin/env python3
'''
Core parsing logic
'''

from errno import EPIPE
import sys
import mmap
import itertools
from datetime import datetime, timezone

import options
import boxes
from parser_tables import box_registry
from contextlib import contextmanager
from typing import Optional, Union, Callable, TypeVar, Iterable, List, Tuple
T = TypeVar('T')
Int = int  # needed to avoid a name collision with MVIO.int() in type signatures

args = options.parser.parse_args()
fname = args.filename

mp4file = open(fname, 'rb')
mp4map = mmap.mmap(mp4file.fileno(), 0, prot=mmap.PROT_READ)
mp4mem = memoryview(mp4map)

# FIXME: move this to dataclass, put in options.py
indent_n = args.indent
bytes_per_line = args.bytes_per_line
max_rows = args.rows
max_dump = bytes_per_line * max_rows
show_lengths = args.lengths
show_offsets = args.offsets
show_defaults = args.defaults
show_descriptions = args.descriptions
colorize = sys.stdout.buffer.isatty() \
	if args.color == None else args.color

mask = lambda n: ~((~0) << n)

def main():
	ps = Parser(mp4mem, 0, 0)
	with ps.handle_errors():
		parse_boxes(ps)


# PARSING

class BitReader:
	''' MSB-first bit reader '''

	def __init__(self, buffer: memoryview) -> None:
		self.buffer = memoryview(buffer).cast('B')
		self.pos = 0

	@property
	def remaining(self) -> int:
		return len(self.buffer) * 8 - self.pos

	@property
	def ended(self) -> bool:
		return self.remaining == 0

	def read(self, n = -1) -> int:
		n = n if n >= 0 else self.remaining
		res = 0
		for _ in range(n):
			res <<= 1
			p, b = divmod(self.pos, 8)
			res |= (self.buffer[p] >> (7 - b)) & 1
			self.pos += 1
		return res

	def bit(self) -> bool:
		return bool(self.read(1))

	# support for 'with' (checks all data is consumed)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if exc_type == None and (remaining := self.remaining):
			raise AssertionError(f'{remaining} unparsed trailing bits')

class MVIO:
	''' like BytesIO, but returns memoryviews instead of bytes. it also contains higher-level methods '''

	# core

	def __init__(self, buffer: memoryview, pos=0):
		self.buffer = memoryview(buffer)
		self.pos = pos
		self.locked = False

	@property
	def remaining(self) -> int:
		assert not self.locked
		return len(self.buffer) - self.pos

	@property
	def ended(self) -> bool:
		assert not self.locked
		return self.remaining == 0

	def peek(self, n = -1) -> memoryview:
		assert not self.locked
		n = n if n >= 0 else self.remaining
		res = self.buffer[self.pos:][:n]
		if len(res) != n:
			raise EOFError(f'unexpected EOF (needed {n}, got {len(res)})')
		return res

	def read(self, n = -1) -> memoryview:
		res = self.peek(n)
		self.pos += len(res)
		return res

	@contextmanager
	def capture(self, n = -1):
		res = self.peek(n)
		self.locked = True
		try:
			yield res
			self.pos += len(res)
		finally:
			self.locked = False

	# common primitives

	def bytes(self, n = -1) -> bytes:
		return self.read(n).tobytes()

	def sint(self, n: int) -> int:
		return int.from_bytes(self.read(n), 'big', signed=True)

	def int(self, n: int) -> int:
		return int.from_bytes(self.read(n), 'big')

	def string(self, encoding='utf-8') -> str:
		"""Parse a C-like string."""
		data = self.peek()
		if (size := data.tobytes().find(b'\0')) == -1:
			raise EOFError('EOF while reading string')
		self.pos += size + 1
		return data[:size].tobytes().decode(encoding)

	def pascal_string(self, prefix_size_bytes: Int, encoding: str = 'utf-8') -> str:
		"""Parse a length-prefixed string."""
		try:
			string_length = self.int(prefix_size_bytes)
		except EOFError:
			raise EOFError('EOF while reading string size')
		if self.remaining < string_length:
			raise EOFError(f'EOF before end of string, expected {string_length} bytes, '
				f'found {self.remaining} bytes: {bytes(self.read(self.remaining))}')
		data = self.bytes(string_length)
		return data.decode(encoding)

	@contextmanager
	def bits(self, n = -1):
		with self.capture(n) as res, BitReader(res) as br:
			yield br

	# less common primitives

	def fourcc(self) -> str:
		return self.read(4).tobytes().decode('latin-1')

	def uuid(self) -> str:
		return format_uuid(self.bytes(16))

	def sfixed16(self) -> float:
		# this division is lossless, as it's a power of 2
		return self.sint(4) / (1 << 16)

	def fixed16(self) -> float:
		# this division is lossless, as it's a power of 2
		return self.int(4) / (1 << 16)

	# support for 'with' (checks all data is consumed)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		assert not self.locked, 'stream was left locked(?)'
		if exc_type == None and (remaining := self.remaining):
			raise AssertionError(f'{remaining} unparsed trailing bytes')


# PARSER STATE

class Parser(MVIO):
	''' subclass of MVIO that holds the rest of the parsing state '''

	def __init__(self, buffer: memoryview, start: int, indent: int):
		super().__init__(buffer)
		self.start = start
		self.indent = indent
		self.prefix = ' ' * (self.indent * indent_n)

	@property
	def offset(self) -> int:
		return self.start + self.pos

	def print(self, val: str, header=False):
		prefix = self.prefix
		if header:
			assert self.indent > 0
			prefix = ' ' * ((self.indent - 1) * indent_n)
		print(prefix + val)

	def raw_field(self, name: str, value: str):
		self.print(ansi_fg3(name) + ' ' + ansi_fg1('=') + ' ' + value)

	def field(self,
		name: str, value: T,
		format: Union[str, Callable[[T], str]]=repr,
		default: Optional[T]=None,
		describe: Optional[Callable[[T], Optional[str]]]=None,
	):
		if not show_defaults and value == default:
			return
		text = value.__format__(format) if isinstance(format, str) else format(value)
		if show_descriptions and describe and (description := describe(value)) != None:
			text += f' ({description})'
		self.raw_field(name, text)

	def field_dump(self, name: str, pre_offset:Optional[int] = None, n: int = -1):
		offset = self.offset
		data = self.read(n)
		pre_offset_text = f'{pre_offset:#x}, ' if pre_offset != None else ''
		offset_text = f' @ {pre_offset_text}{offset:#x} .. {self.offset:#x}' if show_offsets else ''
		length_text = f' ({len(data)})' if show_lengths else ''
		self.print(ansi_fg3(name) + ' ' + ansi_fg1('=') + ansi_fg4(offset_text + length_text))
		print_hex_dump(data, self.prefix + '  ')
		return data

	def reserved(self, name: str, value: T, expected: Optional[T] = None):
		ok = (value == expected) if expected != None else \
			(not any(value)) if isinstance(value, bytes) else (not value)
		if not ok: self.print(ansi_fg1(f'invalid {name}: {value}'))

	@contextmanager
	def subparser(self, n: int):
		with self.capture(n) as data:
			with Parser(data, self.offset, self.indent) as ps:
				yield ps

	@contextmanager
	def handle_errors(self):
		try:
			with self: yield self
		except BrokenPipeError:
			# All of this is necessary so that no exceptions are printed when
			# the user pipes `mp4parser --rows 1000 large_file.mp4 | less` and
			# quits with 'q' before getting close to the end of the file.

			# Attempt to close the stdout buffer. This will in turn try to flush
			# its current buffer if not empty, which will also cause a
			# BrokenPipeError but will close the file regardless -- see
			# cpython/Modules/_io/bufferedio.c, _io__Buffered_close_impl().
			# The goal is to force that flush to occur here and have it fail
			# silently, rather than having Python attempt it inside
			# _Py_Finalize() in response to our raise SystemExit, which would
			# print the following useless message to the user in stderr:
			# > Exception ignored while flushing sys.stdout:
			# > BrokenPipeError: [Errno 32] Broken pipe
			try:
				sys.stdout.close()
			except BrokenPipeError:
				pass
			raise SystemExit(EPIPE)
		except Exception as e:
			print_error(e, self.prefix)
			if max_dump and self.buffer:
				print_hex_dump(self.buffer, self.prefix)
			self.read() # we've consumed all data

	# JSON primitives (they don't do much right now)

	@contextmanager
	def in_object(self):
		self.indent += 1
		self.prefix = ' ' * (self.indent * indent_n)
		try:
			yield self
		finally:
			self.indent -= 1
			self.prefix = ' ' * (self.indent * indent_n)

	@contextmanager
	def in_list(self):
		yield self

	@contextmanager
	def in_list_item(self):
		with self.in_object():
			yield self

# FIXME: display errors more nicely (last two frames, type name, you know)


# FORMATTING

def pad_iter(iterable: Iterable[T], size: int, default: T=None) -> Iterable[Optional[T]]:
	iterator = iter(iterable)
	for _ in range(size):
		yield next(iterator, default)

def split_in_groups(iterable: Iterable[T], size: int) -> Iterable[List[T]]:
	iterator = iter(iterable)
	while (group := list(itertools.islice(iterator, size))):
		yield group

def ansi_sgr(p: str, content: str):
	content = str(content)
	if not colorize: return content
	if not content.endswith('\x1b[m'):
		content += '\x1b[m'
	return f'\x1b[{p}m' + content
ansi_bold = lambda x: ansi_sgr('1', x)
ansi_dim = lambda x: ansi_sgr('2', x)
ansi_fg0 = lambda x: ansi_sgr('30', x)
ansi_fg1 = lambda x: ansi_sgr('31', x)
ansi_fg2 = lambda x: ansi_sgr('32', x)
ansi_fg3 = lambda x: ansi_sgr('33', x)
ansi_fg4 = lambda x: ansi_sgr('34', x)
ansi_fg5 = lambda x: ansi_sgr('35', x)
ansi_fg6 = lambda x: ansi_sgr('36', x)
ansi_fg7 = lambda x: ansi_sgr('37', x)

def print_hex_dump(data: memoryview, prefix: str):
	colorize_byte = lambda x, r: \
		ansi_dim(ansi_fg2(x)) if r == 0 else \
		ansi_fg3(x) if chr(r).isascii() and chr(r).isprintable() else \
		ansi_fg2(x)
	format_hex = lambda x: colorize_byte(f'{x:02x}', x) if x != None else '  '
	format_char = lambda x: colorize_byte(x if x.isascii() and (x.isprintable() or x == ' ') else '.', ord(x))

	def format_line(line):
		groups = split_in_groups(pad_iter(line, bytes_per_line), 4)
		hex_part = '  '.join(' '.join(map(format_hex, group)) for group in groups)
		char_part = ''.join(format_char(x) for x in map(chr, line))
		return hex_part + '   ' + char_part

	for line in split_in_groups(data[:max_dump], bytes_per_line):
		print(prefix + format_line(line))
	if len(data) > max_dump:
		print(prefix + '...')

def print_error(exc, prefix: str):
	print(prefix + f'{ansi_bold(ansi_fg1("ERROR:"))} {ansi_fg1(exc)}\n')

def format_uuid(x: bytes) -> str:
	with MVIO(memoryview(x)) as r:
		return '-'.join(r.bytes(i).hex() for i in [4, 2, 2, 2, 6])

def format_fraction(x: Tuple[int, int]):
	assert type(x) is tuple and len(x) == 2 and all(type(i) is int for i in x)
	num, denom = x
	return f'{num}/{denom}'

def format_size(x: Union[Tuple[int, int], Tuple[float, float]]):
	assert type(x) is tuple and len(x) == 2
	width, height = x
	return f'{width} × {height}'

def format_time(x: int) -> str:
	ts = datetime.fromtimestamp(x - 2082844800, timezone.utc)
	return ts.isoformat(' ', 'seconds').replace('+00:00', 'Z')

def decode_language(data: bytes) -> Optional[str]:
	''' decode a (2-byte) packed ISO 639-2/T code '''
	with BitReader(memoryview(data)) as br:
		pad = br.read(1)
		assert not pad, f'invalid language pad {pad}'
		syms = [br.read(5) for _ in range(3)]
	assert all(0 <= (x - 1) < 26 for x in syms), f'invalid language characters: {syms}'
	return ''.join(chr((x - 1) + ord('a')) for x in syms)


# CORE BOX PARSING

info_by_box = {}

def init_boxes():
	for std_desc, boxes in box_registry:
		for k, v in boxes.items():
			if k in info_by_box:
				raise Exception(f'duplicate boxes {k} coming from {std_desc} and {info_by_box[k][0]}')
			info_by_box[k] = (std_desc, *v)
init_boxes()

def parse_box_header(ps: Parser):
	start = ps.pos
	length = ps.int(4)
	btype = ps.fourcc()
	assert btype.isprintable(), f'invalid type {repr(btype)}'

	last_box, large_size = False, False
	if length == 0:
		length = ps.remaining
		last_box = True
	elif length == 1:
		large_size = True
		length = ps.int(8)
	if btype == 'uuid':
		btype = ps.uuid()

	length -= ps.pos - start
	assert length >= 0, f'invalid box length'
	return btype, length, last_box, large_size

def parse_boxes(ps: Parser, contents_fn: Optional[Callable[[str, Parser], T]]=None) -> List[T]:
	result = []
	with ps.in_list():
		while not ps.ended:
			with ps.in_list_item():
				result.append(parse_box(ps, contents_fn or parse_contents))
	return result

def parse_box(ps: Parser, contents_fn: Callable[[str, Parser], T]) -> T:
	offset = ps.offset
	btype, length, last_box, large_size = parse_box_header(ps)
	offset_text = ansi_fg4(f' @ {offset:#x}, {ps.offset:#x} .. {ps.offset + length:#x}') if show_offsets else ''
	length_text = ansi_fg4(f' ({length})') if show_lengths else ''
	name_text = ''
	if show_descriptions and (box_desc := info_by_box.get(btype)):
		desc = box_desc[1]
		if desc.endswith('Box'): desc = desc[:-3]
		name_text = ansi_bold(f' {desc}')
	if last_box:
		offset_text = ' (last)' + offset_text
	if large_size:
		offset_text = ' (large size)' + offset_text
	type_label = btype
	if len(btype) != 4: # it's a UUID
		type_label = f'UUID {btype}'
	ps.print(ansi_bold(f'[{type_label}]') + name_text + offset_text + length_text, header=True)
	with ps.subparser(length) as data, data.handle_errors():
		return contents_fn(btype, data)

nesting_boxes = { 'moov', 'trak', 'mdia', 'minf', 'dinf', 'stbl', 'mvex', 'moof', 'traf', 'mfra', 'meco', 'edts', 'udta', 'sinf', 'schi', 'gmhd', 'cmov' }
# metadata?
nesting_boxes |= { 'aART', 'trkn', 'covr', '----' }

def parse_contents(btype: str, ps: Parser):
	if (handler := getattr(boxes, f'parse_{btype}_box', None)):
		return handler(ps)
	if btype in nesting_boxes:
		return parse_boxes(ps)
	if (data := ps.read()) and max_dump:
		print_hex_dump(data, ps.prefix)

def parse_fullbox(ps: Parser, max_version=0, known_flags=0, default_version=0, default_flags=0):
	version = ps.int(1)
	flags = ps.int(3)
	assert version <= max_version, f'unsupported box version {version}'
	fields = [
		('version', version, default_version, str),
		('flags', flags, default_flags, '{:06x}'.format),
	]
	fields = [ f'{ansi_fg3(k)} {ansi_fg1("=")} {f(v)}'
		for k, v, d, f in fields if show_defaults or v != d ]
	if fields: ps.print(ansi_fg1(', ').join(fields))
	return version, flags


if __name__ == '__main__':
	main()
