#!/usr/bin/env python3
'''
Main parser code
'''

import sys
import struct
import mmap
import io
import itertools
import re
import options
from parser_tables import *
from contextlib import contextmanager
from typing import Optional, Union, Callable, TypeVar
T = TypeVar('T')

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
get_bits = lambda x, end, start: (x & mask(end)) >> start
split_bits = lambda x, *bits: (get_bits(x, a, b) for a, b in itertools.pairwise(bits))

def main():
	parse_boxes(Parser(mp4mem, 0, 0))


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

	# FIXME: to ease migration, remove afterwards
	def unpack(self, struct_fmt: str) -> tuple:
		struct_obj = struct.Struct('>' + struct_fmt) # FIXME: caching
		return struct_obj.unpack(self.read(struct_obj.size))

	@contextmanager
	def bits(self, n = -1):
		with self.capture(n) as res, BitReader(res) as br:
			yield br

	# less common primitives

	def fourcc(self) -> str:
		return self.read(4).tobytes().decode('latin-1')

	def uuid(self) -> str:
		return format_uuid(self.bytes(16))

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

	def print(self, val: str):
		print(self.prefix + val)

	def raw_field(self, name: str, value: str):
		self.print(name + ' = ' + value)

	def field(self, name: str, value: T, format: Union[str, Callable[[T], str]]=repr, default: Optional[T]=None):
		if not show_defaults and value == default:
			return
		self.raw_field(name,
			value.__format__(format) if isinstance(format, str) else format(value))

	def reserved(self, name: str, value: T, expected: Optional[T] = None):
		ok = (value == expected) if expected != None else \
			(not any(value)) if isinstance(value, bytes) else (not value)
		assert ok, f'invalid {name}: {value}'

# FIXME: to ease migration, remove afterwards
def unpack(stream, struct_fmt: str) -> tuple:
		struct_obj = struct.Struct('>' + struct_fmt) # FIXME: caching
		return struct_obj.unpack(stream.read(struct_obj.size))

def unique_dict(x):
	r = {}
	for k, v in x:
		assert k not in r, f'duplicate key {repr(k)}: existing {repr(r[k])}, got {repr(v)}'
		r[k] = v
	return r

# FIXME: give it a proper CLI interface
# FIXME: display errors more nicely (last two frames, type name, you know)

def pad_iter(iterable, size, default=None):
	iterator = iter(iterable)
	for _ in range(size):
		yield next(iterator, default)

def split_in_groups(iterable, size):
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

format_uuid = lambda x: '-'.join(x.hex()[s:e] for s, e in itertools.pairwise([0, 8, 12, 16, 20, 32]) )

def format_fraction(x: tuple[int, int]):
	assert type(x) is tuple and len(x) == 2 and all(type(i) is int for i in x)
	num, denom = x
	return f'{num}/{denom}'

def format_size(x: Union[tuple[int, int], tuple[float, float]]):
	assert type(x) is tuple and len(x) == 2
	width, height = x
	return f'{width} x {height}'


# CORE PARSING

info_by_box = {}
for std_desc, boxes in box_registry:
	for k, v in boxes.items():
		if k in info_by_box:
			raise Exception(f'duplicate boxes {k} coming from {std_desc} and {info_by_box[k][0]}')
		info_by_box[k] = (std_desc, *v)

def slice_box(mem: memoryview):
	assert len(mem) >= 8, f'box too short ({bytes(mem)})'
	length, btype = struct.unpack('>I4s', mem[0:8])
	btype = btype.decode('latin1')
	assert btype.isprintable(), f'invalid type {repr(btype)}'

	last_box = False
	large_size = False
	pos = 8
	if length == 0:
		length = len(mem)
		last_box = True
	elif length == 1:
		large_size = True
		assert len(mem) >= pos + 8, f'EOF while reading largesize'
		length, = struct.unpack('>Q', mem[pos:pos + 8])
		pos += 8

	if btype == 'uuid':
		assert len(mem) >= pos + 16, f'EOF while reading UUID'
		btype = mem[pos:pos + 16]
		pos += 16

	assert length >= pos, f'invalid {btype} length: {length}'
	assert len(mem) >= length, f'expected {length} {btype}, got {len(mem)}'
	return (btype, mem[pos:length], last_box, large_size), length

def parse_boxes(ps: Parser, contents_fn=None):
	result = []
	while mem:
		(btype, data, last_box, large_size), length = slice_box(mem)
		offset_text = ansi_fg4(f' @ {offset:#x}, {offset + length - len(data):#x} - {offset + length:#x}') if show_offsets else ''
		length_text = ansi_fg4(f' ({len(data)})') if show_lengths else ''
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
			type_label = f'UUID {format_uuid(btype)}'
		ps.print(ansi_bold(f'[{type_label}]') + name_text + offset_text + length_text)
		result.append( (contents_fn or parse_contents)(btype, offset + length - len(data), data, indent + 1) )
		mem, offset = mem[length:], offset + length
	return result

nesting_boxes = { 'moov', 'trak', 'mdia', 'minf', 'dinf', 'stbl', 'mvex', 'moof', 'traf', 'mfra', 'meco', 'edts', 'udta', 'sinf', 'schi' }
# apple(?) / quicktime metadata
nesting_boxes |= { 'ilst', '\u00a9too', '\u00a9nam', '\u00a9day', '\u00a9ART', 'aART', '\u00a9alb', '\u00a9cmt', '\u00a9day', 'trkn', 'covr', '----' }

