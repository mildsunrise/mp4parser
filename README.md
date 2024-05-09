# mp4parser

Portable* ISO Base Media File Format dissector / parser.

(*) Needs Python 3.8+

Goals / development guidelines:

  - Low level. Meant as a dissector, i.e. to obtain info about the structure of the file
    rather than high level info.

  - Print offsets to every box to let users inspect deeper. If parsing fails, print an
    error for that particular box followed by a hexdump.

  - Don't parse non-MP4 structures. It is fine to parse the info in the MP4 boxes,
    as long as this info is specific to MP4. Examples of things we don't parse:
     - Codec-specific structures (SPS, PPS)
     - ID3v2 blobs
     - H.264 NALUs
     - XML
     - ICC profiles
    These blobs are just left as hexdump, with their offsets / length printed in case the
    user wants to dive deeper.
    The only exception is when this info is needed to dissect other MP4 boxes correctly.

  - Focus on dissection, not parsing. First priority is to show the box structure correctly
    and to 'dig as deeper as possible' if there are nested boxes; decoding non-box info
    (instead of showing hexdumps) is second priority.

  - Print *every field on the wire*, with only minimal / mostly obvious postprocessing.
    Exception: versions / flags that are restricted to a single value.
    Exception: values which have a default (`template`) set by spec, which may be omitted
    from output if the value is set to the default, and `show_defaults` was not set.
    Exception: big boxes, or long rows of output, may be summarized through the
    `max_dump` (for hexdumps) and `max_rows` (for tables) options.

  - Option to hide lengths / offset (for i.e. diffs).

  - In the future we should have options to make the output interoperable (make it machine
    friendly like JSON), don't use global variables for config/state, allow output to a
    different file (for programmatic use).

  - Parsed fields should be named exactly like in the spec's syntax.
    Both in code, and in the output.

  - Performance isn't a concern. Correctness is more important, but it's also nice for
    the code to be 'hacker-friendly' for people who may want to tweak it.
