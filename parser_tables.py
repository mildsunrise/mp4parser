'''
This module holds static data scraped from various specs.
'''

box_registry = [
	({
		'name': 'ISO/IEC 14496-12',
		'title': 'Information technology — Coding of audio-visual objects — Part 12: ISO base media file format',
		'version': '2015',
		'url': 'https://www.iso.org/standard/68960.html',
	}, {
		'ftyp': ('FileTypeBox', 'Box'),
		'mdat': ('MediaDataBox', 'Box'),
		'pdin': ('ProgressiveDownloadInfoBox', 'FullBox'),
		'moov': ('MovieBox', 'Box'),
		'mvhd': ('MovieHeaderBox', 'FullBox'),
		'trak': ('TrackBox', 'Box'),
		'tkhd': ('TrackHeaderBox', 'FullBox'),
		'tref': ('TrackReferenceBox', 'Box'),
		'mdia': ('MediaBox', 'Box'),
		'mdhd': ('MediaHeaderBox', 'FullBox'),
		'hdlr': ('HandlerBox', 'FullBox'),
		'minf': ('MediaInformationBox', 'Box'),
		'nmhd': ('NullMediaHeaderBox', 'FullBox'),
		'elng': ('ExtendedLanguageBox', 'FullBox'),
		'stbl': ('SampleTableBox', 'Box'),
		'btrt': ('BitRateBox', 'Box'),
		'stsd': ('SampleDescriptionBox', 'FullBox'),
		'stdp': ('DegradationPriorityBox', 'FullBox'),
		'stts': ('TimeToSampleBox', 'FullBox'),
		'ctts': ('CompositionOffsetBox', 'FullBox'),
		'cslg': ('CompositionToDecodeBox', 'FullBox'),
		'stss': ('SyncSampleBox', 'FullBox'),
		'stsh': ('ShadowSyncSampleBox', 'FullBox'),
		'sdtp': ('SampleDependencyTypeBox', 'FullBox'),
		'edts': ('EditBox', 'Box'),
		'elst': ('EditListBox', 'FullBox'),
		'dinf': ('DataInformationBox', 'Box'),
		'url ': ('DataEntryUrlBox', 'FullBox'),
		'urn ': ('DataEntryUrnBox', 'FullBox'),
		'dref': ('DataReferenceBox', 'FullBox'),
		'stsz': ('SampleSizeBox', 'FullBox'),
		'stz2': ('CompactSampleSizeBox', 'FullBox'),
		'stsc': ('SampleToChunkBox', 'FullBox'),
		'stco': ('ChunkOffsetBox', 'FullBox'),
		'co64': ('ChunkLargeOffsetBox', 'FullBox'),
		'padb': ('PaddingBitsBox', 'FullBox'),
		'subs': ('SubSampleInformationBox', 'FullBox'),
		'saiz': ('SampleAuxiliaryInformationSizesBox', 'FullBox'),
		'saio': ('SampleAuxiliaryInformationOffsetsBox', 'FullBox'),
		'mvex': ('MovieExtendsBox', 'Box'),
		'mehd': ('MovieExtendsHeaderBox', 'FullBox'),
		'trex': ('TrackExtendsBox', 'FullBox'),
		'moof': ('MovieFragmentBox', 'Box'),
		'mfhd': ('MovieFragmentHeaderBox', 'FullBox'),
		'traf': ('TrackFragmentBox', 'Box'),
		'tfhd': ('TrackFragmentHeaderBox', 'FullBox'),
		'trun': ('TrackRunBox', 'FullBox'),
		'mfra': ('MovieFragmentRandomAccessBox', 'Box'),
		'tfra': ('TrackFragmentRandomAccessBox', 'FullBox'),
		'mfro': ('MovieFragmentRandomAccessOffsetBox', 'FullBox'),
		'tfdt': ('TrackFragmentBaseMediaDecodeTimeBox', 'FullBox'),
		'leva': ('LevelAssignmentBox', 'FullBox'),
		'trep': ('TrackExtensionPropertiesBox', 'FullBox'),
		'assp': ('AlternativeStartupSequencePropertiesBox', 'FullBox'),
		'sbgp': ('SampleToGroupBox', 'FullBox'),
		'sgpd': ('SampleGroupDescriptionBox', 'FullBox'),
		'udta': ('UserDataBox', 'Box'),
		'cprt': ('CopyrightBox', 'FullBox'),
		'tsel': ('TrackSelectionBox', 'FullBox'),
		'kind': ('KindBox', 'FullBox'),
		'meta': ('MetaBox', 'FullBox'),
		'xml ': ('XMLBox', 'FullBox'),
		'bxml': ('BinaryXMLBox', 'FullBox'),
		'iloc': ('ItemLocationBox', 'FullBox'),
		'pitm': ('PrimaryItemBox', 'FullBox'),
		'ipro': ('ItemProtectionBox', 'FullBox'),
		'fdel': ('FDItemInfoExtension', 'ItemInfoExtension'),
		'infe': ('ItemInfoEntry', 'FullBox'),
		'iinf': ('ItemInfoBox', 'FullBox'),
		'meco': ('AdditionalMetadataContainerBox', 'Box'),
		'mere': ('MetaboxRelationBox', 'FullBox'),
		'idat': ('ItemDataBox', 'Box'),
		'iref': ('ItemReferenceBox', 'FullBox'),
		'sinf': ('ProtectionSchemeInfoBox', 'Box'),
		'frma': ('OriginalFormatBox', 'Box'),
		'schm': ('SchemeTypeBox', 'FullBox'),
		'schi': ('SchemeInformationBox', 'Box'),
		'paen': ('PartitionEntry', 'Box'),
		'fiin': ('FDItemInformationBox', 'FullBox'),
		'fpar': ('FilePartitionBox', 'FullBox'),
		'fecr': ('FECReservoirBox', 'FullBox'),
		'segr': ('FDSessionGroupBox', 'Box'),
		'gitn': ('GroupIdToNameBox', 'FullBox'),
		'fire': ('FileReservoirBox', 'FullBox'),
		'strk': ('SubTrack', 'Box'),
		'stri': ('SubTrackInformation', 'FullBox'),
		'strd': ('SubTrackDefinition', 'Box'),
		'stsg': ('SubTrackSampleGroupBox', 'FullBox'),
		'rinf': ('RestrictedSchemeInfoBox', 'Box'),
		'stvi': ('StereoVideoBox', 'FullBox'),
		'sidx': ('SegmentIndexBox', 'FullBox'),
		'ssix': ('SubsegmentIndexBox', 'FullBox'),
		'prft': ('ProducerReferenceTimeBox', 'FullBox'),
		'icpv': ('IncompleteAVCSampleEntry', 'VisualSampleEntry'),
		'cinf': ('CompleteTrackInfoBox', 'Box'),
		'rtp ': ('RtpHintSampleEntry', 'SampleEntry'),
		'tims': ('timescaleentry', 'Box'),
		'tsro': ('timeoffset', 'Box'),
		'snro': ('sequenceoffset', 'Box'),
		'srtp': ('SrtpHintSampleEntry', 'SampleEntry'),
		'srpp': ('SRTPProcessBox', 'FullBox'),
		'hnti': ('moviehintinformation', 'box'),
		'rtp ': ('rtpmoviehintinformation', 'box'),
		'hnti': ('trackhintinformation', 'box'),
		'sdp ': ('rtptracksdphintinformation', 'box'),
		'hinf': ('hintstatisticsbox', 'box'),
		'trpy': ('hintBytesSent', 'box'),
		'nump': ('hintPacketsSent', 'box'),
		'tpyl': ('hintBytesSent', 'box'),
		'totl': ('hintBytesSent', 'box'),
		'npck': ('hintPacketsSent', 'box'),
		'tpay': ('hintBytesSent', 'box'),
		'maxr': ('hintmaxrate', 'box'),
		'dmed': ('hintmediaBytesSent', 'box'),
		'dimm': ('hintimmediateBytesSent', 'box'),
		'drep': ('hintrepeatedBytesSent', 'box'),
		'tmin': ('hintminrelativetime', 'box'),
		'tmax': ('hintmaxrelativetime', 'box'),
		'pmax': ('hintlargestpacket', 'box'),
		'dmax': ('hintlongestpacket', 'box'),
		'payt': ('hintpayloadID', 'box'),
		'fdp ': ('FDHintSampleEntry', 'SampleEntry'),
		'fdsa': ('FDsample', 'Box'),
		'fdpa': ('FDpacketBox', 'Box'),
		'extr': ('ExtraDataBox', 'Box'),
		'feci': ('FECInformationBox', 'Box'),
		'rm2t': ('MPEG2TSReceptionSampleEntry', 'MPEG2TSSampleEntry'),
		'sm2t': ('MPEG2TSServerSampleEntry', 'MPEG2TSSampleEntry'),
		'tPAT': ('PATBox', 'Box'),
		'tPMT': ('PMTBox', 'Box'),
		'tOD ': ('ODBox', 'Box'),
		'tsti': ('TSTimingBox', 'Box'),
		'istm': ('InitialSampleTimeBox', 'Box'),
		'pm2t': ('ProtectedMPEG2TransportStreamSampleEntry', 'MPEG2TransportStreamSampleEntry'),
		'rrtp': ('ReceivedRtpHintSampleEntry', 'SampleEntry'),
		'tssy': ('timestampsynchrony', 'Box'),
		'rssr': ('ReceivedSsrcBox', 'Box'),
		'rtpx': ('rtphdrextTLV', 'Box'),
		'rcsr': ('receivedCSRC', 'Box'),
		'rsrp': ('ReceivedSrtpHintSampleEntry', 'SampleEntry'),
		'ccid': ('ReceivedCryptoContextIdBox', 'Box'),
		'sroc': ('RolloverCounterBox', 'Box'),
		'roll': ('VisualRollRecoveryEntry', 'VisualSampleGroupEntry'),
		'roll': ('AudioRollRecoveryEntry', 'AudioSampleGroupEntry'),
		'prol': ('AudioPreRollEntry', 'AudioSampleGroupEntry'),
		'rash': ('RateShareEntry', 'SampleGroupDescriptionEntry'),
		'alst': ('AlternativeStartupEntry', 'VisualSampleGroupEntry'),
		'rap ': ('VisualRandomAccessEntry', 'VisualSampleGroupEntry'),
		'tele': ('TemporalLevelEntry', 'VisualSampleGroupEntry'),
		'sap ': ('SAPEntry', 'SampleGroupDescriptionEntry'),
		'vmhd': ('VideoMediaHeaderBox', 'FullBox'),
		'pasp': ('PixelAspectRatioBox', 'Box'),
		'clap': ('CleanApertureBox', 'Box'),
		'colr': ('ColourInformationBox', 'Box'),
		'smhd': ('SoundMediaHeaderBox', 'FullBox'),
		'srat': ('SamplingRateBox', 'FullBox'),
		'chnl': ('ChannelLayout', 'FullBox'),
		'dmix': ('DownMixInstructions', 'FullBox'),
		'tlou': ('TrackLoudnessInfo', 'LoudnessBaseBox'),
		'alou': ('AlbumLoudnessInfo', 'LoudnessBaseBox'),
		'ludt': ('LoudnessBox', 'Box'),
		'metx': ('XMLMetaDataSampleEntry', 'MetaDataSampleEntry'),
		'txtC': ('TextConfigBox', 'Fullbox'),
		'mett': ('TextMetaDataSampleEntry', 'MetaDataSampleEntry'),
		'uri ': ('URIBox', 'FullBox'),
		'uriI': ('URIInitBox', 'FullBox'),
		'urim': ('URIMetaSampleEntry', 'MetaDataSampleEntry'),
		'hmhd': ('HintMediaHeaderBox', 'FullBox'),
		'stxt': ('SimpleTextSampleEntry', 'PlainTextSampleEntry'),
		'sthd': ('SubtitleMediaHeaderBox', 'FullBox'),
		'stpp': ('XMLSubtitleSampleEntry', 'SubtitleSampleEntry'),
		'sbtt': ('TextSubtitleSampleEntry', 'SubtitleSampleEntry'),
		'free': ('FreeSpaceBox', 'Box'),
		'skip': ('FreeSpaceBox', 'Box'),
	}),
	({
		'name': 'ISO/IEC 14496-14',
		'title': 'Information technology — Coding of audio-visual objects — Part 14: MP4 file format',
		'version': '2003',
		'url': 'https://www.iso.org/standard/38538.html',
	}, {
		'iods': ('ObjectDescriptorBox', 'FullBox'),
		'esds': ('ESDBox', 'FullBox'),
		'mp4v': ('MP4VisualSampleEntry', 'VisualSampleEntry'),
		'mp4a': ('MP4AudioSampleEntry', 'AudioSampleEntry'),
		'mp4s': ('MpegSampleEntry', 'SampleEntry'),
	}),
	({
		'name': 'ISO/IEC 14496-15',
		'title': 'Information technology — Coding of audio-visual objects — Part 15: Carriage of network abstraction layer (NAL) unit structured video in ISO base media file format',
		'version': '2014',
		'url': 'https://www.iso.org/standard/65216.html',
	}, {
		'avcC': ('AVCConfigurationBox', 'Box'),
		'm4ds': ('MPEG4ExtensionDescriptorsBox', 'Box'),
		'avc1': ('AVCSampleEntry', 'VisualSampleEntry'),
		'avc3': ('AVCSampleEntry', 'VisualSampleEntry'),
		'avc2': ('AVC2SampleEntry', 'VisualSampleEntry'),
		'avc4': ('AVC2SampleEntry', 'VisualSampleEntry'),
		'avcp': ('AVCParameterSampleEntry', 'VisualSampleEntry'),
		'avss': ('AVCSubSequenceEntry', 'VisualSampleGroupEntry'),
		'avll': ('AVCLayerEntry', 'VisualSampleGroupEntry'),
		'svcC': ('SVCConfigurationBox', 'Box'),
		'seib': ('ScalabilityInformationSEIBox', 'Box'),
		'svcP': ('SVCPriorityAssignmentBox', 'Box'),
		'svc1': ('SVCSampleEntry', 'VisualSampleEntry'),
		'svc2': ('SVCSampleEntry', 'VisualSampleEntry'),
		'tiri': ('TierInfoBox', 'Box'),
		'tibr': ('TierBitRateBox', 'Box'),
		'svpr': ('PriorityRangeBox', 'Box'),
		'svop': ('SVCDependencyRangeBox', 'Box'),
		'svip': ('InitialParameterSetBox', 'Box'),
		'rrgn': ('RectRegionBox', 'Box'),
		'buff': ('BufferingBox', 'Box'),
		'ldep': ('TierDependencyBox', 'Box'),
		'iroi': ('IroiInfoBox', 'Box'),
		'tran': ('TranscodingInfoBox', 'Box'),
		'scif': ('ScalableGroupEntry', 'VisualSampleGroupEntry'),
		'mvif': ('MultiviewGroupEntry', 'VisualSampleGroupEntry'),
		'scnm': ('ScalableNALUMapEntry', 'VisualSampleGroupEntry'),
		'dtrt': ('DecodeRetimingEntry', 'VisualSampleGroupEntry'),
		'vipr': ('ViewPriorityBox', 'Box'),
		'vipr': ('ViewPriorityEntry', 'VisualSampleGroupEntry'),
		'sstl': ('SVCSubTrackLayerBox', 'FullBox'),
		'mstv': ('MVCSubTrackViewBox', 'FullBox'),
		'stti': ('SubTrackTierBox', 'FullBox'),
		'stmg': ('MVCSubTrackMultiviewGroupBox', 'FullBox'),
		'svmC': ('SVCMetadataSampleConfigBox', 'FullBox'),
		'qlif': ('SVCPriorityLayerInfoBox', 'Box'),
		'svcM': ('SVCMetadataSampleEntry', 'MetadataSampleEntry'),
		'icam': ('IntrinsicCameraParametersBox', 'FullBox'),
		'ecam': ('ExtrinsicCameraParametersBox', 'FullBox'),
		'vwid': ('ViewIdentifierBox', 'FullBox'),
		'mvcC': ('MVCConfigurationBox', 'Box'),
		'vsib': ('ViewScalabilityInformationSEIBox', 'Box'),
		'mvcg': ('MultiviewGroupBox', 'FullBox'),
		'swtc': ('MultiviewGroupRelationBox', 'FullBox'),
		'vwdi': ('MultiviewSceneInfoBox', 'Box'),
		'mvcP': ('MVCViewPriorityAssignmentBox', 'Box'),
		'hvcC': ('HEVCConfigurationBox', 'Box'),
		'hvc1': ('HEVCSampleEntry', 'VisualSampleEntry'),
		'hev1': ('HEVCSampleEntry', 'VisualSampleEntry'),
		'sync': ('SyncSampleEntry', 'VisualSampleGroupEntry'),
		'tscl': ('TemporalLayerEntry', 'VisualSampleGroupEntry'),
		'tsas': ('TemporalSubLayerEntry', 'VisualSampleGroupEntry'),
		'stsa': ('StepwiseTemporalLayerEntry', 'VisualSampleGroupEntry'),
		'sdep': ('SampleDependencyBox', 'FullBox'),
		'seii': ('SeiInformationBox', 'Box'),
		'mvci': ('MultiviewInformationBox', 'FullBox'),
		'mvra': ('MultiviewRelationAttributeBox', 'FullBox'),
	}),
	({
		'name': 'ISO/IEC 23001-7',
		'title': 'Information technology — MPEG systems technologies — Part 7: Common encryption in ISO base media file format files',
		'version': '2016',
		'url': 'https://www.iso.org/standard/68042.html',
	}, {
		'seig': ('CencSampleEncryptionInformationGroupEntry', 'SampleGroupEntry'),
		'senc': ('SampleEncryptionBox', 'FullBox'),
		'pssh': ('ProtectionSystemSpecificHeaderBox', 'FullBox'),
		'tenc': ('TrackEncryptionBox', 'FullBox'),
	}),
	({
		'name': 'ISO/IEC 23008-12',
		'title': 'Information technology — MPEG systems technologies — Part 12: Image File Format',
		'version': '17 January 2014 working draft',
		'url': 'https://www.iso.org/standard/83650.html',
	}, {
		'ccst': ('CodingConstraintsBox', 'FullBox'),
		'vsmi': ('VisualSampleToMetadataItemEntry', 'VisualSampleGroupEntry'),
		'mint': ('MetadataIntegrityBox', 'FullBox'),
	}),
	({
		'title': 'Encapsulation of Opus in ISO Base Media File Format',
		'version': '0.8.1 (incomplete)',
		'url': 'https://vfrmaniac.fushizen.eu/contents/opus_in_isobmff.html'
	}, {
		'Opus': ('OpusSampleEntry', 'AudioSampleEntry'),
		'dOps': ('OpusSpecificBox', 'Box'),
	}),
	({
		'title': 'AV1 Codec ISO Media File Format Binding',
		'version': 'v1.2.0',
		'url': 'https://aomediacodec.github.io/av1-isobmff/v1.2.0.html',
	}, {
		'av01': ('AV1SampleEntry', 'VisualSampleEntry'),
		'av1C': ('AV1CodecConfigurationBox', 'Box'),
		'av1f': ('AV1ForwardKeyFrameSampleGroupEntry', 'VisualSampleGroupEntry'),
		'av1m': ('AV1MultiFrameSampleGroupEntry', 'VisualSampleGroupEntry'),
		'av1s': ('AV1SwitchFrameSampleGroupEntry', 'VisualSampleGroupEntry'),
		'av1M': ('AV1MetadataSampleGroupEntry', 'VisualSampleGroupEntry'),
	}),
	({
		'title': '[ad-hoc]',
		'url': 'https://mp4ra.org/#/references',
	}, {
		'ID32': ('ID3v2Box', 'FullBox'),
	}),
]


