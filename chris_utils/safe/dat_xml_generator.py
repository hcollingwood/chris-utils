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
    length: Optional[BlockLength] = element(default=None)


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


class Include(BaseXmlModel, tag="include", ns="xs"):
    schema_location: str = attr(name="schemaLocation")


class Schema(BaseXmlModel, nsmap=namespaces, ns="xs", tag="schema"):
    xmlns: str = attr(default="http://www.esa.int/safe/1.2/mos")
    include: Optional[Include] = element(default=None)
    target_namespace: str = attr(name="targetNamespace", default="http://www.esa.int/safe/1.2/mos")
    element: Element
    complex_type: list[ComplexType]


if __name__ == "__main__":
    complex_elements = [
        Element(
            name="pixel",
            type="pixelType",
            min_occurs="0",
            max_occurs="unbounded",
            annotation=Annotation(
                documentation=Documentation(
                    lang="en",
                    value="The file contains binary data in 12-bit pixel values. The raw "
                    "block length for image data varies depending on the band "
                    "configuration—specifically whether it's full or half width, "
                    "and whether it's binned or unbinned.",
                ),
                app_info=AppInfo(
                    block=Block(
                        encoding=BlockEncoding(value="BINARY"),
                        length=BlockLength(value=12),
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
        value="A SAFE product generated with CHRIS PROBA-1 data includes one .dat file, "
        "containing 12-bit pixel values. The data is structured in fixed-length packets, "
        "as defined by PACKETSIZE in the headers. Each packet includes a header containing "
        "synchronization markers, metadata, and checksums, and a block of image data, "
        "where pixels from odd and even channels are interleaved. The raw block length "
        "for image data varies depending on the band configuration—specifically whether "
        "it's full or half width, and whether it's binned or unbinned. These values "
        "represent the number of bytes per channel per line at 12 bits per pixel. The "
        "actual block length is determined by the configuration specified in the .set file "
        "the data corresponding to one imaging sequence along with the corresponding header "
        "data.",
    )
    element = Element(
        name="measurement",
        type="measurementType",
        annotation=Annotation(documentation=documentation),
    )

    parent_instance = Schema(
        element=element,
        complex_type=complex_type,
    )

    xml = parent_instance.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")

    print(xml)
