import datetime
from typing import Optional

from pydantic_xml import BaseXmlModel, attr, element

namespaces = {
    "sdf": "http://www.gael.fr/2004/12/drb/sdf",
    "xs": "http://www.w3.org/2001/XMLSchema",
    "xml": "http://www.w3.org/XML/1998/namespace",
}


class BlockOccurrence(BaseXmlModel, tag="occurrence", ns="sdf"):
    value: str


class BlockOffset(BaseXmlModel, tag="offset", ns="sdf"):
    value: int


class BlockLength(BaseXmlModel, tag="length", ns="sdf"):
    unit: Optional[str] = attr(default=None)
    value: int


class BlockEncoding(BaseXmlModel, tag="encoding", ns="sdf"):
    value: str


class Block(BaseXmlModel, nsmap=namespaces, tag="block", ns="sdf"):
    encoding: BlockEncoding
    occurence: Optional[BlockOccurrence] = element(default=None)
    offset: Optional[BlockOffset] = element(default=None)
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
    annotation: Annotation
    sequence: Sequence


class Schema(BaseXmlModel, nsmap=namespaces, ns="xs", tag="schema"):
    xmlns: str = attr(default="http://www.esa.int/safe/1.2/mos")
    target_namespace: str = attr(name="targetNamespace", default="http://www.esa.int/safe/1.2/mos")
    complex_type: list[ComplexType]

    def __init__(self, **data):
        timestamp = data["timestamp"]
        year = timestamp.strftime("%Y")
        doy = timestamp.strftime("%j")
        hours = timestamp.strftime("%H")
        minutes = timestamp.strftime("%M")
        seconds = timestamp.strftime("%S")
        fraction_of_second = timestamp.strftime("%f")
        milliseconds, microseconds = [
            int(fraction_of_second[i : i + 3]) for i in range(0, len(fraction_of_second), 3)
        ]

        datetime_sequence_elements = [
            Element(
                name="year",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=year,
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="day",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=doy,
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="hours",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=hours,
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="minutes",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=minutes,
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="seconds",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=seconds,
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="milliseconds",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=str(milliseconds),
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="microseconds",
                type="xs:unsignedInt",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value=str(microseconds),
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            length=BlockLength(value=4),
                        )
                    ),
                ),
            ),
            Element(
                name="satelliteTime",
                type="xs:double",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value="Swath time in milliseconds and part of them from the beginning of the year.",
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"),
                            offset=BlockOffset(value=4),
                            length=BlockLength(value=8),
                        )
                    ),
                ),
            ),
        ]

        complex_type = [
            ComplexType(
                name="auxiliaryDataType",
                annotation=Annotation(
                    documentation=Documentation(
                        lang="en",
                        value="Auxiliary Data Type.",
                    ),
                    app_info=AppInfo(
                        block=Block(
                            encoding=BlockEncoding(value="BINARY"), length=BlockLength(value=40)
                        )
                    ),
                ),
                sequence=Sequence(elements=datetime_sequence_elements),
            ),
        ]

        super().__init__(
            complex_type=complex_type,
            **data,
        )


if __name__ == "__main__":
    parent_instance = Schema(
        timestamp=datetime.datetime(
            year=2020, month=12, day=11, hour=11, minute=10, second=9, microsecond=8007
        )
    )

    xml = parent_instance.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")

    print(xml)