# https://dashif.org/identifiers/content_protection#protection-system-specific-identifiers
protection_systems = {
	'6dd8b3c3-45f4-4a68-bf3a-64168d01a4a6': ('ABV DRM (MoDRM)', 'For further information please contact ABV International Pte Ltd. Documentation is available under NDA. ABV Content Protection for MPEG DASH (MoDRM v4.7 and above).'),
	'f239e769-efa3-4850-9c16-a903c6932efb': ('Adobe Primetime DRM version 4', 'For further information please contact Adobe.'),
	'616c7469-6361-7374-2d50-726f74656374': ('Alticast', 'For further information please contact Alticast. galtiprotect_drm@alticast.com.'),
	'94ce86fb-07ff-4f43-adb8-93d2fa968ca2': ('Apple FairPlay', 'Content Protection System Identifier for Apple FairPlay Streaming.'),
	'279fe473-512c-48fe-ade8-d176fee6b40f': ('Arris Titanium', 'For further information please contact multitrust.info@arris.com. Documentation is available under NDA. @value is specified in documentation related to a specific version of the product.'),
	'3d5e6d35-9b9a-41e8-b843-dd3c6e72c42c': ('ChinaDRM', 'ChinaDRM is defined by China Radio and Television Film Industry Standard GY/T 277-2014. @value indicates ChinaDRM specific solution provided by various vendors.'),
	'3ea8778f-7742-4bf9-b18b-e834b2acbd47': ('Clear Key AES-128', 'Identifier for HLS Clear Key encryption using CBC mode. This is to be used as an identifier when requesting key system information when using CPIX.'),
	'be58615b-19c4-4684-88b3-c8c57e99e957': ('Clear Key SAMPLE-AES', 'Identifier for HLS Clear Key encryption using CBCS mode. This is to be used as an identifier when requesting key system information when using CPIX.'),
	'e2719d58-a985-b3c9-781a-b030af78d30e': ('Clear Key DASH-IF', 'This identifier is meant to be used to signal the availability of W3C Clear Key in the context of a DASH presentation.'),
	'644fe7b5-260f-4fad-949a-0762ffb054B4': ('CMLA (OMA DRM)', 'A draft version of the CMLA Technical Specification which is in process with involved adopters is not published. It is planned to be chapter 18 of our CMLA Technical Specification upon completion and approval.Revisions of the CMLA Technical Specification become public upon CMLA approval. UUID will correlate to various related XML schema and PSSH components as well as elements of the content protection element relating to CMLA DASH mapping.'),
	'37c33258-7b99-4c7e-b15d-19af74482154': ('Commscope Titanium V3', 'Documentation available under NDA. @value is specified in documentation related to a specific version of the product. Contact multitrust.info@arris.com for further information.'),
	'45d481cb-8fe0-49c0-ada9-ab2d2455b2f2': ('CoreCrypt', 'CoreTrust Content Protection for MPEG-DASH. For further information and specification please contact CoreTurst at mktall@coretrust.com.'),
	'dcf4e3e3-62f1-5818-7ba6-0a6fe33ff3dd': ('DigiCAP SmartXess', 'For further information please contact DigiCAP. Documentation is available under NDA. DigiCAP SmartXess for DASH @value CA/DRM_NAME VERSION (CA 1.0, DRM+ 2.0)'),
	'35bf197b-530e-42d7-8b65-1b4bf415070f': ('DivX DRM Series 5', 'Please contact DivX for specifications.'),
	'80a6be7e-1448-4c37-9e70-d5aebe04c8d2': ('Irdeto Content Protection', 'For further information please contact Irdeto. Documentation is available under NDA.'),
	'5e629af5-38da-4063-8977-97ffbd9902d4': ('Marlin Adaptive Streaming Simple Profile V1.0', 'Details of what can be further specified within the ContentProtection element is in the specifications.'),
	'9a04f079-9840-4286-ab92-e65be0885f95': ('Microsoft PlayReady', 'For further information please contact Microsoft.'),
	'6a99532d-869f-5922-9a91-113ab7b1e2f3': ('MobiTV DRM', 'Identifier for any version of MobiDRM (MobiTV DRM). The version is signaled in the pssh box.'),
	'adb41c24-2dbf-4a6d-958b-4457c0d27b95': ('Nagra MediaAccess PRM 3.0', 'It identifies Nagra MediaAccess PRM 3.0 and above. Documentation is available under NDA.'),
	'1f83e1e8-6ee9-4f0d-ba2f-5ec4e3ed1a66': ('SecureMedia', 'Documentation is available under NDA. @value shall be Arris SecureMedia version XXXXXXX. XXXXXX is specified in documentation associated with a particular version of the product. The UUID will be made available in SecureMedia documentation shared with a partner or customer of SecureMedia Arris.'),
	'992c46e6-c437-4899-b6a0-50fa91ad0e39': ('SecureMedia SteelKnot', 'Documentation is available under NDA. @value shall be Arris SecureMedia SteelKnot version XXXXXXX. The exact length and syntax of XXXXXXX is specified in documentation associated with a particular version of the product. The UUID will be made available in SecureMedia SteelKnot documentation shared with a partner or customer of SecureMedia SteelKnot.'),
	'a68129d3-575b-4f1a-9cba-3223846cf7c3': ('Synamedia/Cisco/NDS VideoGuard DRM', 'Documentation is available under NDA.'),
	'aa11967f-cc01-4a4a-8e99-c5d3dddfea2d': ('Unitend DRM (UDRM)', 'For further information please contact y.ren@unitend.com.'),
	'9a27dd82-fde2-4725-8cbc-4234aa06ec09': ('Verimatrix VCAS', '@value is Verimatrix VCAS for DASH ViewRightWeb VV.vv (VV.vv is the version number). If used this can help the client to determine if the current DRM client can play the content.'),
	'b4413586-c58c-ffb0-94a5-d4896c1af6c3': ('Viaccess-Orca DRM (VODRM)', 'For further information please contact Viaccess-Orca. VODRM documentation is available under NDA.'),
	'793b7956-9f94-4946-a942-23e7ef7e44b4': ('VisionCrypt', 'For further information please contact gosdrm@gospell.com.'),
	'1077efec-c0b2-4d02-ace3-3c1e52e2fb4b': ('W3C Common PSSH box', 'This identifier is to be used as the SystemID for the Common PSSH box format defined by W3C as a preferred alternative to DRM system specific PSSH box formats. This identifier may be used in PSSH boxes and MPEG-DASH ContentProtection elements.'),
	'edef8ba9-79d6-4ace-a3c8-27dcd51d21ed': ('Widevine Content Protection', 'For further information please contact Widevine.'),
}


