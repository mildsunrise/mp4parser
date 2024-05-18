#!/usr/bin/env python3
'''
Main parser code
'''

import sys
import mmap
import itertools
import re
from datetime import datetime, timezone

import options
from parser_tables import *
from contextlib import contextmanager
from typing import Optional, Union, Callable, TypeVar, Iterable
T = TypeVar('T')
T2 = TypeVar('T2')

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


# UTILITIES

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
		return int.from_bytes(self.read(n), signed=True)

	def int(self, n: int) -> int:
		return int.from_bytes(self.read(n))

	def string(self, encoding='utf-8') -> str:
		data = self.peek()
		if (size := data.tobytes().find(b'\0')) == -1:
			raise EOFError('EOF while reading string')
		self.pos += size + 1
		return data[:size].tobytes().decode(encoding)

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

	def reserved(self, name: str, value: T, expected: Optional[T] = None):
		ok = (value == expected) if expected != None else \
			(not any(value)) if isinstance(value, bytes) else (not value)
		assert ok, f'invalid {name}: {value}'

	@contextmanager
	def subparser(self, n: int):
		with self.capture(n) as data:
			with Parser(data, self.offset, self.indent) as ps:
				yield ps

	@contextmanager
	def handle_errors(self):
		try:
			with self: yield self
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

def unique_dict(x: Iterable[tuple[T, T2]]) -> dict[T, T2]:
	r = {}
	for k, v in x:
		assert k not in r, f'duplicate key {repr(k)}: existing {repr(r[k])}, got {repr(v)}'
		r[k] = v
	return r

# FIXME: give it a proper CLI interface
# FIXME: display errors more nicely (last two frames, type name, you know)

def pad_iter(iterable: Iterable[T], size: int, default: T=None) -> Iterable[Optional[T]]:
	iterator = iter(iterable)
	for _ in range(size):
		yield next(iterator, default)

def split_in_groups(iterable: Iterable[T], size: int) -> Iterable[list[T]]:
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
	return '-'.join(x.hex()[s:e] for s, e in itertools.pairwise([0, 8, 12, 16, 20, 32]) )

def format_fraction(x: tuple[int, int]):
	assert type(x) is tuple and len(x) == 2 and all(type(i) is int for i in x)
	num, denom = x
	return f'{num}/{denom}'

def format_size(x: Union[tuple[int, int], tuple[float, float]]):
	assert type(x) is tuple and len(x) == 2
	width, height = x
	return f'{width} × {height}'

def format_time(x: int) -> str:
	ts = datetime.fromtimestamp(x - 2082844800, timezone.utc)
	return ts.isoformat(' ', 'seconds').replace('+00:00', 'Z')


# CORE PARSING

info_by_box = {}
for std_desc, boxes in box_registry:
	for k, v in boxes.items():
		if k in info_by_box:
			raise Exception(f'duplicate boxes {k} coming from {std_desc} and {info_by_box[k][0]}')
		info_by_box[k] = (std_desc, *v)

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

def parse_boxes(ps: Parser, contents_fn=None):
	result = []
	with ps.in_list():
		while not ps.ended:
			with ps.in_list_item():
				result.append(parse_box(ps, contents_fn))
	return result

def parse_box(ps: Parser, contents_fn=None):
		offset = ps.offset
		btype, length, last_box, large_size = parse_box_header(ps)
		offset_text = ansi_fg4(f' @ {offset:#x}, {ps.offset:#x} - {ps.offset + length:#x}') if show_offsets else ''
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
			return (contents_fn or parse_contents)(btype, data)

nesting_boxes = { 'moov', 'trak', 'mdia', 'minf', 'dinf', 'stbl', 'mvex', 'moof', 'traf', 'mfra', 'meco', 'edts', 'udta', 'sinf', 'schi' }
# apple(?) / quicktime metadata
nesting_boxes |= { 'ilst', '\u00a9too', '\u00a9des', '\u00a9nam', '\u00a9day', '\u00a9ART', 'aART', '\u00a9alb', '\u00a9cmt', '\u00a9day', 'trkn', 'covr', '----' }

def parse_contents(btype: str, ps: Parser):
	if (handler := globals().get(f'parse_{btype}_box')):
		return handler(ps)
	if btype in nesting_boxes:
		return parse_boxes(ps)
	if (data := ps.read()) and max_dump:
		print_hex_dump(data, ps.prefix)

def parse_fullbox(ps: Parser):
	version = ps.int(1)
	flags = ps.int(3)
	return version, flags

def parse_skip_box(ps: Parser):
	data = ps.read()
	if any(bytes(data)):
		print_hex_dump(data, ps.prefix)
	else:
		ps.print(ansi_dim(ansi_fg2(f'({len(data)} empty bytes)')))

parse_free_box = parse_skip_box


# BOX CONTAINERS THAT ALSO HAVE A PREPENDED BINARY STRUCTURE

def parse_meta_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	ps.print(f'version = {version}, flags = {box_flags:06x}')
	parse_boxes(ps)

# hack: use a global variable because I'm too lazy to rewrite everything to pass this around
# FIXME: remove this hack, which is sometimes unreliable since there can be inner handlers we don't care about
last_handler_seen = None