def parse_contents(btype: str, ps: Parser):
	try:

		if (handler := globals().get(f'parse_{btype}_box')):
			return handler(ps)

		if btype in nesting_boxes:
			return parse_boxes(ps)

	except Exception as e:
		print_error(e, ps.prefix)

	# as fall back (or if error), print hex dump
	if not max_dump or not ps.buffer: return
	print_hex_dump(ps.buffer, ps.prefix)

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
	pre_defined, handler_type = ps.unpack('I4s')
	handler_type = handler_type.decode('latin1')
	reserved = ps.bytes(4 * 3)
	# FIXME: a lot of videos seem to break the second assertion (apple metadata?), some break the first
	assert not pre_defined, f'invalid pre-defined: {pre_defined}'
	assert not any(reserved), f'invalid reserved: {reserved}'
	name = ps.bytes().decode('utf-8')
	ps.print(f'handler_type = {repr(handler_type)}, name = {repr(name)}')

	global last_handler_seen
	last_handler_seen = handler_type

def parse_stsd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	entry_count, = ps.unpack('I')
	ps.print(f'version = {version}, entry_count = {entry_count}')
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'

	contents_fn = lambda *a, **b: parse_sample_entry_contents(*a, **b, version=version)
	boxes = parse_boxes(ps, contents_fn=contents_fn)
	assert len(boxes) == entry_count, f'entry_count not matching boxes present'

def parse_sample_entry_contents(btype: str, ps: Parser, version: int):
	reserved = ps.bytes(6)
	assert not any(reserved), f'invalid reserved field: {reserved}'
	ps.field('data_reference_index', ps.int(2))

	try:
		if last_handler_seen == 'vide':
			return parse_video_sample_entry_contents(btype, ps, version)
		if last_handler_seen == 'soun':
			return parse_audio_sample_entry_contents(btype, ps, version)
		if last_handler_seen in {'meta', 'text', 'subt'}:
			return parse_text_sample_entry_contents(btype, ps, version)
	except Exception as e:
		print_error(e, ps.prefix)

	# as fall back (or if error), print hex dump
	if not max_dump or not ps.buffer: return
	print_hex_dump(ps.buffer, ps.prefix)

def parse_video_sample_entry_contents(btype: str, ps: Parser, version: int):
	assert version == 0, 'invalid version'

	reserved = ps.bytes(16)
	assert not any(reserved), f'invalid reserved / pre-defined data: {reserved}'
	width, height, horizresolution, vertresolution, reserved_2, frame_count, compressorname, depth, pre_defined_3 = ps.unpack('HHIIIH 32s Hh')
	ps.field('size', (width, height), format_size)
	if show_defaults or horizresolution != 0x00480000 or vertresolution != 0x00480000:
		ps.field('resolution', (horizresolution, vertresolution), format_size)
	if show_defaults or frame_count != 1:
		ps.field('frame_count', frame_count)

	compressorname_len, compressorname = compressorname[0], compressorname[1:]
	assert compressorname_len <= len(compressorname)
	assert not any(compressorname[compressorname_len:]), 'invalid compressorname padding'
	compressorname = compressorname[:compressorname_len].decode('utf-8')
	ps.field('compressorname', compressorname)

	if show_defaults or depth != 0x0018:
		ps.field('depth', depth)
	assert not reserved_2, f'invalid reserved: {reserved_2}'
	assert pre_defined_3 == -1, f'invalid reserved: {pre_defined_3}'

	parse_boxes(ps)

def parse_audio_sample_entry_contents(btype: str, ps: Parser, version: int):
	assert version <= 1, 'invalid version'

	if version == 0:
		reserved_1, channelcount, samplesize, pre_defined_1, reserved_2, samplerate = ps.unpack('8sHHHHI')
		assert not any(reserved_1), f'invalid reserved_1: {reserved_1}'
		assert not reserved_2, f'invalid reserved_2: {reserved_2}'
		assert not pre_defined_1, f'invalid pre_defined_1: {pre_defined_1}'
		if show_defaults or channelcount != 2:
			ps.field('channelcount', channelcount)
		if show_defaults or samplesize != 16:
			ps.field('samplesize', samplesize)
		ps.field('samplerate', samplerate / (1 << 16))
	else:
		entry_version, reserved_1, channelcount, samplesize, pre_defined_1, reserved_2, samplerate = ps.unpack('H6sHHHHI')
		assert entry_version == 1, f'invalid entry_version: {entry_version}'
		assert not any(reserved_1), f'invalid reserved_1: {reserved_1}'
		assert not reserved_2, f'invalid reserved_2: {reserved_2}'
		assert not pre_defined_1, f'invalid pre_defined_1: {pre_defined_1}'
		ps.field('channelcount', channelcount)
		if show_defaults or samplesize != 16:
			ps.field('samplesize', samplesize)
		if show_defaults or samplerate != (1 << 16):
			ps.field('samplerate', samplerate / (1 << 16))

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
	major_brand, minor_version = ps.unpack('4sI')
	major_brand = major_brand.decode('latin1')
	ps.field('major_brand', major_brand)
	ps.field('minor_version', minor_version, '08x')
	while not ps.ended:
		compatible_brand = ps.fourcc()
		ps.print(f'- compatible: {repr(compatible_brand)}')