# based on <https://github.com/mp4ra/mp4ra.github.io/blob/5a9966617f953a65c708eb05d1bdc778ecc7e6bd/CSV/oti.csv>
# kind: Optional[Literal['audio', 'video', 'image', 'text', 'font']
# name: str # full name
# notes: Optional[list[str]] # notes indicated in CSV, if any
# short: Optional[str] # short / common name
# withdrawn: Optional[bool] # true if removed and shouldn't be used
object_types = {
	0x01: {                  'name': 'Systems ISO/IEC 14496-1',                                                                                         'notes': ['a'] },
	0x02: {                  'name': 'Systems ISO/IEC 14496-1',                                                                                         'notes': ['b'] },
	0x03: {                  'name': 'Interaction Stream',                                                                                                             },
	0x04: {                  'name': 'Extended BIFS',                                                                                                   'notes': ['h'] },
	0x05: {                  'name': 'AFX Stream',                                                                                                      'notes': ['i'] },
	0x06: { 'kind': 'font',  'name': 'Font Data Stream',                                                                                                               },
	0x07: {                  'name': 'Synthetised Texture',                                                                                                            },
	0x08: { 'kind': 'text',  'name': 'Text Stream',                                                                                                                    },
	0x09: {                  'name': 'LASeR Stream',                                                                                                                   },
	0x0A: {                  'name': 'Simple Aggregation Format (SAF) Stream',                                                                                         },

	0x20: { 'kind': 'video', 'name': 'Visual ISO/IEC 14496-2',                                            'short': 'MPEG-4 Video',                      'notes': ['c'] },
	0x21: { 'kind': 'video', 'name': 'Visual ITU-T Recommendation H.264 | ISO/IEC 14496-10',              'short': 'H.264 / AVC',                       'notes': ['g'] },
	0x22: { 'kind': 'video', 'name': 'Parameter Sets for ITU-T Recommendation H.264 | ISO/IEC 14496-10',  'short': 'H.264 / AVC (PPS / SPS)',           'notes': ['g'] },
	0x23: { 'kind': 'video', 'name': 'Visual ISO/IEC 23008-2 | ITU-T Recommendation H.265',               'short': 'H.265 / HEVC',                                     },

	0x40: { 'kind': 'audio', 'name': 'Audio ISO/IEC 14496-3',                                             'short': 'AAC',                               'notes': ['d'] },

	0x60: { 'kind': 'video', 'name': 'Visual ISO/IEC 13818-2 Simple Profile',                             'short': 'MPEG-2 Video (Simple Profile)',                    },
	0x61: { 'kind': 'video', 'name': 'Visual ISO/IEC 13818-2 Main Profile',                               'short': 'MPEG-2 Video (Main Profile)',                      },
	0x62: { 'kind': 'video', 'name': 'Visual ISO/IEC 13818-2 SNR Profile',                                'short': 'MPEG-2 Video (SNR Profile)',                       },
	0x63: { 'kind': 'video', 'name': 'Visual ISO/IEC 13818-2 Spatial Profile',                            'short': 'MPEG-2 Video (Spatial Profile)',                   },
	0x64: { 'kind': 'video', 'name': 'Visual ISO/IEC 13818-2 High Profile',                               'short': 'MPEG-2 Video (High Profile)',                      },
	0x65: { 'kind': 'video', 'name': 'Visual ISO/IEC 13818-2 422 Profile',                                'short': 'MPEG-2 Video (422 Profile)',                       },
	0x66: { 'kind': 'audio', 'name': 'Audio ISO/IEC 13818-7 Main Profile',                                'short': 'MPEG-2 AAC',                                       },
	0x67: { 'kind': 'audio', 'name': 'Audio ISO/IEC 13818-7 LowComplexity Profile',                       'short': 'MPEG-2 AAC-LC',                                    },
	0x68: { 'kind': 'audio', 'name': 'Audio ISO/IEC 13818-7 Scaleable Sampling Rate Profile',             'short': 'MPEG-2 AAC-SSR',                                   },
	0x69: { 'kind': 'audio', 'name': 'Audio ISO/IEC 13818-3',                                             'short': 'MPEG-2 BC Audio',                                  },
	0x6A: { 'kind': 'video', 'name': 'Visual ISO/IEC 11172-2',                                            'short': 'MPEG-1 Video',                                     },
	0x6B: { 'kind': 'audio', 'name': 'Audio ISO/IEC 11172-3',                                             'short': 'MPEG-1 Audio (usually MP3)',                       },
	0x6C: { 'kind': 'image', 'name': 'Visual ISO/IEC 10918-1',                                            'short': 'JPEG',                                             },
	0x6D: { 'kind': 'image', 'name': 'Portable Network Graphics',                                         'short': 'PNG',                               'notes': ['f'] },
	0x6E: { 'kind': 'image', 'name': 'Visual ISO/IEC 15444-1 (JPEG 2000)',                                'short': 'JPEG 2000',                                        },

	0xA0: { 'kind': 'audio', 'name': 'EVRC Voice',                                                                                                                     },
	0xA1: { 'kind': 'audio', 'name': 'SMV Voice',                                                                                                                      },
	0xA2: {                  'name': '3GPP2 Compact Multimedia Format (CMF)',                             'short': 'CMF',                                              },
	0xA3: { 'kind': 'video', 'name': 'SMPTE VC-1 Video',                                                                                                               },
	0xA4: { 'kind': 'video', 'name': 'Dirac Video Coder',                                                                                                              },
	0xA5: { 'kind': 'audio', 'name': 'AC-3',                                                              'withdrawn': True,                                           },
	0xA6: { 'kind': 'audio', 'name': 'Enhanced AC-3',                                                     'withdrawn': True,                                           },
	0xA7: { 'kind': 'audio', 'name': 'DRA Audio',                                                                                                                      },
	0xA8: { 'kind': 'audio', 'name': 'ITU G.719 Audio',                                                                                                                },
	0xA9: {                  'name': 'Core Substream',                                                                                                                 },
	0xAA: {                  'name': 'Core Substream + Extension Substream',                                                                                           },
	0xAB: {                  'name': 'Extension Substream containing only XLL',                                                                                        },
	0xAC: {                  'name': 'Extension Substream containing only LBR',                                                                                        },
	0xAD: { 'kind': 'audio', 'name': 'Opus audio',                                                        'short': 'Opus',                                             },
	0xAE: { 'kind': 'audio', 'name': 'AC-4',                                                              'withdrawn': True,                                           },
	0xAF: { 'kind': 'audio', 'name': 'Auro-Cx 3D audio',                                                                                                               },
	0xB0: { 'kind': 'video', 'name': 'RealVideo Codec 11',                                                                                                             },
	0xB1: { 'kind': 'video', 'name': 'VP9 Video',                                                         'short': 'VP9',                                              },
	0xB2: { 'kind': 'audio', 'name': 'DTS-UHD profile 2',                                                                                                              },
	0xB3: { 'kind': 'audio', 'name': 'DTS-UHD profile 3 or higher',                                                                                                    },

	0xE1: { 'kind': 'audio', 'name': '13K Voice',                                                                                                                      },
}