def parse_hdlr_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0 and box_flags == 0, 'invalid version / flags'
	# FIXME: a lot of videos seem to break the second assertion (apple metadata?), some break the first
	ps.reserved('pre_defined', ps.bytes(4))
	handler_type = ps.fourcc()
	ps.reserved('reserved', ps.bytes(4 * 3))
	name = ps.bytes().decode('utf-8')
	ps.print(f'handler_type = {repr(handler_type)}, name = {repr(name)}')

	global last_handler_seen
	last_handler_seen = handler_type

def parse_stsd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	entry_count = ps.int(4)
	ps.print(f'version = {version}, entry_count = {entry_count}')
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'

	contents_fn = lambda *a, **b: parse_sample_entry_contents(*a, **b, version=version)
	boxes = parse_boxes(ps, contents_fn=contents_fn)
	assert len(boxes) == entry_count, f'entry_count not matching boxes present'

def parse_sample_entry_contents(btype: str, ps: Parser, version: int):
	ps.reserved('reserved', ps.bytes(6))
	ps.field('data_reference_index', ps.int(2))

	if last_handler_seen == 'vide':
		return parse_video_sample_entry_contents(btype, ps, version)
	if last_handler_seen == 'soun':
		return parse_audio_sample_entry_contents(btype, ps, version)
	if last_handler_seen in {'meta', 'text', 'subt'}:
		return parse_text_sample_entry_contents(btype, ps, version)
	if (data := ps.read()) and max_dump:
		print_hex_dump(data, ps.prefix)

def parse_video_sample_entry_contents(btype: str, ps: Parser, version: int):
	assert version == 0, 'invalid version'

	ps.reserved('reserved', ps.bytes(16))

	ps.field('size', (ps.int(2), ps.int(2)), format_size)
	ps.field('resolution', (ps.fixed16(), ps.fixed16()), format_size, default=(72,)*2)
	ps.reserved('reserved_2', ps.int(4))
	ps.field('frame_count', ps.int(2), default=1)

	with ps.subparser(32) as ps2:
		ps.field('compressorname', ps2.bytes(ps2.int(1)).decode('utf-8'))
		ps.reserved('compressorname_pad', ps2.bytes())

	ps.field('depth', ps.int(2), default=24)
	ps.reserved('pre_defined_3', ps.sint(2), -1)

	parse_boxes(ps)

def parse_audio_sample_entry_contents(btype: str, ps: Parser, version: int):
	assert version <= 1, 'invalid version'

	if version == 0:
		ps.reserved('reserved_1_2', ps.bytes(2))
	else:
		ps.reserved('entry_version', ps.int(2), 1)
	ps.reserved('reserved_1', ps.bytes(6))

	ps.field('channelcount', ps.int(2), default=(2 if version == 0 else None))
	ps.field('samplesize', ps.int(2), default=16)
	ps.reserved('pre_defined_1', ps.int(2))
	ps.reserved('reserved_2', ps.int(2))
	ps.field('samplerate', ps.fixed16(), default=(None if version == 0 else 1))

	parse_boxes(ps)

def parse_text_sample_entry_contents(btype: str, ps: Parser, version: int):
	assert version == 0, 'invalid version'

	fields = {
		# meta
		'metx': ('content_encoding', 'namespace', 'schema_location'),
		'mett': ('content_encoding', 'mime_format'),
		'urim': (),
		# text
		'stxt': ('content_encoding', 'mime_format'),
		# subt
		'sbtt': ('content_encoding', 'mime_format'),
		'stpp': ('namespace', 'schema_location', 'auxiliary_mime_types'),
	}.get(btype, [])
	for field_name in fields:
		ps.field(field_name, ps.string())

	parse_boxes(ps)


# HEADER BOXES

def parse_ftyp_box(ps: Parser):
	ps.field('major_brand', ps.fourcc())
	ps.field('minor_version', ps.int(4), '08x')
	while not ps.ended:
		compatible_brand = ps.fourcc()
		ps.print(f'- compatible: {repr(compatible_brand)}')

parse_styp_box = parse_ftyp_box

def parse_matrix(ps: Parser):
	matrix = [ ps.sfixed16() for _ in range(9) ]
	ps.field('matrix', matrix, default=[1,0,0, 0,1,0, 0,0,0x4000])

def decode_language(syms: list[int]):
	if not any(syms):
		return None
	assert all(0 <= (x - 1) < 26 for x in syms), f'invalid language characters: {syms}'
	return ''.join(chr((x - 1) + ord('a')) for x in syms)

def parse_language(ps: Parser):
	with ps.bits(2) as br:
		ps.reserved('language_pad', br.read(1))
		ps.field('language', decode_language([br.read(5) for _ in range(3)]), str)

def parse_mfhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	ps.field('sequence_number', ps.int(4))

def parse_mvhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	ps.field('version', version)
	wsize = [4, 8][version]

	ps.field('creation_time', ps.int(wsize), format_time, default=0)
	ps.field('modification_time', ps.int(wsize), format_time, default=0)
	ps.field('timescale', ps.int(4))
	ps.field('duration', ps.int(wsize), default=mask(wsize))
	ps.field('rate', ps.sfixed16(), default=1)
	ps.field('volume', ps.sint(2) / (1 << 8), default=1)
	ps.reserved('reserved_1', ps.int(2))
	ps.reserved('reserved_2', ps.int(4))
	ps.reserved('reserved_3', ps.int(4))

	parse_matrix(ps)

	ps.reserved('pre_defined', ps.bytes(6 * 4))
	ps.field('next_track_ID', ps.int(4), default=mask(32))

