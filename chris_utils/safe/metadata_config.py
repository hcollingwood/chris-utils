from chris_utils.safe.dat_xml_generator import Schema as DATSchema, Include, Annotation, Element, Documentation, Sequence, ComplexType, BlockEncoding,AppInfo,BlockLength,Block,BlockOccurrence



def dat_schema():
    complex_elements = [
        Element(
            name="pixel",
            type="pixelType",
            min_occurs="0",
            max_occurs="unbounded",
            annotation=Annotation(
                documentation=Documentation(
                    lang="en",
                    value="The file contains binary data in 12-bit pixel values. The raw block length for image data varies depending on the band configuration—specifically whether it's full or half width, and whether it's binned or unbinned."
                ),
                app_info=AppInfo(
                    block=Block(
                        encoding=BlockEncoding(value="BINARY"),
                        length=BlockLength(value=12),
                        # occurence=BlockOccurrence(value="unbounded"),
                    )
                ),
            ),
        )
    ]

    complex_type = [
        ComplexType(
            name="measurementType",
            sequence=Sequence(elements=complex_elements),
        ),
    ]

    documentation = Documentation(
        lang="en",
        value="A SAFE product generated with CHRIS PROBA-1 data includes one .dat file, containing 12-bit pixel values. The data is structured in fixed-length packets, as defined by PACKETSIZE in the headers. Each packet includes a header containing synchronization markers, metadata, and checksums, and a block of image data, where pixels from odd and even channels are interleaved. The raw block length for image data varies depending on the band configuration—specifically whether it's full or half width, and whether it's binned or unbinned. These values represent the number of bytes per channel per line at 12 bits per pixel. The actual block length is determined by the configuration specified in the .set file the data corresponding to one imaging sequence along with the corresponding header data.",
    )
    element = Element(
        name="measurement",
        type="measurementType",
        annotation=Annotation(documentation=documentation),
    )
    xml = DATSchema(
        # include=Include(schema_location="mos-object-types.xsd"),
        element=element,
        complex_type=complex_type,
    )

    return xml

def txt_schema():
    complex_elements = [
        Element(
            name="txt",
            type="txtType",
            # min_occurs="0",
            # max_occurs="unbounded",
            annotation=Annotation(
                documentation=Documentation(
                    lang="en",
                    value="The file contains metadata in plain text format."
                ),
                app_info=AppInfo(
                    block=Block(
                        encoding=BlockEncoding(value="ASCII"),
                        # length=BlockLength(value=12),
                        # occurence=BlockOccurrence(value="unbounded"),
                    )
                ),
            ),
        )
    ]

    complex_type = [
        ComplexType(
            name="measurementType",
            sequence=Sequence(elements=complex_elements),
        ),
    ]

    documentation = Documentation(
        lang="en",
        value="A SAFE product generated with CHRIS PROBA-1 data includes one .txt file, containing image attribute data. File is to be read vertically with attributes denoted by lines starting with '//' and the corresponding value on the line below.",
    )
    element = Element(
        name="measurement",
        type="measurementType",
        annotation=Annotation(documentation=documentation),
    )
    xml = DATSchema(
        # include=Include(schema_location="mos-object-types.xsd"),
        element=element,
        complex_type=complex_type,
    )

    return xml



def hdr_schema():
    complex_elements = [
        Element(
            name="hdr",
            type="hdrType",
            # min_occurs="0",
            # max_occurs="unbounded",
            annotation=Annotation(
                documentation=Documentation(
                    lang="en",
                    value="The file contains header data in plain text format."
                ),
                app_info=AppInfo(
                    block=Block(
                        encoding=BlockEncoding(value="ASCII"),
                        # length=BlockLength(value=12),
                        # occurence=BlockOccurrence(value="unbounded"),
                    )
                ),
            ),
        )
    ]

    complex_type = [
        ComplexType(
            name="measurementType",
            sequence=Sequence(elements=complex_elements),
        ),
    ]

    documentation = Documentation(
        lang="en",
        value="A SAFE product generated with CHRIS PROBA-1 data includes one .hdr file, containing image header data. Attributes and the corresponding values are defined per line, separated by an equals sign e.g. attribute = value.",
    )
    element = Element(
        name="measurement",
        type="measurementType",
        annotation=Annotation(documentation=documentation),
    )
    xml = DATSchema(
        # include=Include(schema_location="mos-object-types.xsd"),
        element=element,
        complex_type=complex_type,
    )

    return xml


def set_schema():
    complex_elements = [
        Element(
            name="set",
            type="setType",
            # min_occurs="0",
            # max_occurs="unbounded",
            annotation=Annotation(
                documentation=Documentation(
                    lang="en",
                    value="The file contains configuration data in binary format."
                ),
                app_info=AppInfo(
                    block=Block(
                        encoding=BlockEncoding(value="BINARY"),
                        length=BlockLength(value=12),
                        # occurence=BlockOccurrence(value="unbounded"),
                    )
                ),
            ),
        )
    ]

    complex_type = [
        ComplexType(
            name="measurementType",
            sequence=Sequence(elements=complex_elements),
        ),
    ]

    documentation = Documentation(
        lang="en",
        value="A SAFE product generated with CHRIS PROBA-1 data includes one .set file, containing image configuration data. This defines values including integers, flags and dimensions.",
    )
    element = Element(
        name="measurement",
        type="measurementType",
        annotation=Annotation(documentation=documentation),
    )
    xml = DATSchema(
        # include=Include(schema_location="mos-object-types.xsd"),
        element=element,
        complex_type=complex_type,
    )

    return xml