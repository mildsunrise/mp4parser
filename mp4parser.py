# Portable* ISO Base Format dissector / parser.
# Usage: ./mp4parser.py <file name>
#
# (*) Needs Python 3.8+
#
# Goals / development guidelines:
#
#  - Low level. Meant as a dissector, i.e. to obtain info about the structure of the file
#    rather than high level info.
# 
#  - Print offsets to every box to let users inspect deeper. If parsing fails, print an
#    error for that particular box followed by a hexdump.
#
#  - Don't parse non-MP4 structures. It is fine to parse the info in the MP4 boxes,
#    as long as this info is specific to MP4. Examples of things we don't parse:
#     - Codec-specific structures (SPS, PPS)
#     - ID3v2 tags
#     - H.264 NALUs
#     - XML
#    These blobs are just left as hexdump, with their offsets / length printed in case the
#    user wants to dive deeper.
#    The only exception is when this info is needed to dissect other MP4 boxes correctly.
#
#  - Focus on dissection, not parsing. First priority is to show the box structure correctly
#    and to 'dig as deeper as possible' if there are nested boxes; decoding non-box info
#    (instead of showing hexdumps) is second priority.
#
#  - Print *every field on the wire*, with only minimal / mostly obvious postprocessing.
#    Exception: lengths, in many cases. Exception: values which have a default (`template`)
#    set by spec, which may be omitted from output if the value is set to the default, and
#    `show_defaults` was not set. Exception: big boxes, or long rows of output, may
#    be summarized through the `max_dump` (for hexdumps) and `max_rows` (for tables) options.
#
#  - Option to hide lengths / offset (for i.e. diffs).
#
#  - In the future we should have options to make the output interoperable (make it machine
#    friendly like JSON), don't use global variables for config/state, allow output to a
#    different file (for programmatic use).
#
#  - Parsed fields should be named exactly like in the spec's syntax.
#    Both in code, and in the output.
#
#  - Performance isn't a concern. Correctness is more important, but it's also nice for
#    the code to be 'hacker-friendly' for people who may want to tweak it.

import sys
import struct
import mmap
import io
import itertools

fname, = sys.argv[1:]
mp4file = open(fname, 'rb')
mp4map = mmap.mmap(mp4file.fileno(), 0, prot=mmap.PROT_READ)
mp4mem = memoryview(mp4map)

indent_n = 4
bytes_per_line = 16
max_rows = 7
max_dump = bytes_per_line * max_rows
show_lengths = True
show_offsets = True
show_defaults = False
colorize = True

mask = lambda n: ~((~0) << n)
get_bits = lambda x, end, start: (x & mask(end)) >> start
split_bits = lambda x, *bits: (get_bits(x, a, b) for a, b in itertools.pairwise(bits))

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


# CORE PARSING

def slice_box(mem: memoryview):
	assert len(mem) >= 8, f'box too short ({bytes(mem)})'
	length, btype = struct.unpack('>I4s', mem[0:8])
	btype = btype.decode('ascii')
	assert btype.isprintable(), f'invalid type {repr(btype)}'
	assert length >= 8, f'invalid {btype} length: {length}'
	# FIXME: implement length == 1 and length == 0
	assert len(mem) >= length, f'expected {length} {btype}, got {len(mem)}'
	return (btype, mem[8:length]), length

def parse_boxes(offset: int, mem: memoryview, indent=0, contents_fn=None):
	prefix = ' ' * (indent * indent_n)
	result = []
	while mem:
		(btype, data), length = slice_box(mem)
		offset_text = ansi_fg4(f' {offset:#x} - {offset + length:#x}') if show_offsets else ''
		length_text = ansi_fg4(f' ({len(data)})') if show_lengths else ''
		print(prefix + ansi_bold(f'[{btype}]') + offset_text + length_text)
		result.append( (contents_fn or parse_contents)(btype, offset + 8, data, indent + 1) ) # FIXME: offset + 8
		mem, offset = mem[length:], offset + length
	return result