def parse_tkhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	ps.print(f'version = {version}, flags = {box_flags:06x}')
	wsize = [4, 8][version]
	# FIXME: display flags!!

	ps.field('creation_time', ps.int(wsize), format_time, default=0)
	ps.field('modification_time', ps.int(wsize), format_time, default=0)
	ps.field('track_ID', ps.int(4))
	ps.reserved('reserved_1', ps.int(4))
	ps.field('duration', ps.int(wsize), default=mask(wsize))
	ps.reserved('reserved_2', ps.int(4))
	ps.reserved('reserved_3', ps.int(4))
	ps.field('layer', ps.sint(2), default=0)
	ps.field('alternate_group', ps.sint(2), default=0)
	ps.field('volume', ps.sint(2) / (1 << 8), default=1)
	ps.reserved('reserved_4', ps.int(2))
	parse_matrix(ps)
	ps.field('size', (ps.fixed16(), ps.fixed16()), format_size, default=(0, 0))

def parse_mdhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	ps.field('version', version)
	wsize = [4, 8][version]

	ps.field('creation_time', ps.int(wsize), format_time, default=0)
	ps.field('modification_time', ps.int(wsize), format_time, default=0)
	ps.field('timescale', ps.int(4))
	ps.field('duration', ps.int(wsize), default=mask(wsize))
	parse_language(ps)
	ps.reserved('pre_defined_1', ps.int(2))

def parse_mehd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	ps.field('version', version)
	wsize = [4, 8][version]

	fragment_duration = ps.int(wsize)
	ps.field('fragment_duration', fragment_duration)

def parse_smhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	ps.field('balance', ps.sint(2), default=0)
	ps.reserved('reserved', ps.int(2))

def parse_vmhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 1, f'invalid flags: {box_flags}'

	ps.field('graphicsmode', ps.int(2), default=0)
	ps.field('opcolor', tuple(ps.int(2) for _ in range(3)), default=(0,)*3)

def format_sdtp_value(x: int) -> str:
	return ['unknown', 'yes', 'no', ansi_fg1('reserved')][x]

def parse_sample_flags(ps: Parser, name: str):
	ps.print(f'{name} =')
	with ps.in_object(), ps.bits(4) as br:
		ps.reserved('reserved', br.read(4))

		# equivalent meanings as for 'sdtp'
		ps.field('is_leading', br.read(2), default=0, describe=format_sdtp_value)
		ps.field('sample_depends_on', br.read(2), default=0, describe=format_sdtp_value)
		ps.field('sample_is_depended_on', br.read(2), default=0, describe=format_sdtp_value)
		ps.field('sample_has_redundancy', br.read(2), default=0, describe=format_sdtp_value)

		ps.field('sample_padding_value', br.read(3), default=0)
		ps.field('sample_is_non_sync_sample', br.bit(), default=0)
		ps.field('sample_degradation_priority', br.read(16), default=0)

def parse_trex_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	ps.field('track_ID', ps.int(4))
	ps.field('default_sample_description_index', ps.int(4))
	ps.field('default_sample_duration', ps.int(4))
	ps.field('default_sample_size', ps.int(4))
	parse_sample_flags(ps, 'default_sample_flags')

# TODO: mvhd, trhd, mdhd
# FIXME: vmhd, smhd, hmhd, sthd, nmhd
# FIXME: mehd


# NON CODEC-SPECIFIC BOXES

def parse_ID32_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	ps.print(f'flags = {box_flags:06x}')
	parse_language(ps)
	ps.print(f'ID3v2 data =')
	print_hex_dump(ps.read(), ps.prefix + '  ')

def parse_dref_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	entry_count = ps.int(4)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'
	ps.print(f'version = {version}, entry_count = {entry_count}')

	boxes = parse_boxes(ps)
	assert len(boxes) == entry_count, f'entry_count not matching boxes present'

def parse_url_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	ps.print(f'flags = {box_flags:06x}')
	if ps.ended: return
	ps.field('location', ps.string())

def parse_urn_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	ps.print(f'flags = {box_flags:06x}')
	if ps.ended: return
	ps.field('location', ps.string())
	if ps.ended: return
	ps.field('name', ps.string())

globals()['parse_url _box'] = parse_url_box
globals()['parse_urn _box'] = parse_urn_box

def format_colour_type(colour_type: str):
	return {
		'nclx': 'on-screen colours',
		'rICC': 'restricted ICC profile',
		'prof': 'unrestricted ICC profile',
	}.get(colour_type)

def parse_colr_box(ps: Parser):
	ps.field('colour_type', colour_type := ps.fourcc(), describe=format_colour_type)
	if colour_type == 'nclx':
		ps.field('colour_primaries', ps.int(2))
		ps.field('transfer_characteristics', ps.int(2))
		ps.field('matrix_coefficients', ps.int(2))
		with ps.bits(1) as br:
			ps.field('full_range_flag', br.bit())
			ps.reserved('reserved', br.read())
	else:
		name = 'ICC_profile' if colour_type in { 'rICC', 'prof' } else 'data'
		ps.print(f'{name} =')
		print_hex_dump(ps.read(), ps.prefix + '  ')

def parse_btrt_box(ps: Parser):
	ps.field('bufferSizeDB', ps.int(4))
	ps.field('maxBitrate', ps.int(4))
	ps.field('avgBitrate', ps.int(4))