parse_styp_box = parse_ftyp_box

def parse_matrix(ps: Parser):
	matrix = [ x / (1 << 16) for x in ps.unpack('9i') ]
	if show_defaults or matrix != [1,0,0, 0,1,0, 0,0,0x4000]:
		ps.field('matrix', matrix)

def parse_language(ps: Parser):
	language, = ps.unpack('H')
	if not language:
		ps.print('language = (null)') # FIXME: log a warning or something
		return
	pad, *language = split_bits(language, 16, 15, 10, 5, 0)
	assert all(0 <= (x - 1) < 26 for x in language), f'invalid language characters: {language}'
	language = ''.join(chr((x - 1) + ord('a')) for x in language)
	ps.field('language', language)
	assert not pad, f'invalid pad: {pad}'

def parse_mfhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	sequence_number, = ps.unpack('I')
	ps.field('sequence_number', sequence_number)

def parse_mvhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	ps.field('version', version)

	creation_time, modification_time, timescale, duration, rate, volume, reserved_1, reserved_2, reserved_3 = \
		ps.unpack(('QQIQ' if version == 1 else 'IIII') + 'ih' + 'HII')
	ps.field('creation_time', creation_time)
	ps.field('modification_time', modification_time)
	ps.field('timescale', timescale)
	ps.field('duration', duration)
	rate /= 1 << 16
	if show_defaults or rate != 1: ps.field('rate', rate)
	volume /= 1 << 8
	if show_defaults or volume != 1: ps.field('volume', volume)
	assert not reserved_1, f'invalid reserved_1: {reserved_1}'
	assert not reserved_2, f'invalid reserved_2: {reserved_2}'
	assert not reserved_3, f'invalid reserved_3: {reserved_3}'

	parse_matrix(ps)

	pre_defined = ps.bytes(6 * 4)
	assert not any(pre_defined), f'invalid pre_defined: {pre_defined}'
	next_track_ID, = ps.unpack('I')
	ps.field('next_track_ID', next_track_ID)

def parse_tkhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	creation_time, modification_time, track_ID, reserved_1, duration, reserved_2, reserved_3, layer, alternate_group, volume, reserved_4 = \
		ps.unpack(('QQIIQ' if version == 1 else 'IIIII') + 'II' + 'hhh' + 'H')
	ps.field('creation_time', creation_time)
	ps.field('modification_time', modification_time)
	ps.field('track_ID', track_ID)
	ps.field('duration', duration)
	if show_defaults or layer != 0:
		ps.field('layer', layer)
	if show_defaults or alternate_group != 0:
		ps.field('alternate_group', alternate_group)
	volume /= 1 << 8
	ps.field('volume', volume)
	assert not reserved_1, f'invalid reserved_1: {reserved_1}'
	assert not reserved_2, f'invalid reserved_1: {reserved_2}'
	assert not reserved_3, f'invalid reserved_1: {reserved_3}'
	assert not reserved_4, f'invalid reserved_1: {reserved_4}'

	parse_matrix(ps)

	width, height = ps.unpack('II')
	width /= 1 << 16
	height /= 1 << 16
	ps.field('size', (width, height), format_size)

def parse_mdhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	ps.field('version', version)

	creation_time, modification_time, timescale, duration = \
		ps.unpack('QQIQ' if version == 1 else 'IIII')
	ps.field('creation_time', creation_time)
	ps.field('modification_time', modification_time)
	ps.field('timescale', timescale)
	ps.field('duration', duration)
	parse_language(ps)
	pre_defined_1, = ps.unpack('H')
	assert not pre_defined_1, f'invalid reserved_1: {pre_defined_1}'

def parse_mehd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	ps.field('version', version)

	fragment_duration, = ps.unpack(('Q' if version == 1 else 'I'))
	ps.field('fragment_duration', fragment_duration)

def parse_smhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	balance, reserved = ps.unpack('hH')
	if show_defaults or balance != 0:
		ps.field('balance', balance)
	assert not reserved, f'invalid reserved: {reserved}'

def parse_vmhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 1, f'invalid flags: {box_flags}'

	graphicsmode, *opcolor = ps.unpack('HHHH')
	if show_defaults or graphicsmode != 0:
		ps.field('graphicsmode', graphicsmode)
	if show_defaults or opcolor != [0, 0, 0]:
		ps.field('opcolor', opcolor)

def parse_trex_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	track_ID, default_sample_description_index, default_sample_duration, default_sample_size, default_sample_flags = \
		ps.unpack('IIIII')
	ps.field('track_ID', track_ID)
	ps.field('default_sample_description_index', default_sample_description_index)
	ps.field('default_sample_duration', default_sample_duration)
	ps.field('default_sample_size', default_sample_size)
	ps.field('default_sample_flags', default_sample_flags, '08x')

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
	entry_count, = ps.unpack('I')
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