stream_types = {
	0x01: 'ObjectDescriptorStream',
	0x02: 'ClockReferenceStream',
	0x03: 'SceneDescriptionStream',
	0x04: 'VisualStream',
	0x05: 'AudioStream',
	0x06: 'MPEG7Stream',
	0x07: 'IPMPStream',
	0x08: 'ObjectContentInfoStream',
	0x09: 'MPEGJStream',
	0x0A: 'Interaction Stream',
	0x0B: 'IPMPToolStream',
	0x0C: 'FontDataStream',
	0x0D: 'StreamingText',
}


'''
class Namespace(TypedDict):
	# classes defined within this namespace
	classes: list[ClassEntry]
	# ranges for this namespace, if any
	ranges: list[NamespaceRange]
	# number over which entries are user private, otherwise reserved for ISO
	user_private: int

NamespaceRange = tuple[
	int, # start (inclusive)
	int, # end (noninclusive)
	str, # class name
]

class ClassEntry(TypedDict):
	# tag number, if any (unset on some base classes)
	tag: Optional[int]
	# identifier used to refer to the tag number, if any
	# (if typos are found, we prefer the name in the tag list)
	tag_name: Optional[str]
	# class name (will be used to look up handler)
	name: str
	# name of base class (None for root class)
	base_class: Optional[str]
	# handler function to parse this class (will be set automatically from globals)
	handler: Callable[...]

descriptor_namespaces: dict[str, Namespace]
'''
descriptor_namespaces = {

	'default': {
		'classes': [
			{ 'name': 'BaseDescriptor', 'base_class': None },

			{ 'tag': 0x03, 'base_class': 'BaseDescriptor', 'name': 'ES_Descriptor', 'tag_name': 'ES_DescrTag' },
			{ 'tag': 0x05, 'base_class': 'BaseDescriptor', 'name': 'DecoderSpecificInfo', 'tag_name': 'DecSpecificInfoTag' },
			{ 'tag': 0x04, 'base_class': 'BaseDescriptor', 'name': 'DecoderConfigDescriptor', 'tag_name': 'DecoderConfigDescrTag' },
			{ 'tag': 0x09, 'base_class': 'BaseDescriptor', 'name': 'IPI_DescrPointer', 'tag_name': 'IPI_DescrPointerTag' },
			{ 'tag': 0x0a, 'base_class': 'BaseDescriptor', 'name': 'IPMP_DescriptorPointer', 'tag_name': 'IPMP_DescrPointerTag' },
			{ 'tag': 0x0b, 'base_class': 'BaseDescriptor', 'name': 'IPMP_Descriptor', 'tag_name': 'IPMP_DescrTag' },
			{ 'tag': 0x60, 'base_class': 'BaseDescriptor', 'name': 'IPMP_ToolListDescriptor', 'tag_name': 'IPMP_ToolsListDescrTag' },
			{ 'tag': 0x61, 'base_class': 'BaseDescriptor', 'name': 'IPMP_Tool', 'tag_name': 'IPMP_ToolTag' },
			{ 'tag': 0x0c, 'base_class': 'BaseDescriptor', 'name': 'QoS_Descriptor', 'tag_name': 'QoS_DescrTag' },
			{ 'tag': 0x0d, 'base_class': 'BaseDescriptor', 'name': 'RegistrationDescriptor', 'tag_name': 'RegistrationDescrTag' },

			{ 'name': 'ObjectDescriptorBase', 'base_class': 'BaseDescriptor' },
			{ 'tag': 0x01, 'base_class': 'ObjectDescriptorBase', 'name': 'ObjectDescriptor', 'tag_name': 'ObjectDescrTag' },
			{ 'tag': 0x02, 'base_class': 'ObjectDescriptorBase', 'name': 'InitialObjectDescriptor', 'tag_name': 'InitialObjectDescrTag' },
			{ 'name': 'IP_IdentificationDataSet', 'base_class': 'BaseDescriptor' },
			{ 'tag': 0x07, 'base_class': 'IP_IdentificationDataSet', 'name': 'ContentIdentificationDescriptor', 'tag_name': 'ContentIdentDescrTag' },
			{ 'tag': 0x08, 'base_class': 'IP_IdentificationDataSet', 'name': 'SupplementaryContentIdentificationDescriptor', 'tag_name': 'SupplContentIdentDescrTag' },

			{ 'name': 'OCI_Descriptor', 'base_class': 'BaseDescriptor' },
			{ 'tag': 0x40, 'base_class': 'OCI_Descriptor', 'name': 'ContentClassificationDescriptor', 'tag_name': 'ContentClassificationDescrTag' },
			{ 'tag': 0x41, 'base_class': 'OCI_Descriptor', 'name': 'KeyWordDescriptor', 'tag_name': 'KeyWordDescrTag' },
			{ 'tag': 0x42, 'base_class': 'OCI_Descriptor', 'name': 'RatingDescriptor', 'tag_name': 'RatingDescrTag' },
			{ 'tag': 0x43, 'base_class': 'OCI_Descriptor', 'name': 'LanguageDescriptor', 'tag_name': 'LanguageDescrTag' },
			{ 'tag': 0x44, 'base_class': 'OCI_Descriptor', 'name': 'ShortTextualDescriptor', 'tag_name': 'ShortTextualDescrTag' },
			{ 'tag': 0x45, 'base_class': 'OCI_Descriptor', 'name': 'ExpandedTextualDescriptor', 'tag_name': 'ExpandedTextualDescrTag' },
			{ 'tag': 0x46, 'base_class': 'OCI_Descriptor', 'name': 'ContentCreatorNameDescriptor', 'tag_name': 'ContentCreatorNameDescrTag' },
			{ 'tag': 0x47, 'base_class': 'OCI_Descriptor', 'name': 'ContentCreationDateDescriptor', 'tag_name': 'ContentCreationDateDescrTag' },
			{ 'tag': 0x48, 'base_class': 'OCI_Descriptor', 'name': 'OCICreatorNameDescriptor', 'tag_name': 'OCICreatorNameDescrTag' },
			{ 'tag': 0x49, 'base_class': 'OCI_Descriptor', 'name': 'OCICreationDateDescriptor', 'tag_name': 'OCICreationDateDescrTag' },
			{ 'tag': 0x4a, 'base_class': 'OCI_Descriptor', 'name': 'SmpteCameraPositionDescriptor', 'tag_name': 'SmpteCameraPositionDescrTag' },
			{ 'tag': 0x4b, 'base_class': 'OCI_Descriptor', 'name': 'SegmentDescriptor', 'tag_name': 'SegmentDescrTag' },
			{ 'tag': 0x4c, 'base_class': 'OCI_Descriptor', 'name': 'MediaTimeDescriptor', 'tag_name': 'MediaTimeDescrTag' },

			{ 'name': 'ExtensionDescriptor', 'base_class': 'BaseDescriptor' },
			{ 'tag': 0x13, 'base_class': 'ExtensionDescriptor', 'name': 'ExtensionProfileLevelDescriptor', 'tag_name': 'ExtensionProfileLevelDescrTag' },
			{ 'tag': 0x14, 'base_class': 'BaseDescriptor', 'name': 'ProfileLevelIndicationIndexDescriptor', 'tag_name': 'ProfileLevelIndicationIndexDescrTag' },

			{ 'tag': 0x06, 'base_class': 'BaseDescriptor', 'name': 'SLConfigDescriptor', 'tag_name': 'SLConfigDescrTag' },
			{ 'tag': 0x64, 'base_class': 'SLConfigDescriptor', 'name': 'ExtendedSLConfigDescriptor', 'tag_name': 'ExtSLConfigDescrTag' },
			{ 'name': 'SLExtensionDescriptor', 'base_class': 'BaseDescriptor' },  # quirk, this class doesn't have a base class in the spec
			{ 'tag': 0x67, 'base_class': 'SLExtensionDescriptor', 'name': 'DependencyPointer', 'tag_name': 'DependencyPointerTag' },
			{ 'tag': 0x68, 'base_class': 'SLExtensionDescriptor', 'name': 'MarkerDescriptor', 'tag_name': 'DependencyMarkerTag' },

			{ 'tag': 0x69, 'base_class': 'BaseDescriptor', 'name': 'M4MuxChannelDescriptor', 'tag_name': 'M4MuxChannelDescrTag' },
			{ 'tag': 0x65, 'base_class': 'BaseDescriptor', 'name': 'M4MuxBufferSizeDescriptor', 'tag_name': 'M4MuxBufferSizeDescrTag' },
			{ 'tag': 0x62, 'base_class': 'BaseDescriptor', 'name': 'M4MuxTimingDescriptor', 'tag_name': 'M4MuxTimingDescrTag' },
			{ 'tag': 0x63, 'base_class': 'BaseDescriptor', 'name': 'M4MuxCodeTableDescriptor', 'tag_name': 'M4MuxCodeTableDescrTag' },
			{ 'tag': 0x66, 'base_class': 'BaseDescriptor', 'name': 'M4MuxIdentDescriptor', 'tag_name': 'M4MuxIdentDescrTag' },

			# defined in ISO/IEC 14496-14. names for the last two are made up as not defined formally anywhere
			{ 'tag': 0x0e, 'base_class': 'BaseDescriptor', 'name': 'ES_ID_Inc', 'tag_name': 'ES_ID_IncTag' },
			{ 'tag': 0x0f, 'base_class': 'BaseDescriptor', 'name': 'ES_ID_Ref', 'tag_name': 'ES_ID_RefTag' },
			{ 'tag': 0x11, 'base_class': 'ObjectDescriptor', 'name': '<MP4ObjectDescriptor>', 'tag_name': 'MP4_OD_Tag' },
			{ 'tag': 0x10, 'base_class': 'InitialObjectDescriptor', 'name': '<MP4InitialObjectDescriptor>', 'tag_name': 'MP4_IOD_Tag' },

			# was unable to find where this is defined
			{ 'tag': 0x12, 'base_class': 'BaseDescriptor', 'name': '<IPL_DescrPointerRef>', 'tag_name': 'IPL_DescrPointerRefTag' },
		],
		'ranges': [
			(0x40, 0x60, 'OCI_Descriptor'),
			(0x6A, 0xFF, 'ExtensionDescriptor'),
		],
		'user_private': 0xC0,
	},

	'command': {
		'classes': [
			{ 'name': 'BaseCommand', 'base_class': None },

			{ 'tag': 0x01, 'base_class': 'BaseCommand', 'name': 'ObjectDescriptorUpdate', 'tag_name': 'ObjectDescrUpdateTag' },
			{ 'tag': 0x02, 'base_class': 'BaseCommand', 'name': 'ObjectDescriptorRemove', 'tag_name': 'ObjectDescrRemoveTag' },
			{ 'tag': 0x03, 'base_class': 'BaseCommand', 'name': 'ES_DescriptorUpdate', 'tag_name': 'ES_DescrUpdateTag' },
			{ 'tag': 0x04, 'base_class': 'BaseCommand', 'name': 'ES_DescriptorRemove', 'tag_name': 'ES_DescrRemoveTag' },
			{ 'tag': 0x05, 'base_class': 'BaseCommand', 'name': 'IPMP_DescriptorUpdate', 'tag_name': 'IPMP_DescrUpdateTag' },
			{ 'tag': 0x06, 'base_class': 'BaseCommand', 'name': 'IPMP_DescriptorRemove', 'tag_name': 'IPMP_DescrRemoveTag' },
			{ 'tag': 0x08, 'base_class': 'BaseCommand', 'name': 'ObjectDescriptorExecute', 'tag_name': 'ObjectDescrExecuteTag' },

			# defined in ISO/IEC 14496-14. names is made up as not defined formally anywhere
			{ 'tag': 0x07, 'base_class': 'ES_DescriptorRemove', 'name': '<ES_DescriptorRemoveRef>', 'tag_name': 'ES_DescrRemoveRefTag' },
		],
		'user_private': 0xC0,
	},

	'QoS': {
		'classes': [
			{ 'name': 'QoS_Qualifier', 'base_class': None },

			{ 'tag': 0x01, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_MAX_DELAY' },
			{ 'tag': 0x02, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_PREF_MAX_DELAY' },
			{ 'tag': 0x03, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_LOSS_PROB' },
			{ 'tag': 0x04, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_MAX_GAP_LOSS' },
			{ 'tag': 0x41, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_MAX_AU_SIZE' },
			{ 'tag': 0x42, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_AVG_AU_SIZE' },
			{ 'tag': 0x43, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_MAX_AU_RATE' },
			{ 'tag': 0x44, 'base_class': 'QoS_Qualifier', 'name': 'QoS_Qualifier_REBUFFERING_RATIO' },
		],
		'user_private': 0x80,
	},

	'IPMP': {
		'classes': [
			{ 'name': 'IPMP_Data_BaseClass', 'base_class': None },  # <- keep in mind this has fields

			{ 'tag': 0x10, 'base_class': 'IPMP_Data_BaseClass', 'name': 'IPMP_ParamtericDescription', 'tag_name': 'IPMP_ParamtericDescription_tag' },

			# tag numbers defined in ISO/IEC 14496-13
			# FIXME: define them here, and set user_private
		],
	},

}