def parse_pasp_box(ps: Parser):
	ps.field('pixel aspect ratio', (ps.int(4), ps.int(4)), format_fraction)

def parse_clap_box(ps: Parser):
	ps.field('cleanApertureWidth', (ps.int(4), ps.int(4)), format_fraction)
	ps.field('cleanApertureHeight', (ps.int(4), ps.int(4)), format_fraction)
	ps.field('horizOff', (ps.int(4), ps.int(4)), format_fraction)
	ps.field('vertOff', (ps.int(4), ps.int(4)), format_fraction)

def parse_sgpd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'
	ps.field('version', version)

	ps.field('grouping_type', ps.fourcc())
	if version == 1:
		ps.field('default_length', default_length := ps.int(4))
	elif version >= 2:
		ps.field('default_sample_description_index', ps.int(4))

	entry_count = ps.int(4)
	for i in range(entry_count):
		ps.print(f'- entry {i+1}:')
		if version == 1:
			if (description_length := default_length) == 0:
				description_length = ps.int(4)
				ps.print(f'  description_length = {description_length}')
			description = ps.read(description_length)
			print_hex_dump(description, ps.prefix + '  ')
		else:
			raise NotImplementedError('TODO: parse box')


# CODEC-SPECIFIC BOXES

def parse_avcC_box(ps: Parser):
	if (configurationVersion := ps.int(1)) != 1:
		raise AssertionError(f'invalid configuration version: {configurationVersion}')
	ps.field('profile / compat / level', ps.bytes(3).hex(), str)
	with ps.bits(1) as br:
		ps.reserved('reserved_1', br.read(6), mask(6))
		ps.field('lengthSizeMinusOne', br.read(2))

	with ps.bits(1) as br:
		ps.reserved('reserved_2', br.read(3), mask(3))
		numOfSequenceParameterSets = br.read(5)
	for i in range(numOfSequenceParameterSets):
		ps.print(f'- SPS: {ps.bytes(ps.int(2)).hex()}')
	numOfPictureParameterSets = ps.int(1)
	for i in range(numOfPictureParameterSets):
		ps.print(f'- PPS: {ps.bytes(ps.int(2)).hex()}')

	# FIXME: parse extensions

def parse_svcC_box(ps: Parser):
	if (configurationVersion := ps.int(1)) != 1:
		raise AssertionError(f'invalid configuration version: {configurationVersion}')
	ps.field('profile / compat / level', ps.bytes(3).hex(), str)
	with ps.bits(1) as br:
		ps.field('complete_represenation', br.bit())
		ps.reserved('reserved_1', br.read(5), mask(5))
		ps.field('lengthSizeMinusOne', br.read(2))

	with ps.bits(1) as br:
		ps.reserved('reserved_2', br.read(1), 0)
		numOfSequenceParameterSets = br.read(7)
	for i in range(numOfSequenceParameterSets):
		ps.print(f'- SPS: {ps.bytes(ps.int(2)).hex()}')
	numOfPictureParameterSets = ps.int(1)
	for i in range(numOfPictureParameterSets):
		ps.print(f'- PPS: {ps.bytes(ps.int(2)).hex()}')

def parse_hvcC_box(ps: Parser):
	if (configurationVersion := ps.int(1)) != 1:
		raise AssertionError(f'invalid configuration version: {configurationVersion}')

	with ps.bits(1) as br:
		ps.field('general_profile_space', br.read(2))
		ps.field('general_tier_flag', br.read(1))
		ps.field('general_profile_idc', br.read(5), '02x')
	ps.field('general_profile_compatibility_flags', ps.bytes(4).hex(), str)
	ps.field('general_constraint_indicator_flags', ps.bytes(6).hex(), str)
	ps.field('general_level_idc', ps.bytes(1).hex(), str)

	with ps.bits(2) as br:
		ps.reserved('reserved', br.read(4), mask(4))
		ps.field('min_spatial_segmentation_idc', br.read())
	with ps.bits(1) as br:
		ps.reserved('reserved', br.read(6), mask(6))
		ps.field('parallelismType', br.read())
	with ps.bits(1) as br:
		ps.reserved('reserved', br.read(6), mask(6))
		ps.field('chromaFormat', br.read())
	with ps.bits(1) as br:
		ps.reserved('reserved', br.read(5), mask(5))
		ps.field('bitDepthLumaMinus8', br.read())
	with ps.bits(1) as br:
		ps.reserved('reserved', br.read(5), mask(5))
		ps.field('bitDepthChromaMinus8', br.read())

	ps.field('avgFrameRate', ps.int(2))
	with ps.bits(1) as br:
		ps.field('constantFrameRate', br.read(2))
		ps.field('numTemporalLayers', br.read(3))
		ps.field('temporalIdNested', br.bit())
		ps.field('lengthSizeMinusOne', br.read(2))

	numOfArrays = ps.int(1)
	#ps.field('numOfArrays', numOfArrays)
	for i in range(numOfArrays):
		ps.print(f'- array {i}:')

		with ps.bits(1) as br:
			array_completeness = br.bit()
			ps.print(f'    array_completeness = {bool(array_completeness)}')
			ps.reserved('reserved', br.read(1), 0)
			NAL_unit_type = br.read(6)
			ps.print(f'    NAL_unit_type = {NAL_unit_type}')

		numNalus = ps.int(2)
		#ps.print(f'    numNalus = {numNalus}')
		for n in range(numNalus):
			ps.print(f'    - NALU {n}')
			print_hex_dump(ps.read(ps.int(2)), ps.prefix + '        ')