nesting_boxes = { 'moov', 'trak', 'mdia', 'minf', 'dinf', 'stbl', 'mvex', 'moof', 'traf', 'mfra', 'meco', 'edts' }

def parse_contents(btype: str, offset: int, data: memoryview, indent):
	prefix = ' ' * (indent * indent_n)
	try:

		if (handler := globals().get(f'parse_{btype}_box')):
			return handler(offset, data, indent)

		if btype in nesting_boxes:
			return parse_boxes(offset, data, indent)

	except Exception as e:
		print(prefix + f'{ansi_bold(ansi_fg1("ERROR:"))} {ansi_fg1(e)}\n')

	# as fall back (or if error), print hex dump
	if not max_dump or not data: return
	print_hex_dump(data, prefix)

def parse_full_box(data: io.BytesIO, prefix: str):
	fv = data.read(4)
	assert len(fv) == 4
	return fv[0], int.from_bytes(fv[1:], 'big')


# BOX CONTAINERS THAT ALSO HAVE A PREPENDED BINARY STRUCTURE

def parse_meta_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	print(prefix + f'version = {version}, flags = {box_flags:08x}')
	parse_boxes(offset + data.tell(), memoryview(data.read()), indent)

# hack: use a global variable because I'm too lazy to rewrite everything to pass this around
last_handler_seen = None

def parse_hdlr_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version == 0 and box_flags == 0, 'invalid version / flags'
	pre_defined, handler_type = struct.unpack('>I4s', data.read(8))
	handler_type = handler_type.decode('ascii')
	reserved = data.read(4 * 3)
	assert not pre_defined, f'invalid pre-defined: {pre_defined}'
	assert not any(reserved), f'invalid reserved: {reserved}'
	name = data.read().decode('utf-8')
	print(prefix + f'HandlerBox: handler_type = {repr(handler_type)}, name = {repr(name)}')

	global last_handler_seen
	last_handler_seen = handler_type

def parse_stsd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	entry_count, = struct.unpack('>I', data.read(4))
	print(prefix + f'SampleDescriptionBox: version = {version}, entry_count = {entry_count}')
	assert box_flags == 0, f'invalid flags: {box_flags:08x}'

	contents_fn = lambda *a, **b: parse_sample_entry_contents(*a, **b, version=version)
	boxes = parse_boxes(offset + data.tell(), memoryview(data.read()), indent, contents_fn=contents_fn)
	assert len(boxes) == entry_count, f'entry_count not matching boxes present'

def parse_sample_entry_contents(btype: str, offset: int, data: memoryview, indent: int, version: int):
	prefix = ' ' * (indent * indent_n)

	assert len(data) >= 6 + 2, 'entry too short'
	assert data[:6] == b'\x00\x00\x00\x00\x00\x00', f'invalid reserved field: {data[:6]}'
	data_reference_index, = struct.unpack('>H', data[6:8])
	data = data[8:]
	print(prefix + f'data_reference_index = {data_reference_index}')

	try:
		if last_handler_seen == 'vide':
			return parse_video_sample_entry_contents(btype, offset, data, indent, version)
		if last_handler_seen == 'soun':
			return parse_audio_sample_entry_contents(btype, offset, data, indent, version)
		if last_handler_seen in {'meta', 'text', 'subt'}:
			return parse_text_sample_entry_contents(btype, offset, data, indent, version)
	except Exception as e:
		print(prefix + f'{ansi_bold(ansi_fg1("ERROR:"))} {ansi_fg1(e)}\n')

	# as fall back (or if error), print hex dump
	if not max_dump or not data: return
	print_hex_dump(data, prefix)

