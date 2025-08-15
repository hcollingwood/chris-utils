from datetime import datetime

from pydantic_xml import BaseXmlModel, attr, element


namespaces = {
    "sip": "http://www.eo.esa.int/SIP/sipInfo/2.0"
}


class SIPInfo(BaseXmlModel, nsmap=namespaces, ns="sip"):
    version: str = attr(value="2.0")
    sip_creator: str = element(tag="SIPCreator")#, ns='')
    sip_creation_time: datetime = element(tag="SIPCreationTime")#, ns='')


if __name__ == "__main__":
    parent_instance = SIPInfo(
        version="2.0", sip_creator="ESA", sip_creation_time=datetime.now()
    )

    xml = parent_instance.to_xml(
        pretty_print=True, encoding="UTF-8", standalone=True
    ).decode("utf-8")

    print(xml)

    print("complete")