# FIXME: implement av1C

def parse_esds_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'
	with ps.in_object():
		parse_descriptor(ps, expected=3)

parse_iods_box = parse_esds_box

def parse_m4ds_box(ps: Parser):
	parse_descriptors(ps)

def parse_dOps_box(ps: Parser):
	if (Version := ps.int(1)) != 0:
		raise AssertionError(f'invalid Version: {Version}')

	ps.field('OutputChannelCount', OutputChannelCount := ps.int(1))
	ps.field('PreSkip', ps.int(2))
	ps.field('InputSampleRate', ps.int(4))
	ps.field('OutputGain', ps.sint(2) / (1 << 8))
	ps.field('ChannelMappingFamily', ChannelMappingFamily := ps.int(1))
	if ChannelMappingFamily != 0:
		ps.field('StreamCount', ps.int(1))
		ps.field('CoupledCount', ps.int(1))
		ps.field('ChannelMapping', list(ps.bytes(OutputChannelCount)))


# TABLES

def parse_elst_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version <= 1, f'invalid version: {version}'
	ps.field('version', version)
	wsize = [4, 8][version]

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		segment_duration = ps.int(wsize)
		media_time = ps.sint(wsize)
		media_rate = ps.sfixed16()
		if i < max_rows:
			ps.print(f'[edit segment {i:3}] duration = {segment_duration:6}, media_time = {media_time:6}, media_rate = {media_rate}')
	if entry_count > max_rows:
		ps.print('...')

def parse_sidx_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version <= 1, f'invalid version: {version}'
	ps.field('version', version)
	wsize = [4, 8][version]

	ps.field('reference_ID', ps.int(4))
	ps.field('timescale', ps.int(4))
	ps.field('earliest_presentation_time', ps.int(wsize))
	ps.field('first_offset', ps.int(wsize))
	ps.reserved('reserved_1', ps.int(2))
	ps.field('reference_count', reference_count := ps.int(2))
	for i in range(reference_count):
		with ps.bits(4) as br:
			reference_type = br.read(1)
			referenced_size = br.read(31)
		subsegment_duration = ps.int(4)
		with ps.bits(4) as br:
			starts_with_SAP = br.read(1)
			SAP_type = br.read(3)
			SAP_delta_time = br.read(28)
		if i < max_rows:
			ps.print(f'[reference {i:3}] type = {reference_type}, size = {referenced_size}, duration = {subsegment_duration}, starts_with_SAP = {starts_with_SAP}, SAP_type = {SAP_type}, SAP_delta_time = {SAP_delta_time}')
	if reference_count > max_rows:
		ps.print('...')

def parse_stts_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	sample, time = 1, 0
	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_count = ps.int(4)
		sample_delta = ps.int(4)
		if i < max_rows:
			ps.print(f'[entry {i:3}] [sample = {sample:6}, time = {time:6}] sample_count = {sample_count:5}, sample_delta = {sample_delta:5}')
		sample += sample_count
		time += sample_count * sample_delta
	if entry_count > max_rows:
		ps.print('...')
	ps.print(f'[samples = {sample-1:6}, time = {time:6}]')

def parse_ctts_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version <= 1, f'invalid version: {version}'
	ps.field('version', version)

	sample = 1
	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_count = ps.int(4)
		sample_offset = [ps.sint, ps.int][version](4)
		if i < max_rows:
			ps.print(f'[entry {i:3}] [sample = {sample:6}] sample_count = {sample_count:5}, sample_offset = {sample_offset:5}')
		sample += sample_count
	if entry_count > max_rows:
		ps.print('...')
	ps.print(f'[samples = {sample-1:6}]')

def parse_stsc_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	sample, last = 1, None
	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		first_chunk = ps.int(4)
		samples_per_chunk = ps.int(4)
		sample_description_index = ps.int(4)
		if last != None:
			last_chunk, last_spc = last
			assert first_chunk > last_chunk
			sample += last_spc * (first_chunk - last_chunk)
		if i < max_rows:
			ps.print(f'[entry {i:3}] [sample = {sample:6}] first_chunk = {first_chunk:5}, samples_per_chunk = {samples_per_chunk:4}, sample_description_index = {sample_description_index}')
		last = first_chunk, samples_per_chunk
	if entry_count > max_rows:
		ps.print('...')

def parse_stsz_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	ps.field('sample_size', sample_size := ps.int(4), default=0)
	ps.field('sample_count', sample_count := ps.int(4))
	if sample_size == 0:
		for i in range(sample_count):
			sample_size = ps.int(4)
			if i < max_rows:
				ps.print(f'[sample {i+1:6}] sample_size = {sample_size:5}')
		if sample_count > max_rows:
			ps.print('...')

