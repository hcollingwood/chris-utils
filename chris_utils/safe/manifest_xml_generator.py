import hashlib
import logging
from typing import Optional

from pydantic_xml import BaseXmlModel, attr, element

namespaces = {
    "xfdu": "urn:ccsds:schema:xfdu:1",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
    "": "",
}

file_info = {
    "xsd": ("SAFE Restriction to XFDU Schema", None, "xmlBaseSchema"),
    "measurement": ("Measurement Data", "measurementData", "measurementSchema"),
}


class Checksum(BaseXmlModel, tag="checksum"):
    checksum_name: str = attr(name="checksumName")
    value: str = element


class FileLocation(BaseXmlModel, tag="fileLocation"):
    locator_type: str = attr(name="locatorType")
    text_info: str = attr(name="textInfo")
    href: str = attr(name="href")


class ByteStream(BaseXmlModel, tag="byteStream"):
    mime_type: str = attr(name="mimeType")
    file_location: FileLocation
    checksum: Checksum


class DataObject(BaseXmlModel, tag="dataObject"):
    data_object_id: str = attr(name="ID")
    rep_id: str = attr(name="repID")
    byte_stream: ByteStream


class DataObjectSection(BaseXmlModel, tag="dataObjectSection", ns=""):
    data_objects: list[DataObject]


class MetadataReference(BaseXmlModel, tag="metadataReference", ns=""):
    locator_type: str = attr(name="locatorType")
    href: str = attr(ns=None)
    vocabulary_name: str = attr(name="vocabularyName")
    mime_type: str = attr(name="mimeType")


class MetadataObject(BaseXmlModel, tag="metadataObject", ns=""):
    object_id: str = attr(name="ID")
    classification: str = attr(ns=None)
    category: str = attr(ns=None)
    metadata_reference: MetadataReference


class MetadataSection(BaseXmlModel, tag="metadataSection", ns=""):
    metadata_objects: list[MetadataObject]


class DataObjectPointer(BaseXmlModel, tag="dataObjectPointer", ns=""):
    data_object_id: str = attr(name="dataObjectID")


class ContentUnitInner(BaseXmlModel, tag="contentUnit", ns="xfdu", nsmap=namespaces):
    unit_type: str = attr(name="unitType")
    id_content_unit: str = attr(name="ID")
    rep_id: str = attr(name="repID")
    data_object_pointer: Optional[DataObjectPointer] = element(default=None)


class ContentUnitOuter(BaseXmlModel, tag="contentUnit", ns="xfdu", nsmap=namespaces):
    unit_type: str = attr(name="unitType")
    text_info: str = attr(name="textInfo")
    id_content_unit: str = attr(name="ID")
    dmd_id: str = attr(name="dmdID")
    pdi_id: str = attr(name="pdiID")
    content_unit: list[ContentUnitInner]


class InformationPackageMap(BaseXmlModel, tag="informationPackageMap", ns=""):
    content_unit: ContentUnitOuter


def calculate_md5_checksum(file_path: str):
    with open(file_path, "rb") as f:
        data = f.read()
        return hashlib.md5(data).hexdigest()


class XFDU(BaseXmlModel, nsmap=namespaces, ns="xfdu"):
    version: str = attr(value="esa/safe/2.0")
    schema_location: str = attr(name="schemaLocation", ns="xsi")
    information_package_map: InformationPackageMap
    metadata_section: MetadataSection
    data_object_section: DataObjectSection

    def __init__(self, data_objects=None, **data):
        version = "esa/safe/2.0"
        schema_location = "urn:ccsds:schema:xfdu:1 xfdu.xsd"
        file_id = "CHRIS"
        rep_id = f"{file_id}BaseSchema"

        data_object_pointer = DataObjectPointer(data_object_id=file_id)

        data_object_list = []
        if data_objects:
            for data_object in data_objects:
                split_path = data_object.rsplit("/", 2)
                logging.info("/".join(split_path[1:]))
                data_type = split_path[-2]
                file_name = split_path[-1]
                file_extension = file_name.split(".")[-1]

                try:
                    text_info, data_object_id, rep_id = file_info[file_extension]
                except KeyError:
                    text_info, data_object_id, rep_id = file_info["measurement"]
                    data_object_id = f"{data_object_id}{file_extension.title()}"

                if data_object_id is None:
                    data_object_id = f"{file_extension}Schema"

                checksum = Checksum(checksum_name="MD5", value=calculate_md5_checksum(data_object))
                file_location = FileLocation(
                    locator_type="URL",
                    text_info=text_info,
                    href=f"{data_type}/{file_name}",
                )
                byte_stream = ByteStream(
                    mime_type="application/octet-stream",
                    file_location=file_location,
                    checksum=checksum,
                )
                data_object_list.append(
                    DataObject(
                        data_object_id=data_object_id,
                        rep_id=rep_id,
                        byte_stream=byte_stream,
                    )
                )

        content_unit_inner = [
            ContentUnitInner(
                unit_type="CHRIS data unit",
                id_content_unit="measurementUnit",
                rep_id=rep_id,
                data_object_pointer=data_object_pointer,
            )
        ]
        content_unit_outer = ContentUnitOuter(
            unit_type="SAFE Archive Information Package",
            text_info="SAFE Archive Information Package",
            id_content_unit="packageUnit",
            dmd_id="CHRIS sensor class",
            pdi_id="processing packageId",
            content_unit=content_unit_inner,
        )

        metadata_reference = MetadataReference(
            locator_type="OTHER",
            href=f"urn:x-safe:BASE:root",
            vocabulary_name="SAFE",
            mime_type="text/xml",
        )

        metadata_object = MetadataObject(
            object_id=rep_id,
            classification="SYNTAX",
            category="REP",
            metadata_reference=metadata_reference,
        )

        information_package_map = InformationPackageMap(content_unit=content_unit_outer)
        metadata_section = MetadataSection(metadata_objects=[metadata_object])

        data_object_section = DataObjectSection(data_objects=data_object_list)

        super().__init__(
            version=version,
            schema_location=schema_location,
            information_package_map=information_package_map,
            metadata_section=metadata_section,
            data_object_section=data_object_section,
            **data,
        )


if __name__ == "__main__":
    parent_instance = XFDU(file_name="myfile.zip")

    xml = parent_instance.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True, exclude_unset=True
    ).decode("utf-8")

    print(xml)
