'''
MPEG-4 part 1 DESCRIPTORS (based on 2010 edition)
(these aren't specific to ISOBMFF and so we shouldn't parse them buuuut
they're still part of MPEG-4 and not widely known so we'll make an exception)
'''

import re
from typing import Iterable, TypeVar, Tuple, Dict

from mp4parser import \
	Parser, mask, \
	ansi_bold, ansi_dim, ansi_fg4, ansi_fg1, \
	max_dump, show_descriptions, print_hex_dump
from parser_tables import descriptor_namespaces, object_types, stream_types

T = TypeVar('T')
T2 = TypeVar('T2')

def unique_dict(x: Iterable[Tuple[T, T2]]) -> Dict[T, T2]:
	r = {}
	for k, v in x:
		assert k not in r, f'duplicate key {repr(k)}: existing {repr(r[k])}, got {repr(v)}'
		r[k] = v
	return r


# CORE PARSING

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


# DESCRIPTOR HANDLERS

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

def parse_InitialObjectDescriptor_descriptor(ps: Parser):
	with ps.bits(2) as br:
		ps.field('ObjectDescriptorID', br.read(10))
		URL_Flag = br.bit()
		ps.field('includeInlineProfileLevelFlag', br.bit())
		ps.reserved('reserved', br.read(4), mask(4))
	if URL_Flag:
		ps.field('URLstring', ps.bytes(ps.int(1)).decode('utf-8'))
	else:
		ps.field('ODProfileLevelIndication', ps.int(1))
		ps.field('sceneProfileLevelIndication', ps.int(1))
		ps.field('audioProfileLevelIndication', ps.int(1))
		ps.field('visualProfileLevelIndication', ps.int(1))
		ps.field('graphicsProfileLevelIndication', ps.int(1))
		# ES_Descriptor esDescr[1 .. 255];
		# OCI_Descriptor ociDescr[0 .. 255];
		# IPMP_DescriptorPointer ipmpDescrPtr[0 .. 255];
		# IPMP_Descriptor ipmpDescr [0 .. 255];
		# IPMP_ToolListDescriptor toolListDescr[0 .. 1];
	parse_descriptors(ps)


# METADATA

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