def parse_stco_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		chunk_offset = ps.int(4)
		if i < max_rows:
			ps.print(f'[chunk {i+1:5}] offset = {chunk_offset:#08x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_co64_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		chunk_offset = ps.int(8)
		if i < max_rows:
			ps.print(f'[chunk {i+1:5}] offset = {chunk_offset:#016x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_stss_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_number = ps.int(4)
		if i < max_rows:
			ps.print(f'[sync sample {i:5}] sample_number = {sample_number:6}')
	if entry_count > max_rows:
		ps.print('...')

def parse_sbgp_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version <= 1, f'invalid version: {version}'
	ps.field('version', version)

	ps.field('grouping_type', ps.fourcc())
	if version == 1:
		ps.field('grouping_type_parameter', ps.int(4))

	sample = 1
	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_count = ps.int(4)
		group_description_index = ps.int(4)
		if i < max_rows:
			ps.print(f'[entry {i+1:5}] [sample = {sample:6}] sample_count = {sample_count:5}, group_description_index = {group_description_index:5}')
		sample += sample_count
	if entry_count > max_rows:
		ps.print('...')
	ps.print(f'[samples = {sample-1:6}]')

def parse_saiz_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	if box_flags & 1:
		ps.field('aux_info_type', ps.fourcc())
		ps.field('aux_info_type_parameter', ps.int(4), '#x')

	ps.field('default_sample_info_size', default_sample_info_size := ps.int(1))
	ps.field('sample_count', sample_count := ps.int(4))
	if default_sample_info_size == 0:
		for i in range(sample_count):
			sample_info_size = ps.int(1)
			if i < max_rows:
				ps.print(f'[sample {i+1:6}] sample_info_size = {sample_info_size:5}')
		if sample_count > max_rows:
			ps.print('...')

def parse_saio_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	ps.print(f'version = {version}, flags = {box_flags:06x}')
	wsize = [4, 8][version]

	if box_flags & 1:
		ps.field('grouping_type_parameter', ps.int(4))

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		offset = ps.int(wsize)
		if i < max_rows:
			ps.print(f'[entry {i+1:6}] offset = {offset:#08x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_tfdt_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	wsize = [4, 8][version]

	ps.print(f'version = {version}, flags = {box_flags:06x}')
	ps.field('baseMediaDecodeTime', ps.int(wsize))

def parse_tfhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'

	ps.print(f'version = {version}, flags = {box_flags:06x}')
	ps.field('track_ID', ps.int(4))
	if box_flags & 0x10000:  # duration‐is‐empty
		ps.print('duration-is-empty flag set')
	if box_flags & 0x20000:  # default-base-is-moof
		ps.print('default-base-is-moof flag set')

	if box_flags & 0x1:  # base‐data‐offset‐present
		ps.field('base_data_offset', ps.int(8))
	if box_flags & 0x2:  # sample-description-index-present
		ps.field('sample_description_index', ps.int(4))
	if box_flags & 0x8:  # default‐sample‐duration‐present
		ps.field('default_sample_duration', ps.int(4))
	if box_flags & 0x10:  # default‐sample‐size‐present
		ps.field('default_sample_size', ps.int(4))
	if box_flags & 0x20:  # default‐sample‐flags‐present
		parse_sample_flags(ps, 'default_sample_flags')

def parse_trun_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	ps.field('sample_count', sample_count := ps.int(4))
	if box_flags & (1 << 0):
		ps.field('data_offset', ps.sint(4), '#x')
	if box_flags & (1 << 2):
		parse_sample_flags(ps, 'first_sample_flags')

	s_offset = 0
	s_time = 0
	for s_idx in range(sample_count):
		s_text = []
		if box_flags & (1 << 8):
			sample_duration = ps.int(4)
			s_text.append(f'time={s_time:7} + {sample_duration:5}')
			s_time += sample_duration
		if box_flags & (1 << 9):
			sample_size = ps.int(4)
			s_text.append(f'offset={s_offset:#9x} + {sample_size:5}')
			s_offset += sample_size
		if box_flags & (1 << 10):
			sample_flags = ps.int(4)
			s_text.append(f'flags={sample_flags:08x}') # FIXME: use parse_sample_flags here when we expand this
		if box_flags & (1 << 11):
			sample_composition_time_offset = [ps.int, ps.sint][version](4)
			s_text.append(f'{sample_composition_time_offset}')
		if s_idx < max_rows:
			ps.print(f'[sample {s_idx:4}] {", ".join(s_text)}')
	if sample_count > max_rows:
		ps.print('...')

# FIXME: describe handlers, boxes (from RA, also look at the 'handlers' and 'unlisted' pages), brands


# DRM boxes

def parse_frma_box(ps: Parser):
	ps.field('data_format', ps.fourcc())

def parse_schm_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	ps.field('scheme_type', ps.fourcc())
	ps.field('scheme_version', ps.int(4), '#x')
	if box_flags & 1:
		ps.field('scheme_uri', ps.string())

def parse_tenc_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	ps.reserved('reserved_1', ps.int(1), 0)

	if version > 0:
		with ps.bits(1) as br:
			ps.field('default_crypt_byte_block', br.read(4))
			ps.field('default_skip_byte_block', br.read(4))
	else:
		ps.reserved('reserved_2', ps.int(1), 0)

	ps.field('default_isProtected', default_isProtected := ps.int(1))
	ps.field('default_Per_Sample_IV_Size', default_Per_Sample_IV_Size := ps.int(1))
	ps.field('default_KID', ps.bytes(16).hex(), str)
	if default_isProtected == 1 and default_Per_Sample_IV_Size == 0:
		ps.field('default_constant_IV', ps.bytes(ps.int(1)).hex(), str)

def format_system_id(SystemID: str):
	return protection_systems.get(SystemID, (None, None))[0]

def parse_pssh_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	ps.field('SystemID', ps.uuid(), str, describe=format_system_id)

	if version > 0:
		KID_count = ps.int(4)
		for i in range(KID_count):
			ps.print(f'- KID: {ps.bytes(16).hex()}')

	ps.print(f'Data =')
	print_hex_dump(ps.read(ps.int(4)), ps.prefix + '  ')


# MPEG-4 part 1 DESCRIPTORS (based on 2010 edition)
# (these aren't specific to ISOBMFF and so we shouldn't parse them buuuut
# they're still part of MPEG-4 and not widely known so we'll make an exception)

def parse_descriptors(ps: Parser, **kwargs):
	with ps.in_list():
		while not ps.ended:
			with ps.in_list_item():
				parse_descriptor(ps, **kwargs)

def parse_descriptor(ps: Parser, expected=None, namespace='default', contents_fn=None):
	tag = ps.int(1)
	assert tag != 0x00 and tag != 0xFF, f'forbidden tag number: {tag}'

	size_start = ps.offset
	size = 0
	while True:
		with ps.bits(1) as br:
			next_byte = br.bit()
			size = (size << 7) | br.read(7)
		if not next_byte: break

	n_size_bytes = ps.offset - size_start
	size_text = ''
	if size.bit_length() <= (n_size_bytes - 1) * 7:
		size_text = ansi_fg4(f' ({n_size_bytes} length bytes)')

	def get_class_chain(k):
		r = [k]
		while k['base_class'] != None:
			k = class_registry[k['base_class']][1]
			r.append(k)
		return r
	nsdata = descriptor_namespaces[namespace]
	labels = []
	klasses = []
	if tag in nsdata['tag_registry']:
		klasses = get_class_chain(nsdata['tag_registry'][tag])
	else:
		labels.append(ansi_fg4('reserved for ISO use' if tag < nsdata['user_private'] else 'user private'))
		if k := next((k for (s, e, k) in nsdata['ranges'] if s <= tag < e), None):
			klasses = get_class_chain(class_registry[k][1])
	labels += [ ansi_bold(k['name']) for k in klasses ]

	ps.print(ansi_bold(f'[{tag}]') + (' ' + ' -> '.join(labels) if show_descriptions else '') + size_text, header=True)
	with ps.subparser(size) as data, data.handle_errors():
		(contents_fn or parse_descriptor_contents)(tag, klasses, data)

def parse_descriptor_contents(tag: int, klasses, ps: Parser):
	for k in klasses[::-1]:
		if 'handler' not in k: break
		k['handler'](ps)
	if (data := ps.read()) and max_dump:
		print_hex_dump(data, ps.prefix)

def parse_BaseDescriptor_descriptor(ps: Parser):
	pass

def parse_ObjectDescriptorBase_descriptor(ps: Parser):
	pass

def parse_ExtensionDescriptor_descriptor(ps: Parser):
	pass

def parse_OCI_Descriptor_descriptor(ps: Parser):
	pass

def parse_IP_IdentificationDataSet_descriptor(ps: Parser):
	pass

def parse_ES_Descriptor_descriptor(ps: Parser):
	ps.field('ES_ID', ps.int(2))
	with ps.bits(1) as br:
		streamDependenceFlag = br.bit()
		URL_Flag = br.bit()
		OCRstreamFlag = br.bit()
		ps.field('streamPriority', br.read(5))
	if streamDependenceFlag:
		ps.field('dependsOn_ES_ID', ps.int(2))
	if URL_Flag:
		ps.field('URL', ps.bytes(ps.int(1)).decode('utf-8'))
	if OCRstreamFlag:
		ps.field('OCR_ES_ID', ps.int(2))
	parse_descriptors(ps)

def parse_DecoderConfigDescriptor_descriptor(ps: Parser):
	ps.field('objectTypeIndication', ps.int(1), describe=format_object_type)
	with ps.bits(4) as br:
		ps.field('streamType', br.read(6), describe=format_stream_type)
		ps.field('upStream', br.bit())
		ps.reserved('reserved', br.read(1), 1)
		ps.field('bufferSizeDB', br.read(24))
	ps.field('maxBitrate', ps.int(4))
	ps.field('avgBitrate', ps.int(4))
	parse_descriptors(ps)

def format_sl_predefined(predefined: int) -> str:
	return {
		0x00: 'Custom',
		0x01: 'null SL packet header',
		0x02: 'Reserved for use in MP4 files',
	}.get(predefined, 'Reserved for ISO use')

def parse_SLConfigDescriptor_descriptor(ps: Parser):
	ps.field('predefined', predefined := ps.int(1), describe=format_sl_predefined)
	if predefined != 0: return

	with ps.bits(1) as br:
		ps.field('useAccessUnitStartFlag', br.bit())
		ps.field('useAccessUnitEndFlag', br.bit())
		ps.field('useRandomAccessPointFlag', br.bit())
		ps.field('hasRandomAccessUnitsOnlyFlag', br.bit())
		ps.field('usePaddingFlag', br.bit())
		ps.field('useTimeStampsFlag', useTimeStampsFlag := br.bit())
		ps.field('useIdleFlag', br.bit())
		ps.field('durationFlag', durationFlag := br.bit())
	ps.field('timeStampResolution', ps.int(4))
	ps.field('OCRResolution', ps.int(4))
	ps.field('timeStampLength', timeStampLength := ps.int(1))
	assert timeStampLength <= 64, f'invalid timeStampLength: {timeStampLength}'
	ps.field('OCRLength', OCRLength := ps.int(1))
	assert OCRLength <= 64, f'invalid OCRLength: {OCRLength}'
	ps.field('AU_Length', AU_Length := ps.int(1))
	assert AU_Length <= 32, f'invalid AU_Length: {AU_Length}'
	ps.field('instantBitrateLength', ps.int(1))
	with ps.bits(2) as br:
		ps.field('degradationPriorityLength', br.read(4))
		ps.field('AU_seqNumLength', AU_seqNumLength := br.read(5))
		assert AU_seqNumLength <= 16, f'invalid AU_seqNumLength: {AU_seqNumLength}'
		ps.field('packetSeqNumLength', packetSeqNumLength := br.read(5))
		assert packetSeqNumLength <= 16, f'invalid packetSeqNumLength: {packetSeqNumLength}'
		ps.reserved('reserved', br.read(2), 0b11)
	if durationFlag:
		ps.field('timeScale', ps.int(4))
		ps.field('accessUnitDuration', ps.int(2))
		ps.field('compositionUnitDuration', ps.int(2))
	if not useTimeStampsFlag:
		assert False, 'FIXME: not implemented yet'
		# bit(timeStampLength) startDecodingTimeStamp;
		# bit(timeStampLength) startCompositionTimeStamp;

def parse_ES_ID_Inc_descriptor(ps: Parser):
	ps.field('Track_ID', ps.int(4))

def parse_ES_ID_Ref_descriptor(ps: Parser):
	ps.field('ref_index', ps.int(2))

def parse_ExtendedSLConfigDescriptor_descriptor(ps: Parser):
	parse_descriptors(ps)

def format_qos_predefined(predefined: int) -> str:
	return {
		0x00: 'Custom',
	}.get(predefined, 'Reserved')

def parse_QoS_Descriptor_descriptor(ps: Parser):
	ps.field('predefined', predefined := ps.int(1), describe=format_qos_predefined)
	if predefined != 0: return
	parse_descriptors(ps, namespace='QoS')

def parse_QoS_Qualifier_descriptor(ps: Parser):
	pass

def parse_BaseCommand_descriptor(ps: Parser):
	pass

def init_descriptors():
	global class_registry
	# do sanity checks on the data defined above. for every namespace, make sure:
	#  - class names are globally unique
	class_registry = unique_dict((k['name'], (nsname, k)) for nsname, ns in descriptor_namespaces.items() for k in ns['classes'])
	for nsname, ns in descriptor_namespaces.items():
		#  - there's exactly one root class
		assert len({ k['name'] for k in ns['classes'] if k['base_class'] == None }) == 1, f'namespace {nsname} must have 1 root'
		#  - tags are unique
		ns['tag_registry'] = unique_dict(( k['tag'], k ) for k in ns['classes'] if 'tag' in k)
		#  - range class names are valid
		assert all(class_registry.get(klname, (None,))[0] == nsname for (_, _, klname) in ns.get('ranges', [])), f'namespace {nsname} has invalid ranges'
		#  - base classes are valid, and there are no cycles
		for k in ns['classes']:
			while k['base_class'] != None:
				assert class_registry.get(k['base_class'], (None,))[0] == nsname, f'class {k["base_class"]} not defined'
				k = class_registry[k['base_class']][1]

	# register handlers defined above
	for k, v in globals().items():
		if m := re.fullmatch(r'parse_(.+)_descriptor', k):
			k = m.group(1)
			assert k in class_registry, f'descriptor {k} not defined'
			class_registry[k][1]['handler'] = v

	# check base classes of defined handlers also have a defined handler
	for (_, k) in class_registry.values():
		if 'handler' in k:
			while k['base_class'] != None:
				k = class_registry[k['base_class']][1]
				assert 'handler' in k

init_descriptors()

# FIXME: implement decoder specific info:
#  - ISO/IEC 14496-2 Annex K
#  - ISO/IEC 14496-3 1.1.6
#  - ISO/IEC 14496-11
#  - ISO/IEC 13818-7 „adif_header()“
#  - ISO/IEC 11172-3 or ISO/IEC 13818-3 -> empty
#  - defined locally:
#    - IPMPDecoderConfiguration
#    - OCIDecoderConfiguration
#    - JPEG_DecoderConfig
#    - UIConfig
#    - BIFSConfigEx
#    - AFXConfig
#    - JPEG2000_DecoderConfig
#    - AVCDecoderSpecificInfo

# FIXME: Implements AFXExtDescriptor, which has its own namespace

def format_object_type(oti: int) -> str:
	assert 0 <= oti < 0x100
	if oti == 0x00:
		raise AssertionError('forbidden object type')
	elif oti == 0xFF:
		return ansi_dim('no object type specified')
	elif e := (object_types.get(oti)):
		description = e.get('short') or e['name']
		if e.get('withdrawn'):
			description += ansi_fg1(' (withdrawn, unused, do not use)')
		return description
	else:
		return ansi_fg4('reserved for ISO use' if oti < 0xC0 else 'user private')

def format_stream_type(sti: int) -> str:
	assert 0 <= sti < 0x40
	if sti == 0x00:
		raise AssertionError('forbidden stream type')
	elif e := (stream_types.get(sti)):
		return e
	else:
		return ansi_fg4('reserved for ISO use' if sti < 0x20 else 'user private')


main()