def format_colour_type(colour_type: str) -> str:
	description = {
		'nclx': 'on-screen colours',
		'rICC': 'restricted ICC profile',
		'prof': 'unrestricted ICC profile',
	}.get(colour_type)
	description = f' ({description})' if show_descriptions and description != None else ''
	return repr(colour_type) + description

def parse_colr_box(ps: Parser):
	ps.field('colour_type', colour_type := ps.fourcc(), format_colour_type)
	if colour_type == 'nclx':
		colour_primaries, transfer_characteristics, matrix_coefficients, flags = ps.unpack('HHHB')
		ps.field('colour_primaries', colour_primaries)
		ps.field('transfer_characteristics', transfer_characteristics)
		ps.field('matrix_coefficients', matrix_coefficients)
		full_range_flag, reserved = split_bits(flags, 8, 7, 0)
		assert not reserved, f'invalid reserved: {reserved}'
		ps.field('full_range_flag', bool(full_range_flag))
	else:
		name = 'ICC_profile' if colour_type in { 'rICC', 'prof' } else 'data'
		ps.print(f'{name} =')
		print_hex_dump(ps.read(), ps.prefix + '  ')

def parse_btrt_box(ps: Parser):
	bufferSizeDB, maxBitrate, avgBitrate = ps.unpack('III')
	ps.field('bufferSizeDB', bufferSizeDB)
	ps.field('maxBitrate', maxBitrate)
	ps.field('avgBitrate', avgBitrate)

def parse_pasp_box(ps: Parser):
	hSpacing, vSpacing = ps.unpack('II')
	ps.field('pixel aspect ratio', (hSpacing, vSpacing), format_fraction)

def parse_clap_box(ps: Parser):
	cleanApertureWidthN, cleanApertureWidthD, cleanApertureHeightN, cleanApertureHeightD, horizOffN, horizOffD, vertOffN, vertOffD = ps.unpack('II II II II')
	ps.field('cleanApertureWidth', (cleanApertureWidthN, cleanApertureWidthD), format_fraction)
	ps.field('cleanApertureHeight', (cleanApertureHeightN, cleanApertureHeightD), format_fraction)
	ps.field('horizOff', (horizOffN, horizOffD), format_fraction)
	ps.field('vertOff', (vertOffN, vertOffD), format_fraction)

def parse_sgpd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'
	ps.field('version', version)

	grouping_type, = ps.unpack('4s')
	grouping_type = grouping_type.decode('latin1')
	ps.field('grouping_type', grouping_type)

	if version == 1:
		default_length, = ps.unpack('I')
		ps.field('default_length', default_length)
	elif version >= 2:
		default_sample_description_index, = ps.unpack('I')
		ps.field('default_sample_description_index', default_sample_description_index)

	entry_count, = ps.unpack('I')
	for i in range(entry_count):
		ps.print(f'- entry {i+1}:')
		if version == 1:
			if (description_length := default_length) == 0:
				description_length, = ps.unpack('I')
				ps.print(f'  description_length = {description_length}')
			description = ps.read(description_length)
			print_hex_dump(description, ps.prefix + '  ')
		else:
			raise NotImplementedError('TODO: parse box')


# CODEC-SPECIFIC BOXES

def parse_avcC_box(ps: Parser):
	if (configurationVersion := ps.int(1)) != 1:
		raise AssertionError(f'invalid configuration version: {configurationVersion}')
	ps.field('profile / compat / level', ps.bytes(3).hex())
	with ps.bits(1) as br:
		reserved_1 = br.read(6)
		assert reserved_1 == mask(6), f'invalid reserved_1: {reserved_1}'
		ps.field('lengthSizeMinusOne', br.read(2))

	with ps.bits(1) as br:
		reserved_2 = br.read(3)
		assert reserved_2 == mask(3), f'invalid reserved_2: {reserved_2}'
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
	ps.field('profile / compat / level', ps.bytes(3).hex())
	with ps.bits(1) as br:
		ps.field('complete_represenation', br.bit())
		reserved_1 = br.read(5)
		assert reserved_1 == mask(5), f'invalid reserved_1: {reserved_1}'
		ps.field('lengthSizeMinusOne', br.read(2))

	with ps.bits(1) as br:
		reserved_2 = br.read(1)
		assert reserved_2 == 0, f'invalid reserved_2: {reserved_2}'
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
	ps.field('general_profile_compatibility_flags', ps.bytes(4).hex())
	ps.field('general_constraint_indicator_flags', ps.bytes(6).hex())
	ps.field('general_level_idc', ps.bytes(1).hex())

	with ps.bits(2) as br:
		reserved = br.read(4)
		assert reserved == mask(4), f'invalid reserved: {reserved}'
		ps.field('min_spatial_segmentation_idc', br.read())
	with ps.bits(1) as br:
		reserved = br.read(6)
		assert reserved == mask(6), f'invalid reserved: {reserved}'
		ps.field('parallelismType', br.read())
	with ps.bits(1) as br:
		reserved = br.read(6)
		assert reserved == mask(6), f'invalid reserved: {reserved}'
		ps.field('chromaFormat', br.read())
	with ps.bits(1) as br:
		reserved = br.read(5)
		assert reserved == mask(5), f'invalid reserved: {reserved}'
		ps.field('bitDepthLumaMinus8', br.read())
	with ps.bits(1) as br:
		reserved = br.read(5)
		assert reserved == mask(5), f'invalid reserved: {reserved}'
		ps.field('bitDepthChromaMinus8', br.read())

	avgFrameRate = ps.int(2)
	with ps.bits(1) as br:
		ps.field('avgFrameRate', avgFrameRate)
		ps.field('constantFrameRate', br.read(2))
		ps.field('numTemporalLayers', br.read(3))
		ps.field('temporalIdNested', br.bit())
		ps.field('lengthSizeMinusOne', br.read(2))

	numOfArrays = ps.int(1)
	#ps.field('numOfArrays', numOfArrays)
	for i in range(numOfArrays):
		ps.print(f'- array {i}:')
		composite, numNalus = ps.unpack('BH')
		array_completeness, reserved, NAL_unit_type = split_bits(composite, 8, 7, 6, 0)
		assert reserved == 0, f'invalid reserved: {reserved}'

		ps.print(f'    array_completeness = {bool(array_completeness)}')
		ps.print(f'    NAL_unit_type = {NAL_unit_type}')
		#ps.print(f'    numNalus = {numNalus}')

		for n in range(numNalus):
			ps.print(f'    - NALU {n}')
			print_hex_dump(ps.read(ps.int(2)), ps.prefix + '        ')

