'''
Handlers for each box
'''

from typing import List

from mp4parser import \
	Parser, max_dump, max_rows, mask, print_hex_dump, \
	format_time, format_size, format_fraction, decode_language, \
	parse_boxes, parse_fullbox, \
	ansi_bold, ansi_dim, ansi_fg1, ansi_fg2
from parser_tables import \
	protection_systems, qtff_well_known_types, iso_369_2t_lang_codes
import descriptors


def parse_skip_box(ps: Parser):
	data = ps.read()
	if any(bytes(data)):
		print_hex_dump(data, ps.prefix)
	else:
		ps.print(ansi_dim(ansi_fg2(f'({len(data)} empty bytes)')))

parse_free_box = parse_skip_box


# BOX CONTAINERS THAT ALSO HAVE A PREPENDED BINARY STRUCTURE

def parse_meta_box(ps: Parser):
	parse_fullbox(ps)
	parse_boxes(ps)

# hack: use a global variable because I'm too lazy to rewrite everything to pass this around
# FIXME: remove this hack, which is sometimes unreliable since there can be inner handlers we don't care about
last_handler_seen = None

def parse_hdlr_box(ps: Parser):
	parse_fullbox(ps)
	# FIXME: a lot of videos seem to put stuff in the 2nd reserved (apple metadata?), some in the 1st
	ps.reserved('pre_defined', ps.bytes(4))
	handler_type = ps.fourcc()
	ps.reserved('reserved', ps.bytes(4 * 3))
	name = ps.bytes().decode('utf-8')
	ps.print(f'handler_type = {repr(handler_type)}, name = {repr(name)}')

	global last_handler_seen
	last_handler_seen = handler_type

def parse_stsd_box(ps: Parser):
	version, _ = parse_fullbox(ps, max_version=255)
	entry_count = ps.int(4)

	contents_fn = lambda *a, **b: parse_sample_entry_contents(*a, **b, version=version)
	boxes = parse_boxes(ps, contents_fn=contents_fn)
	assert len(boxes) == entry_count, f'entry_count ({entry_count}) not matching boxes present'

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
	ps.field('resolution', (ps.fixed16(), ps.fixed16()), format_size, default=(72, 72))
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

def parse_language(ps: Parser):
	language = ps.bytes(2)
	ps.field('language', decode_language(language) if any(language) else None,
		str, describe=lambda l: l and iso_369_2t_lang_codes.get(l))

def parse_mfhd_box(ps: Parser):
	parse_fullbox(ps)
	ps.field('sequence_number', ps.int(4))

def parse_mvhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps, 1)
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
	version, box_flags = parse_fullbox(ps, 1)
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
	version, box_flags = parse_fullbox(ps, 1)
	wsize = [4, 8][version]

	ps.field('creation_time', ps.int(wsize), format_time, default=0)
	ps.field('modification_time', ps.int(wsize), format_time, default=0)
	ps.field('timescale', ps.int(4))
	ps.field('duration', ps.int(wsize), default=mask(wsize))
	parse_language(ps)
	ps.reserved('pre_defined_1', ps.int(2))

def parse_mehd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps, 1)
	wsize = [4, 8][version]

	fragment_duration = ps.int(wsize)
	ps.field('fragment_duration', fragment_duration)

def parse_smhd_box(ps: Parser):
	parse_fullbox(ps)
	ps.field('balance', ps.sint(2), default=0)
	ps.reserved('reserved', ps.int(2))

def parse_vmhd_box(ps: Parser):
	_, box_flags = parse_fullbox(ps, 0, 1, default_flags=1)
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
	parse_fullbox(ps)
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
	parse_fullbox(ps)
	parse_language(ps)
	ps.print(f'ID3v2 data =')
	print_hex_dump(ps.read(), ps.prefix + '  ')

def parse_dref_box(ps: Parser):
	parse_fullbox(ps)
	entry_count = ps.int(4)
	boxes = parse_boxes(ps)
	assert len(boxes) == entry_count, f'entry_count ({entry_count}) not matching boxes present'

def parse_url_box(ps: Parser):
	parse_fullbox(ps)
	if ps.ended: return
	ps.field('location', ps.string())

def parse_urn_box(ps: Parser):
	parse_fullbox(ps)
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
	version, box_flags = parse_fullbox(ps, 2)

	ps.field('grouping_type', ps.fourcc())
	if version == 1:
		ps.field('default_length', default_length := ps.int(4))
	elif version >= 2:
		ps.field('default_sample_description_index', ps.int(4))

	entry_count = ps.int(4)
	for i in range(entry_count):
		ps.print(f'- entry {i+1}:')
		if version == 1:
			default_length = default_length # type: ignore
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