def parse_video_sample_entry_contents(btype: str, offset: int, data: memoryview, indent: int, version: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	assert version == 0, 'invalid version'

	reserved = data.read(16)
	assert not any(reserved), f'invalid reserved / pre-defined data: {reserved}'
	st = struct.Struct('>HHIIIH 32s Hh')
	width, height, horizresolution, vertresolution, reserved_2, frame_count, compressorname, depth, pre_defined_3 = st.unpack(data.read(st.size))
	print(prefix + f'size = {width} x {height}')
	if show_defaults or horizresolution != 0x00480000 or vertresolution != 0x00480000:
		print(prefix + f'resolution = {horizresolution} x {vertresolution}')
	if show_defaults or frame_count != 1:
		print(prefix + f'frame count = {frame_count}')
	while compressorname.endswith(b'\0'): compressorname = compressorname[:-1]
	print(prefix + f'compressor = {repr(compressorname)}')
	if show_defaults or depth != 0x0018:
		print(prefix + f'depth = {depth}')
	assert not reserved_2, f'invalid reserved: {reserved_2}'
	assert pre_defined_3 == -1, f'invalid reserved: {pre_defined_3}'

	# FIXME
	parse_boxes(offset + data.tell(), memoryview(data.read()), indent)

def parse_audio_sample_entry_contents(btype: str, offset: int, data: memoryview, indent: int, version: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	assert version <= 1, 'invalid version'

	if version == 0:
		reserved_1, channelcount, samplesize, pre_defined_1, reserved_2, samplerate = struct.unpack('>8sHHHHI', data.read(20))
		assert not any(reserved_1), f'invalid reserved_1: {reserved_1}'
		assert not reserved_2, f'invalid reserved_2: {reserved_2}'
		assert not pre_defined_1, f'invalid pre_defined_1: {pre_defined_1}'
		if show_defaults or channelcount != 2:
			print(prefix + f'channelcount = {channelcount}')
		if show_defaults or samplesize != 16:
			print(prefix + f'samplesize = {samplesize}')
		print(prefix + f'samplerate = {samplerate / (1 << 16)}')
	else:
		entry_version, reserved_1, channelcount, samplesize, pre_defined_1, reserved_2, samplerate = struct.unpack('>H6sHHHHI', data.read(20))
		assert entry_version == 1, f'invalid entry_version: {entry_version}'
		assert not any(reserved_1), f'invalid reserved_1: {reserved_1}'
		assert not reserved_2, f'invalid reserved_2: {reserved_2}'
		assert not pre_defined_1, f'invalid pre_defined_1: {pre_defined_1}'
		print(prefix + f'channelcount = {channelcount}')
		if show_defaults or samplesize != 16:
			print(prefix + f'samplesize = {samplesize}')
		if show_defaults or samplerate != (1 << 16):
			print(prefix + f'samplerate = {samplerate / (1 << 16)}')

	parse_boxes(offset + data.tell(), memoryview(data.read()), indent)

def parse_text_sample_entry_contents(btype: str, offset: int, data: memoryview, indent: int, version: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
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
		value = bytearray()
		while True:
			ch = data.read(1)
			assert ch, f'unexpected end of box without terminating string'
			if not ch[0]: break
			value.append(ch[0])
		print(prefix + f'{field_name} = {bytes(value)}')

	parse_boxes(offset + data.tell(), memoryview(data.read()), indent)


# NON-CONTAINER BOXES

def parse_ftyp_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	major_brand, minor_version = struct.unpack('>4sI', data.read(8))
	major_brand = major_brand.decode('ascii')
	print(prefix + f'major_brand = {repr(major_brand)}')
	print(prefix + f'minor_version = {minor_version}')
	while (compatible_brand := data.read(4)):
		assert len(compatible_brand), 'invalid brand length'
		print(prefix + f'- compatible: {repr(compatible_brand.decode("ascii"))}')

parse_styp_box = parse_ftyp_box

def parse_matrix(data: io.BytesIO, prefix: str):
	matrix = [ x / (1 << 16) for x in struct.unpack('>9i', data.read(9 * 4)) ]
	if show_defaults or matrix != [1,0,0, 0,1,0, 0,0,0x4000]:
		print(prefix + f'matrix = {matrix}')

def parse_mfhd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	sequence_number, = struct.unpack('>I', data.read(4))
	print(prefix + f'sequence_number = {sequence_number}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_mvhd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	print(prefix + f'version = {version}')

	st = struct.Struct('>' + ('QQIQ' if version == 1 else 'IIII') + 'ih' + 'HII')
	creation_time, modification_time, timescale, duration, rate, volume, reserved_1, reserved_2, reserved_3 = st.unpack(data.read(st.size))
	print(prefix + f'creation_time = {creation_time}')
	print(prefix + f'modification_time = {modification_time}')
	print(prefix + f'timescale = {timescale}')
	print(prefix + f'duration = {duration}')
	rate /= 1 << 16
	if show_defaults or rate != 1: print(prefix + f'rate = {rate}')
	volume /= 1 << 8
	if show_defaults or volume != 1: print(prefix + f'volume = {volume}')
	assert not reserved_1, f'invalid reserved_1: {reserved_1}'
	assert not reserved_2, f'invalid reserved_1: {reserved_2}'
	assert not reserved_3, f'invalid reserved_1: {reserved_3}'

	parse_matrix(data, prefix)

	pre_defined = data.read(6 * 4)
	assert not any(pre_defined), f'invalid pre_defined: {pre_defined}'
	next_track_ID, = struct.unpack('>I', data.read(4))
	print(prefix + f'next_track_ID = {next_track_ID}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_tkhd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version <= 1, f'invalid version: {version}'
	print(prefix + f'version = {version}, flags = {box_flags:08x}')

	st = struct.Struct('>' + ('QQIIQ' if version == 1 else 'IIIII') + 'II' + 'hhh' + 'H')
	creation_time, modification_time, track_ID, reserved_1, duration, reserved_2, reserved_3, layer, alternate_group, volume, reserved_4 = st.unpack(data.read(st.size))
	print(prefix + f'creation_time = {creation_time}')
	print(prefix + f'modification_time = {modification_time}')
	print(prefix + f'track_ID = {track_ID}')
	print(prefix + f'duration = {duration}')
	if show_defaults or layer != 0:
		print(prefix + f'layer = {layer}')
	if show_defaults or alternate_group != 0:
		print(prefix + f'alternate_group = {alternate_group}')
	volume /= 1 << 8
	print(prefix + f'volume = {volume}')
	assert not reserved_1, f'invalid reserved_1: {reserved_1}'
	assert not reserved_2, f'invalid reserved_1: {reserved_2}'
	assert not reserved_3, f'invalid reserved_1: {reserved_3}'
	assert not reserved_4, f'invalid reserved_1: {reserved_4}'

	parse_matrix(data, prefix)

	width, height = struct.unpack('>II', data.read(8))
	print(prefix + f'size = {width} x {height}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_mdhd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	print(prefix + f'version = {version}')

	st = struct.Struct('>' + ('QQIQ' if version == 1 else 'IIII') + 'HH')
	creation_time, modification_time, timescale, duration, language, pre_defined_1 = st.unpack(data.read(st.size))
	print(prefix + f'creation_time = {creation_time}')
	print(prefix + f'modification_time = {modification_time}')
	print(prefix + f'timescale = {timescale}')
	print(prefix + f'duration = {duration}')
	pad, *language = split_bits(language, 16, 15, 10, 5, 0)
	assert all(0 <= (x - 1) < 26 for x in language)
	language = ''.join(chr((x - 1) + ord('a')) for x in language)
	print(prefix + f'language = {language}')
	assert not pad, f'invalid pad: {pad}'
	assert not pre_defined_1, f'invalid reserved_1: {pre_defined_1}'

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_mehd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version <= 1, f'invalid version: {version}'
	assert not box_flags, f'invalid flags: {box_flags}'
	print(prefix + f'version = {version}')

	st = struct.Struct('>' + ('Q' if version == 1 else 'I'))
	fragment_duration, = st.unpack(data.read(st.size))
	print(prefix + f'fragment_duration = {fragment_duration}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_smhd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	st = struct.Struct('>hH')
	balance, reserved = st.unpack(data.read(st.size))
	if show_defaults or balance != 0:
		print(prefix + f'balance = {balance}')
	assert not reserved, f'invalid reserved: {reserved}'

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_vmhd_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 1, f'invalid flags: {box_flags}'

	st = struct.Struct('>HHHH')
	graphicsmode, *opcolor = st.unpack(data.read(st.size))
	if show_defaults or graphicsmode != 0:
		print(prefix + f'graphicsmode = {graphicsmode}')
	if show_defaults or opcolor != [0, 0, 0]:
		print(prefix + f'opcolor = {opcolor}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_trex_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert version == 0, f'invalid version: {version}'
	assert box_flags == 0, f'invalid flags: {box_flags}'

	st = struct.Struct('>IIIII')
	track_ID, default_sample_description_index, default_sample_duration, default_sample_size, default_sample_flags = st.unpack(data.read(st.size))
	print(prefix + f'track_ID = {track_ID}')
	print(prefix + f'default_sample_description_index = {default_sample_description_index}')
	print(prefix + f'default_sample_duration = {default_sample_duration}')
	print(prefix + f'default_sample_size = {default_sample_size}')
	print(prefix + f'default_sample_flags = {default_sample_flags:08x}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

# TODO: mvhd, trhd, mdhd
# FIXME: vmhd, smhd, hmhd, sthd, nmhd
# FIXME: mehd


# CODEC-SPECIFIC BOXES

def parse_avcC_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	configurationVersion, = data.read(1)
	assert configurationVersion == 1, f'invalid configuration version: {configurationVersion}'
	avcProfileCompFlags = data.read(3)
	print(prefix + f'profile / compat / level: {avcProfileCompFlags.hex()}')
	composite_1, composite_2 = data.read(2)
	reserved_1, lengthSizeMinusOne = split_bits(composite_1, 8, 2, 0)
	reserved_2, numOfSequenceParameterSets = split_bits(composite_2, 8, 5, 0)
	assert reserved_1 == mask(6), f'invalid reserved_1: {reserved_1}'
	assert reserved_2 == mask(3), f'invalid reserved_2: {reserved_2}'
	print(prefix + f'lengthSizeMinusOne = {lengthSizeMinusOne}')

	for i in range(numOfSequenceParameterSets):
		size, = struct.unpack('>H', data.read(2))
		sps = data.read(size)
		assert len(sps) == size, f'not enough SPS data: expected {size}, found {len(sps)}'
		print(prefix + f'SPS: {sps.hex()}')
	numOfPictureParameterSets, = data.read(1)
	for i in range(numOfPictureParameterSets):
		size, = struct.unpack('>H', data.read(2))
		pps = data.read(size)
		assert len(pps) == size, f'not enough PPS data: expected {size}, found {len(pps)}'
		print(prefix + f'PPS: {pps.hex()}')

	# FIXME: parse extensions

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

def parse_svcC_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	configurationVersion, = data.read(1)
	assert configurationVersion == 1, f'invalid configuration version: {configurationVersion}'
	avcProfileCompFlags = data.read(3)
	print(prefix + f'profile / compat / level: {avcProfileCompFlags.hex()}')
	composite_1, composite_2 = data.read(2)
	complete_represenation, reserved_1, lengthSizeMinusOne = split_bits(composite_1, 8, 7, 2, 0)
	reserved_2, numOfSequenceParameterSets = split_bits(composite_2, 8, 7, 0)
	assert reserved_1 == mask(5), f'invalid reserved_1: {reserved_1}'
	assert reserved_2 == 0, f'invalid reserved_2: {reserved_2}'
	print(prefix + f'complete_represenation = {bool(complete_represenation)}')
	print(prefix + f'lengthSizeMinusOne = {lengthSizeMinusOne}')

	for i in range(numOfSequenceParameterSets):
		size, = struct.unpack('>H', data.read(2))
		sps = data.read(size)
		assert len(sps) == size, f'not enough SPS data: expected {size}, found {len(sps)}'
		print(prefix + f'SPS: {sps.hex()}')
	numOfPictureParameterSets, = data.read(1)
	for i in range(numOfPictureParameterSets):
		size, = struct.unpack('>H', data.read(2))
		pps = data.read(size)
		assert len(sps) == size, f'not enough PPS data: expected {size}, found {len(pps)}'
		print(prefix + f'PPS: {pps.hex()}')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'


# TABLES

def parse_sidx_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)
	assert not box_flags, f'invalid box_flags: {box_flags}'
	print(prefix + f'version = {version}')

	st = struct.Struct('>' + 'II' + ('II' if version == 0 else 'QQ') + 'HH')
	reference_ID, timescale, earliest_presentation_time, first_offset, reserved_1, reference_count = st.unpack(data.read(st.size))
	print(prefix + f'reference_ID = {reference_ID}')
	print(prefix + f'timescale = {timescale}')
	print(prefix + f'earliest_presentation_time = {earliest_presentation_time}')
	print(prefix + f'first_offset = {first_offset}')
	print(prefix + f'reference_count = {reference_count}')
	assert not reserved_1, f'invalid reserved_1 = {reserved_1}'
	for i in range(reference_count):
		composite_1, subsegment_duration, composite_2 = struct.unpack('>III', data.read(12))
		reference_type, referenced_size = split_bits(composite_1, 32, 31, 0)
		starts_with_SAP, SAP_type, SAP_delta_time = split_bits(composite_2, 32, 31, 28, 0)
		if i < max_rows:
			print(prefix + f'[reference {i:3}] type = {reference_type}, size = {referenced_size}, duration = {subsegment_duration}, starts_with_SAP = {starts_with_SAP}, SAP_type = {SAP_type}, SAP_delta_time = {SAP_delta_time}')
	if reference_count > max_rows:
		print(prefix + '...')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'

# FIXME: sample tables

def parse_trun_box(offset: int, data: memoryview, indent: int):
	prefix = ' ' * (indent * indent_n)
	data = io.BytesIO(data)
	version, box_flags = parse_full_box(data, prefix)

	sample_count, = struct.unpack('>I', data.read(4))
	print(prefix + f'version = {version}, flags = {box_flags:06x}, sample_count = {sample_count}')
	if box_flags & (1 << 0):
		data_offset, = struct.unpack('>i', data.read(4))
		print(prefix + f'data_offset = {data_offset:#x}')
	if box_flags & (1 << 2):
		first_sample_flags, = struct.unpack('>I', data.read(4))
		print(prefix + f'first_sample_flags = {first_sample_flags:08x}')

	s_offset = 0
	s_time = 0
	for s_idx in range(sample_count):
		s_text = []
		if box_flags & (1 << 8):
			sample_duration, = struct.unpack('>I', data.read(4))
			s_text.append(f'time={s_time:7} + {sample_duration:5}')
			s_time += sample_duration
		if box_flags & (1 << 9):
			sample_size, = struct.unpack('>I', data.read(4))
			s_text.append(f'offset={s_offset:#9x} + {sample_size:5}')
			s_offset += sample_size
		if box_flags & (1 << 10):
			sample_flags, = struct.unpack('>I', data.read(4))
			s_text.append(f'flags={sample_flags:08x}')	
		if box_flags & (1 << 11):
			sample_composition_time_offset, = struct.unpack('>I' if version == 0 else '>i', data.read(4))
			s_text.append(f'{sample_composition_time_offset}')
		if s_idx < max_rows:
			print(prefix + f'[sample {s_idx:4}] {", ".join(s_text)}')
	if sample_count > max_rows:
		print(prefix + '...')

	left = data.read()
	assert not left, f'{len(left)} bytes of trailing data'



parse_boxes(0, mp4mem)