# FIXME: implement av1C

def parse_esds_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags:06x}'
	parse_descriptor(io.BytesIO(ps.read()), ps.indent, expected=3)

parse_iods_box = parse_esds_box

def parse_m4ds_box(ps: Parser):
	parse_descriptors(io.BytesIO(ps.read()), ps.indent)

def parse_dOps_box(ps: Parser):
	if (Version := ps.unpack('B')[0]) != 0:
		raise AssertionError(f'invalid Version: {Version}')

	ps.field('OutputChannelCount', OutputChannelCount := ps.unpack('B')[0])
	ps.field('PreSkip', ps.unpack('H')[0])
	ps.field('InputSampleRate', ps.unpack('I')[0])
	ps.field('OutputGain', ps.unpack('h')[0] / (1 << 8))
	ps.field('ChannelMappingFamily', ChannelMappingFamily := ps.unpack('B')[0])
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

	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		segment_duration, media_time, media_rate = \
			ps.unpack(('Qq' if version == 1 else 'Ii') + 'i')
		media_rate /= 1 << 16
		if i < max_rows:
			ps.print(f'[edit segment {i:3}] duration = {segment_duration:6}, media_time = {media_time:6}, media_rate = {media_rate}')
	if entry_count > max_rows:
		ps.print('...')

def parse_sidx_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version <= 1, f'invalid version: {version}'
	ps.field('version', version)

	reference_ID, timescale, earliest_presentation_time, first_offset, reserved_1, reference_count = \
		ps.unpack('II' + ('II' if version == 0 else 'QQ') + 'HH')
	ps.field('reference_ID', reference_ID)
	ps.field('timescale', timescale)
	ps.field('earliest_presentation_time', earliest_presentation_time)
	ps.field('first_offset', first_offset)
	ps.field('reference_count', reference_count)
	assert not reserved_1, f'invalid reserved_1 = {reserved_1}'
	for i in range(reference_count):
		composite_1, subsegment_duration, composite_2 = ps.unpack('III')
		reference_type, referenced_size = split_bits(composite_1, 32, 31, 0)
		starts_with_SAP, SAP_type, SAP_delta_time = split_bits(composite_2, 32, 31, 28, 0)
		if i < max_rows:
			ps.print(f'[reference {i:3}] type = {reference_type}, size = {referenced_size}, duration = {subsegment_duration}, starts_with_SAP = {starts_with_SAP}, SAP_type = {SAP_type}, SAP_delta_time = {SAP_delta_time}')
	if reference_count > max_rows:
		ps.print('...')

def parse_stts_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	sample, time = 1, 0
	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_count, sample_delta = ps.unpack('II')
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
	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_count, sample_offset = ps.unpack('I' + ('i' if version==1 else 'I'))
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
	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		first_chunk, samples_per_chunk, sample_description_index = ps.unpack('III')
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

	sample_size, sample_count = ps.unpack('II')
	if show_defaults or sample_size != 0:
		ps.field('sample_size', sample_size)
	ps.field('sample_count', sample_count)
	if sample_size == 0:
		for i in range(sample_count):
			sample_size, = ps.unpack('I')
			if i < max_rows:
				ps.print(f'[sample {i+1:6}] sample_size = {sample_size:5}')
		if sample_count > max_rows:
			ps.print('...')