def parse_av1C_box(ps: Parser):
	with ps.bits(4) as br:
		ps.reserved('marker', br.bit(), 1)
		if (version := br.read(7)) != 1:
			raise AssertionError(f'invalid configuration version: {version}')
		ps.field('seq_profile', br.read(3))
		ps.field('seq_level_idx_0', br.read(5))
		ps.field('seq_tier_0', br.bit())
		ps.field('high_bitdepth', br.bit())
		ps.field('twelve_bit', br.bit())
		ps.field('monochrome', br.bit())
		ps.field('chroma_subsampling_x', br.bit())
		ps.field('chroma_subsampling_y', br.bit())
		ps.field('chroma_sample_position', br.read(2))
		ps.reserved('reserved', br.read(3))

		if br.bit():
			ps.field('initial_presentation_delay_minus_one', br.read(4))
		else:
			ps.reserved('reserved', br.read(4))

	ps.print('configOBUs =')
	print_hex_dump(ps.read(), ps.prefix + '  ')

def parse_av1f_box(ps: Parser):
	ps.field('fwd_distance', ps.int(1))

def parse_esds_box(ps: Parser):
	parse_fullbox(ps)
	with ps.in_object():
		descriptors.parse_descriptor(ps, expected=3)

parse_iods_box = parse_esds_box

def parse_m4ds_box(ps: Parser):
	descriptors.parse_descriptors(ps)

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
	version, box_flags = parse_fullbox(ps, 1)
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
	version, box_flags = parse_fullbox(ps, 1)
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
	parse_fullbox(ps)

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
	version, box_flags = parse_fullbox(ps, 1)

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
	parse_fullbox(ps)

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
	parse_fullbox(ps)

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
	parse_fullbox(ps)

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		chunk_offset = ps.int(4)
		if i < max_rows:
			ps.print(f'[chunk {i+1:5}] offset = {chunk_offset:#08x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_co64_box(ps: Parser):
	parse_fullbox(ps)

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		chunk_offset = ps.int(8)
		if i < max_rows:
			ps.print(f'[chunk {i+1:5}] offset = {chunk_offset:#016x}')
	if entry_count > max_rows:
		ps.print('...')

def parse_stss_box(ps: Parser):
	parse_fullbox(ps)

	entry_count = ps.int(4)
	ps.field('entry_count', entry_count)
	for i in range(entry_count):
		sample_number = ps.int(4)
		if i < max_rows:
			ps.print(f'[sync sample {i:5}] sample_number = {sample_number:6}')
	if entry_count > max_rows:
		ps.print('...')

def parse_sbgp_box(ps: Parser):
	version, box_flags = parse_fullbox(ps, 1)

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
	_, box_flags = parse_fullbox(ps, 0, 1)

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
	version, box_flags = parse_fullbox(ps, 1, 1)
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
	version, box_flags = parse_fullbox(ps, 1)
	wsize = [4, 8][version]
	ps.field('baseMediaDecodeTime', ps.int(wsize))

def parse_tfhd_box(ps: Parser):
	version, box_flags = parse_fullbox(ps, 0, 0x3003b)

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
	version, box_flags = parse_fullbox(ps, 1, 0xf05)

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
	version, box_flags = parse_fullbox(ps, 0, 1)

	ps.field('scheme_type', ps.fourcc())
	ps.field('scheme_version', ps.int(4), '#x')
	if box_flags & 1:
		ps.field('scheme_uri', ps.string())

def parse_tenc_box(ps: Parser):
	version, box_flags = parse_fullbox(ps, 1)

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
	version, box_flags = parse_fullbox(ps, 1)

	ps.field('SystemID', ps.uuid(), str, describe=format_system_id)

	if version > 0:
		KID_count = ps.int(4)
		for i in range(KID_count):
			ps.print(f'- KID: {ps.bytes(16).hex()}')

	ps.print(f'Data =')
	print_hex_dump(ps.read(ps.int(4)), ps.prefix + '  ')


# QTFF METADATA
# <https://developer.apple.com/documentation/quicktime-file-format/metadata_atoms_and_types>

def parse_ilst_box(ps: Parser):
	parse_boxes(ps, parse_metadata_value_box)

def parse_metadata_value_box(btype: str, ps: Parser):
	parse_boxes(ps)

def parse_data_box(ps: Parser):
	# type indicator
	ps.field('type_indicator_byte', type_indicator_byte := ps.int(1),
		default=0, describe={ 0: 'well known type' }.get)
	ps.field('type_indicator_type', type_indicator := ps.int(3),
		default=1, describe=lambda x: qtff_well_known_types.get(x, (None,None))[0])

	# locale indicator
	parse_country = lambda x: x.decode('latin-1') if x[0] else x[1]
	ps.field('country_indicator', parse_country(ps.bytes(2)), default=0) # FIXME: describe function
	parse_language = lambda x: decode_language(x) if x[0] else x[1]
	ps.field('language_indicator', parse_language(ps.bytes(2)), default=0) # FIXME: describe function

	# data
	if type_indicator_byte == 0 and type_indicator == 1:
		ps.field('value', ps.bytes().decode('utf-8'))
	else:
		ps.print('value =')
		print_hex_dump(ps.read(), ps.prefix)
