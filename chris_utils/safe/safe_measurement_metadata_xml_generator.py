from typing import Optional

from pydantic_xml import BaseXmlModel, attr, element

namespaces = {
    "sdf": "http://www.gael.fr/2004/12/drb/sdf",
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


class BlockOccurrence(BaseXmlModel, tag="occurrence", ns="sdf"):
    value: str


class BlockLength(BaseXmlModel, tag="length", ns="sdf"):
    unit: Optional[str] = attr(default=None)
    value: int


class BlockEncoding(BaseXmlModel, tag="encoding", ns="sdf"):
    value: str


class Block(BaseXmlModel, nsmap=namespaces, tag="block", ns="sdf"):
    encoding: BlockEncoding
    occurence: Optional[BlockOccurrence] = element(default=None)
    length: BlockLength


class AppInfo(BaseXmlModel, tag="appinfo", ns="xs"):
    block: Block


class Documentation(BaseXmlModel, nsmap=namespaces, tag="documentation", ns="xs"):
    lang: str = attr(ns="xml", default="en")
    value: str


class Annotation(BaseXmlModel, nsmap=namespaces, tag="annotation", ns="xs"):
    documentation: Documentation
    app_info: Optional[AppInfo] = element(default=None)


class Element(BaseXmlModel, tag="element", ns="xs"):
    name: str = attr()
    type: str = attr(default=None)
    min_occurs: Optional[str] = attr(name="minOccurs", default=None)
    max_occurs: Optional[str] = attr(name="maxOccurs", default=None)
    annotation: Annotation
    complex_type: Optional["ComplexType"] = element(default=None)


class Sequence(BaseXmlModel, nsmap=namespaces, tag="sequence", ns="xs"):
    elements: list[Element]


class ComplexType(BaseXmlModel, nsmap=namespaces, tag="complexType", ns="xs"):
    name: Optional[str] = attr(default=None)
    sequence: Sequence


# class Documentation(BaseXmlModel, tag="documentation", ns="xs"):
#     lang: str = attr(default="en")
#     value: str = element

# class Annotation(BaseXmlModel, nsmap=namespaces, tag="annotation", ns="xs"):
#     documentation: Documentation

# class Element(BaseXmlModel, tag="element", ns="xs"):
#     name: str = attr()
#     type: str = attr()
#     annotation: Annotation


class Include(BaseXmlModel, tag="include", ns="xs"):
    schema_location: str = attr(name="schemaLocation")


class Schema(BaseXmlModel, nsmap=namespaces, ns="xs", tag="schema"):
    xmlns: str = attr()
    target_namespace: str = attr(name="targetNamespace")
    include: Include
    element: Element
    complex_type: list[ComplexType]

    def __init__(self, **data):
        measurement_complex_element = [
            Element(
                name="line",
                type="lineType",
                min_occurs="0",
                max_occurs="unbounded",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en", value="The Data Unit (line) is 6,184 bytes long"
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=6184),
                            occurence=BlockOccurrence(value="unbounded"),
                        )
                    ),
                ),
            )
        ]
        line_complex_element = [
            Element(
                name="auxiliaryData",
                type="auxiliaryDataType",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value="The Auxiliary Data field is 40 bytes long (fixed length) and reports information extracted from the telemetry data during the Level0 processing.",
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=40),
                        )
                    ),
                ),
            ),
            Element(
                name="videoLine",
                type="videoLineType",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value="The Video Line is 6144 bytes long. Each Video Line contains a sequence of 2048 pixels, with 4 bands data words each, word 6 bits long.",
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=6144),
                        )
                    ),
                ),
            ),
        ]

        minor_frame_complex_element = [
            Element(
                name="pixel",
                min_occurs="8",
                max_occurs="8",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value="Each pixel contains 4 bands data words. Each MESSR data word is 6 bits.",
                    ),
                    # app_info=ComplexAppInfo(block=Block(
                    #     encoding=BlockEncoding(value="BINARY"),
                    #     length=BlockLength(value=6184),
                    #     occurence=BlockOccurrence(value="unbounded")
                    # ))
                ),
                complex_type=ComplexType(
                    sequence=Sequence(
                        elements=[
                            Element(
                                name="dataWord",
                                type="xs:unsignedByte",
                                min_occurs="4",
                                max_occurs="4",
                                annotation=Annotation(
                                    documentation=Documentation(
                                        lang="en", value="Each data word is 6 bits."
                                    ),
                                    app_info=AppInfo(
                                        block=Block(
                                            encoding=BlockEncoding(value="BINARY"),
                                            length=BlockLength(unit="bit", value=6),
                                            occurence=BlockOccurrence(value="4"),
                                        )
                                    ),
                                ),
                            )
                        ]
                    )
                ),
            )
        ]
        minor_frame_element_1 = [
            Element(
                name="minorFrame",
                type="minorFrameType",
                min_occurs="256",
                max_occurs="256",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value="The Minor Frame is 24 bytes long and represents 8 pixels, with 4 bands data words each. Each MESSR data word is 6 bits.",
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=24),
                            occurence=BlockOccurrence(value="256"),
                        )
                    ),
                ),
            )
        ]
        complex_type = [
            ComplexType(
                name="measurementType",
                sequence=Sequence(elements=measurement_complex_element),
            ),
            ComplexType(name="lineType", sequence=Sequence(elements=line_complex_element)),
            ComplexType(name="videoLineType", sequence=Sequence(elements=minor_frame_element_1)),
            ComplexType(
                name="minorFrameType",
                sequence=Sequence(elements=minor_frame_complex_element),
            ),
        ]

        documentation = Documentation(
            lang="en",
            value='A SAFE product generated with MOS-1 MESSR data includes one Measurement Data Object file, containing the data corresponding to one imaging sequence and one PCD or Telemetry Data file, containing the TLM bits extracted from the original x-band data stream. The Measurement Data Object file contains several Data Units. The Data Unit represents a swath of the MESSR instrument (Multispectra Electronic Self-Scanning Radiometer), mounted on the MOS-1 platform. It comprises all the four spectral bands. Each Data Unit (fixed length, 6184 bytes long) contains annotations (40 bytes) and measurement data (6144 bytes). The Measurement Data file is divided in Data Units ("lines"), arranged sequentially.',
        )
        element = Element(
            name="measurement",
            type="measurementType",
            annotation=Annotation(documentation=documentation),
        )
        super().__init__(
            include=Include(schema_location="mos-object-types.xsd"),
            element=element,
            complex_type=complex_type,
            # version=version, sip_creator=sip_creator, sip_creation_time=sip_creation_time,
            **data,
        )


if __name__ == "__main__":
    parent_instance = Schema(
        target_namespace="http://www.esa.int/safe/1.2/mos",
        xmlns="http://www.esa.int/safe/1.2/mos",
        # version="2.0", sip_creator="ESA", sip_creation_time=datetime(2021, 2, 3)
    )

    xml = parent_instance.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")

    print(xml)