def parse_stco_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		chunk_offset, = ps.unpack('I')
		if i < max_rows:
			ps.print(f'[chunk {i+1:5}] offset = {chunk_offset:#08x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_co64_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		chunk_offset, = ps.unpack('Q')
		if i < max_rows:
			ps.print(f'[chunk {i+1:5}] offset = {chunk_offset:#016x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_stss_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version == 0, f'invalid version: {version}'

	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_number, = ps.unpack('I')
		if i < max_rows:
			ps.print(f'[sync sample {i:5}] sample_number = {sample_number:6}')
	if entry_count > max_rows:
		ps.print('...')

def parse_sbgp_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	assert version <= 1, f'invalid version: {version}'
	ps.field('version', version)

	grouping_type, = ps.unpack('4s')
	grouping_type = grouping_type.decode('latin1')
	ps.field('grouping_type', grouping_type)
	if version == 1:
		grouping_type_parameter, = ps.unpack('I')
		ps.field('grouping_type_parameter', grouping_type_parameter)

	sample = 1
	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_count, group_description_index = ps.unpack('II')
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
		aux_info_type, aux_info_type_parameter = ps.unpack('4sI')
		aux_info_type = aux_info_type.decode('latin1')
		ps.field('aux_info_type', aux_info_type)
		ps.field('aux_info_type_parameter', aux_info_type_parameter, '#x')

	default_sample_info_size, sample_count = ps.unpack('BI')
	ps.field('default_sample_info_size', default_sample_info_size)
	ps.field('sample_count', sample_count)
	if default_sample_info_size == 0:
		for i in range(sample_count):
			sample_info_size, = ps.unpack('B')
			if i < max_rows:
				ps.print(f'[sample {i+1:6}] sample_info_size = {sample_info_size:5}')
		if sample_count > max_rows:
			ps.print('...')

def parse_saio_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	if box_flags & 1:
		aux_info_type, aux_info_type_parameter = ps.unpack('4sI')
		aux_info_type = aux_info_type.decode('latin1')
		ps.field('aux_info_type', aux_info_type)
		ps.field('aux_info_type_parameter', aux_info_type_parameter, '#x')

	entry_count, = ps.unpack('I')
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		offset, = ps.unpack('I' if version == 0 else 'Q')
		if i < max_rows:
			ps.print(f'[entry {i+1:6}] offset = {offset:#08x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_tfdt_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version <= 1, f'invalid version: {version}'

	baseMediaDecodeTime, = ps.unpack('I' if version == 0 else 'Q')
	ps.print(f'version = {version}, flags = {box_flags:06x}')
	ps.field('baseMediaDecodeTime', baseMediaDecodeTime)

def parse_tfhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	assert version == 0, f'invalid version: {version}'

	ps.print(f'version = {version}, flags = {box_flags:06x}')
	track_ID, = ps.unpack('I')
	ps.field('track_ID', track_ID)
	if box_flags & 0x10000:  # duration‐is‐empty
		ps.print('duration-is-empty flag set')
	if box_flags & 0x20000:  # default-base-is-moof
		ps.print('default-base-is-moof flag set')

	if box_flags & 0x1:  # base‐data‐offset‐present
		base_data_offset, = ps.unpack('Q')
		ps.field('base_data_offset', base_data_offset)
	if box_flags & 0x2:  # sample-description-index-present
		sample_description_index, = ps.unpack('I')
		ps.field('sample_description_index', sample_description_index)
	if box_flags & 0x8:  # default‐sample‐duration‐present
		default_sample_duration, = ps.unpack('I')
		ps.field('default_sample_duration', default_sample_duration)
	if box_flags & 0x10:  # default‐sample‐size‐present
		default_sample_size, = ps.unpack('I')
		ps.field('default_sample_size', default_sample_size)


def parse_trun_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)

	sample_count, = ps.unpack('I')
	ps.print(f'version = {version}, flags = {box_flags:06x}, sample_count = {sample_count}')
	if box_flags & (1 << 0):
		data_offset, = ps.unpack('i')
		ps.field('data_offset', data_offset, '#x')
	if box_flags & (1 << 2):
		first_sample_flags, = ps.unpack('I')
		ps.field('first_sample_flags', first_sample_flags, '08x')

	s_offset = 0
	s_time = 0
	for s_idx in range(sample_count):
		s_text = []
		if box_flags & (1 << 8):
			sample_duration, = ps.unpack('I')
			s_text.append(f'time={s_time:7} + {sample_duration:5}')
			s_time += sample_duration
		if box_flags & (1 << 9):
			sample_size, = ps.unpack('I')
			s_text.append(f'offset={s_offset:#9x} + {sample_size:5}')
			s_offset += sample_size
		if box_flags & (1 << 10):
			sample_flags, = ps.unpack('I')
			s_text.append(f'flags={sample_flags:08x}')
		if box_flags & (1 << 11):
			sample_composition_time_offset, = ps.unpack('I' if version == 0 else 'i')
			s_text.append(f'{sample_composition_time_offset}')
		if s_idx < max_rows:
			ps.print(f'[sample {s_idx:4}] {", ".join(s_text)}')
	if sample_count > max_rows:
		ps.print('...')

# FIXME: describe handlers, boxes (from RA, also look at the 'handlers' and 'unlisted' pages), brands


# DRM boxes

def parse_frma_box(ps: Parser):
	data_format, = ps.unpack('4s')
	data_format = data_format.decode('latin1')
	ps.field('data_format', data_format)

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

	reserved_1 = ps.int(1)
	assert reserved_1 == 0, f'invalid reserved 1: {reserved_1}'

	if version > 0:
		with ps.bits(1) as br:
			ps.field('default_crypt_byte_block', br.read(4))
			ps.field('default_skip_byte_block', br.read(4))
	else:
		reserved_2 = ps.int(1)
		assert reserved_2 == 0, f'invalid reserved 2: {reserved_2}'

	ps.field('default_isProtected', default_isProtected := ps.int(1))
	ps.field('default_Per_Sample_IV_Size', default_Per_Sample_IV_Size := ps.int(1))
	ps.field('default_KID', ps.bytes(16).hex())
	if default_isProtected == 1 and default_Per_Sample_IV_Size == 0:
		ps.field('default_constant_IV', ps.bytes(ps.int(1)).hex())

def format_system_id(SystemID: str) -> str:
	system_name, system_comment = protection_systems.get(SystemID, (None, None))
	return SystemID + (f' ({system_name})' if system_name else '')

def parse_pssh_box(ps: Parser):
	version, box_flags = parse_fullbox(ps)
	ps.print(f'version = {version}, flags = {box_flags:06x}')

	ps.field('SystemID', ps.uuid(), format_system_id)

	if version > 0:
		KID_count, = ps.unpack('I')
		for i in range(KID_count):
			KID, = ps.unpack('16s')
			ps.print(f'- KID: {KID.hex()}')

	ps.print(f'Data =')
	print_hex_dump(ps.read(ps.int(4)), ps.prefix + '  ')


# MPEG-4 part 1 DESCRIPTORS (based on 2010 edition)
# (these aren't specific to ISOBMFF and so we shouldn't parse them buuuut
# they're still part of MPEG-4 and not widely known so we'll make an exception)

def parse_descriptor(data, indent: int, expected=None, namespace='default', contents_fn=None, optional=False):
	tag = data.read(1)
	if optional and not tag: return None
	tag, = tag
	assert tag != 0x00 and tag != 0xFF, f'forbidden tag number: {tag}'

	size = 0
	n_size_bytes = 0
	while True:
		b = data.read(1)
		assert b, f'unexpected EOF when reading descriptor size'
		next_byte, size_byte = split_bits(b[0], 8, 7, 0)
		size = (size << 7) | size_byte
		n_size_bytes += 1
		if not next_byte: break

	payload = data.read(size)
	assert len(payload) == size, f'unexpected EOF within descriptor data: expected {size}, got {len(payload)}'
	data = io.BytesIO(payload)

	prefix = ' ' * (indent * indent_n)
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

	print(prefix + ansi_bold(f'[{tag}]') + (' ' + ' -> '.join(labels) if show_descriptions else '') + size_text)
	(contents_fn or parse_descriptor_contents)(tag, klasses, data, indent + 1)

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing descriptor data'
	return tag,

def parse_descriptors(data, indent: int, **kwargs):
	while parse_descriptor(data, indent, **kwargs, optional=True) != None:
		pass

def parse_descriptor_contents(tag: int, klasses, data, indent: int):
	prefix = ' ' * (indent * indent_n)
	try:
		for k in klasses[::-1]:
			if 'handler' not in k: break
			k['handler'](data, indent)
	except Exception as e:
		print_error(e, prefix)

	# FIXME: should we backtrack here a bit? or too much? when a non-indented hexdump is printed, make it clear what it represents
	# as fall back (or if error), print hex dump
	data = data.read()
	if not max_dump or not data: return
	print_hex_dump(data, prefix)

def parse_BaseDescriptor_descriptor(data, indent: int):
	pass

def parse_ObjectDescriptorBase_descriptor(data, indent: int):
	pass

def parse_ExtensionDescriptor_descriptor(data, indent: int):
	pass

def parse_OCI_Descriptor_descriptor(data, indent: int):
	pass

def parse_IP_IdentificationDataSet_descriptor(data, indent: int):
	pass

def parse_ES_Descriptor_descriptor(data, indent: int):
	prefix = ' ' * (indent * indent_n)
	ES_ID, composite_1 = unpack(data, 'HB')
	streamDependenceFlag, URL_Flag, OCRstreamFlag, streamPriority = split_bits(composite_1, 8, 7, 6, 5, 0)
	print(prefix + f'ES_ID = {ES_ID}')
	print(prefix + f'streamPriority = {streamPriority}')
	if streamDependenceFlag:
		dependsOn_ES_ID, = unpack(data, 'H')
		print(prefix + f'dependsOn_ES_ID = {dependsOn_ES_ID}')
	if URL_Flag:
		URLlength, = unpack(data, 'B')
		URLstring = data.read(URLlength)
		assert len(URLstring) == URLlength, f'unexpected EOF while reading URL, expected {URLlength}, found {len(URLstring)}'
		URLstring = URLstring.decode('utf-8')
		print(prefix + f'URL = {repr(URLstring)}')
	if OCRstreamFlag:
		OCR_ES_ID, = unpack(data, 'H')
		print(prefix + f'OCR_ES_ID = {OCR_ES_ID}')
	parse_descriptors(data, indent)

def parse_DecoderConfigDescriptor_descriptor(data, indent: int):
	prefix = ' ' * (indent * indent_n)
	objectTypeIndication, composite, maxBitrate, avgBitrate = unpack(data, 'BIII')
	streamType, upStream, reserved, bufferSizeDB = split_bits(composite, 32, 26, 25, 24, 0)
	print(prefix + f'objectTypeIndication = {objectTypeIndication}' + (f' ({format_object_type(objectTypeIndication)})' if show_descriptions else ''))
	print(prefix + f'streamType = {streamType}' + (f' ({format_stream_type(streamType)})' if show_descriptions else ''))
	print(prefix + f'upStream = {bool(upStream)}')
	print(prefix + f'bufferSizeDB = {bufferSizeDB}')
	print(prefix + f'maxBitrate = {maxBitrate}')
	print(prefix + f'avgBitrate = {avgBitrate}')
	assert reserved == 1, f'invalid reserved: {reserved}'
	parse_descriptors(data, indent)

def parse_SLConfigDescriptor_descriptor(data, indent: int):
	prefix = ' ' * (indent * indent_n)
	predefined, = unpack(data, 'B')
	predefined_description = {
		0x00: 'Custom',
		0x01: 'null SL packet header',
		0x02: 'Reserved for use in MP4 files',
	}.get(predefined, 'Reserved for ISO use')
	print(prefix + f'predefined = {predefined}' + (f' ({predefined_description})' if show_descriptions else ''))
	if predefined != 0: return

	flags, timeStampResolution, OCRResolution, timeStampLength, OCRLength, AU_Length, instantBitrateLength, composite = \
		unpack(data, 'BIIBBBBH')
	useAccessUnitStartFlag, useAccessUnitEndFlag, useRandomAccessPointFlag, hasRandomAccessUnitsOnlyFlag, usePaddingFlag, useTimeStampsFlag, useIdleFlag, durationFlag = \
		split_bits(flags, 8, 7, 6, 5, 4, 3, 2, 1, 0)
	print(prefix + f'useAccessUnitStartFlag = {bool(useAccessUnitStartFlag)}')
	print(prefix + f'useAccessUnitEndFlag = {bool(useAccessUnitEndFlag)}')
	print(prefix + f'useRandomAccessPointFlag = {bool(useRandomAccessPointFlag)}')
	print(prefix + f'hasRandomAccessUnitsOnlyFlag = {bool(hasRandomAccessUnitsOnlyFlag)}')
	print(prefix + f'usePaddingFlag = {bool(usePaddingFlag)}')
	print(prefix + f'useTimeStampsFlag = {bool(useTimeStampsFlag)}')
	print(prefix + f'useIdleFlag = {bool(useIdleFlag)}')
	print(prefix + f'durationFlag = {bool(durationFlag)}')
	print(prefix + f'timeStampResolution = {timeStampResolution}')
	print(prefix + f'OCRResolution = {OCRResolution}')
	print(prefix + f'timeStampLength = {timeStampLength}')
	assert timeStampLength <= 64, f'invalid timeStampLength: {timeStampLength}'
	print(prefix + f'OCRLength = {OCRLength}')
	assert OCRLength <= 64, f'invalid OCRLength: {OCRLength}'
	print(prefix + f'AU_Length = {AU_Length}')
	assert AU_Length <= 32, f'invalid AU_Length: {AU_Length}'
	print(prefix + f'instantBitrateLength = {instantBitrateLength}')
	degradationPriorityLength, AU_seqNumLength, packetSeqNumLength, reserved = split_bits(composite, 16, 12, 7, 2, 0)
	print(prefix + f'degradationPriorityLength = {degradationPriorityLength}')
	print(prefix + f'AU_seqNumLength = {AU_seqNumLength}')
	assert AU_seqNumLength <= 16, f'invalid AU_seqNumLength: {AU_seqNumLength}'
	print(prefix + f'packetSeqNumLength = {packetSeqNumLength}')
	assert packetSeqNumLength <= 16, f'invalid packetSeqNumLength: {packetSeqNumLength}'
	assert reserved == 0b11, f'invalid reserved: {reserved}'
	if durationFlag:
		timeScale, accessUnitDuration, compositionUnitDuration = unpack(data, 'IHH')
		print(prefix + f'timeScale = {timeScale}')
		print(prefix + f'accessUnitDuration = {accessUnitDuration}')
		print(prefix + f'compositionUnitDuration = {compositionUnitDuration}')
	if not useTimeStampsFlag:
		assert False, 'FIXME: not implemented yet'
		# bit(timeStampLength) startDecodingTimeStamp;
		# bit(timeStampLength) startCompositionTimeStamp;

def parse_ES_ID_Inc_descriptor(data, indent: int):
	prefix = ' ' * (indent * indent_n)
	Track_ID, = unpack(data, 'I')
	print(prefix + f'Track_ID = {Track_ID}')

def parse_ES_ID_Ref_descriptor(data, indent: int):
	prefix = ' ' * (indent * indent_n)
	ref_index, = unpack(data, 'H')
	print(prefix + f'ref_index = {ref_index}')

def parse_ExtendedSLConfigDescriptor_descriptor(data, indent: int):
	parse_descriptors(data, indent)

def parse_QoS_Descriptor_descriptor(data, indent: int):
	prefix = ' ' * (indent * indent_n)
	predefined, = unpack(data, 'B')
	predefined_description = {
		0x00: 'Custom',
	}.get(predefined, 'Reserved')
	print(prefix + f'predefined = {predefined}' + (f' ({predefined_description})' if show_descriptions else ''))
	if predefined != 0: return
	parse_descriptors(data, indent, namespace='QoS')

def parse_QoS_Qualifier_descriptor(data, indent: int):
	pass

def parse_BaseCommand_descriptor(data, indent: int):
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
