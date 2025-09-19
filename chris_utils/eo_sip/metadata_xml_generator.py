from datetime import datetime

from pydantic_xml import BaseXmlModel, attr, element

namespaces = {
    "eop": "http://www.opengis.net/eop/2.1",
    "gml": "http://www.opengis.net/gml/3.2",
    "om": "http://www.opengis.net/om/2.0",
    "opt": "http://www.opengis.net/opt/2.1",
    "ows": "http://www.opengis.net/ows/2.0",
    "xlink": "http://www.w3.org/1999/xlink",
    "xsi": "http://www.w3.org/2001/XMLSchema-instance",
}


class SpecificInformation(BaseXmlModel, ns="eop", nsmap=namespaces, tag="SpecificInformation"):
    local_attribute: str = element(tag="localAttribute")
    local_value: str = element(tag="localValue")


class VendorSpecific(BaseXmlModel, ns="eop", nsmap=namespaces, tag="vendorSpecific"):
    specific_information: SpecificInformation

    class Config:
        namespace = "eop"


class EarthObservationMetaData(
    BaseXmlModel, ns="eop", nsmap=namespaces, tag="EarthObservationMetaData"
):
    identifier: str = element(ns="eop")
    acquisition_type: str = element(ns="eop", tag="acquisitionType")
    product_type: str = element(ns="eop", tag="productType")
    status: str = element(ns="eop")
    vendor_specific: list[VendorSpecific]


class Size(BaseXmlModel, ns="eop", tag="size"):
    uom: str = attr(ns=None)
    value: int = element


class RequestMessage(BaseXmlModel, ns="ows", tag="RequestMessage"):
    pass


class ServiceReference(BaseXmlModel, ns="ows", nsmap=namespaces, tag="ServiceReference"):
    href: str = attr(ns="xlink")
    request_message: RequestMessage


class FileName(BaseXmlModel, ns="eop", nsmap=namespaces, tag="fileName"):
    service_reference: ServiceReference


class ProductInformation(BaseXmlModel, ns="eop", nsmap=namespaces, tag="ProductInformation"):
    file_name: FileName
    size: Size = element


class Product(BaseXmlModel, ns="eop", nsmap=namespaces, tag="product"):
    product_information: ProductInformation


class EarthObservationResult(
    BaseXmlModel, ns="opt", nsmap=namespaces, tag="EarthObservationResult"
):
    id: str = attr(ns="gml")
    product: Product


class Pos(BaseXmlModel, nsmap=namespaces, ns="gml"):
    value: str = element


class Point(BaseXmlModel, nsmap=namespaces, ns="gml", tag="Point"):
    id: str = attr(ns="gml")
    pos: Pos


class CenterOf(BaseXmlModel, ns="eop", nsmap=namespaces, tag="centerOf"):
    point: Point


class PosList(BaseXmlModel, ns="gml", nsmap=namespaces, tag="posList"):
    value: str = element


class LinearRing(BaseXmlModel, ns="gml", nsmap=namespaces, tag="LinearRing"):
    pos_list: PosList


class Exterior(BaseXmlModel, nsmap=namespaces, ns="gml"):
    linear_ring: LinearRing


class Polygon(BaseXmlModel, ns="gml", nsmap=namespaces, tag="Polygon"):
    id: str = attr(ns="gml")
    exterior: Exterior


class SurfaceMember(BaseXmlModel, ns="gml", nsmap=namespaces, tag="surfaceMember"):
    polygon: Polygon


class MultiSurface(BaseXmlModel, ns="gml", nsmap=namespaces, tag="MultiSurface"):
    id: str = attr(ns="gml")
    surface_member: SurfaceMember


class MultiExtentOf(BaseXmlModel, ns="eop", nsmap=namespaces, tag="multiExtentOf"):
    multi_surface: MultiSurface


class Footprint(BaseXmlModel, ns="eop", nsmap=namespaces, tag="Footprint"):
    id: str = attr(ns="gml")
    multi_extent_of: MultiExtentOf
    center_of: CenterOf


class IlluminationAngle(BaseXmlModel, nsmap=namespaces, ns="eop"):
    uom: str = attr(ns=None)
    value: float = element


class WrsGrid(BaseXmlModel, nsmap=namespaces, ns="eop"):
    code_space: str = attr(name="codeSpace")
    value: str = element


class Acquisition(BaseXmlModel, ns="eop", nsmap=namespaces, tag="Acquisition"):
    orbit_number: str = element(tag="orbitNumber")
    wrs_longitude_grid: WrsGrid = element(tag="wrsLongitudeGrid")
    wrs_latitude_grid: WrsGrid = element(tag="wrsLatitudeGrid")
    illumination_azimuth_angle: IlluminationAngle = element(tag="illuminationAzimuthAngle")
    illumination_elevation_angle: IlluminationAngle = element(tag="illuminationElevationAngle")


class AcquisitionParameters(BaseXmlModel, ns="eop", nsmap=namespaces, tag="acquisitionParameters"):
    parameters: Acquisition


class SensorOperationalMode(BaseXmlModel, ns="eop", nsmap=namespaces, tag="operationalMode"):
    code_space: str = attr(name="codeSpace")
    value: str = element


class SensorBottom(BaseXmlModel, ns="eop", nsmap=namespaces, tag="Sensor"):
    sensor_type: str = element(ns="eop", tag="sensorType")
    operational_mode: SensorOperationalMode


class SensorTop(BaseXmlModel, ns="eop", nsmap=namespaces, tag="sensor"):
    sensor: SensorBottom


class InstrumentBottom(BaseXmlModel, ns="eop", nsmap=namespaces, tag="Instrument"):
    short_name: str = element(ns="eop", tag="shortName")


class InstrumentTop(BaseXmlModel, ns="eop", nsmap=namespaces, tag="instrument"):
    instrument: InstrumentBottom


class PlatformBottom(BaseXmlModel, ns="eop", nsmap=namespaces, tag="Platform"):
    short_name: str = element(ns="eop", tag="shortName")
    serial_identifier: str = element(ns="eop", tag="serialIdentifier")


class PlatformTop(BaseXmlModel, ns="eop", nsmap=namespaces, tag="platform"):
    platform: PlatformBottom


class EarthObservationEquipment(
    BaseXmlModel, ns="eop", nsmap=namespaces, tag="EarthObservationEquipment"
):
    id: str = attr(ns="gml")
    platform: PlatformTop
    instrument: InstrumentTop
    sensor: SensorTop
    acquisition_parameters: AcquisitionParameters


class TimePosition(BaseXmlModel, ns="gml", nsmap=namespaces, tag="timePosition"):
    position: datetime = element


class BeginPosition(BaseXmlModel, ns="gml", nsmap=namespaces, tag="beginPosition"):
    position: datetime = element


class EndPosition(BaseXmlModel, ns="gml", nsmap=namespaces, tag="endPosition"):
    position: datetime = element


class TimePeriod(BaseXmlModel, ns="gml", nsmap=namespaces, tag="TimePeriod"):
    id: str = attr(ns="gml")
    begin_position: BeginPosition
    end_position: EndPosition


class TimeInstant(BaseXmlModel, ns="gml", nsmap=namespaces, tag="TimeInstant"):
    id: str = attr(ns="gml")
    time_position: TimePosition


class PhenomenonTime(BaseXmlModel, ns="om", nsmap=namespaces, tag="phenomenonTime"):
    time_period: TimePeriod


class ResultTime(BaseXmlModel, ns="om", nsmap=namespaces, tag="resultTime"):
    time_instant: TimeInstant


class Procedure(BaseXmlModel, ns="om", nsmap=namespaces, tag="procedure"):
    earth_observation_equipment: EarthObservationEquipment


class ObservedProperty(BaseXmlModel, ns="om", nsmap=namespaces, tag="observedProperty"):
    nil_reason: str = attr(name="nilReason")
    nil: str = attr(ns="xsi")


class FeatureOfInterest(BaseXmlModel, ns="om", nsmap=namespaces, tag="featureOfInterest"):
    footprint: Footprint


class Result(BaseXmlModel, ns="om", nsmap=namespaces, tag="result"):
    earth_observation_result: EarthObservationResult


class MetaDataProperty(BaseXmlModel, ns="eop", nsmap=namespaces, tag="metaDataProperty"):
    earth_observation_meta_data: EarthObservationMetaData


class EarthObservation(BaseXmlModel, nsmap=namespaces, ns="opt"):
    id: str = attr(ns="gml")
    phenomenon_time: PhenomenonTime
    result_time: ResultTime
    procedure: Procedure
    observed_property: ObservedProperty
    feature_of_interest: FeatureOfInterest
    result: Result
    meta_data_property: MetaDataProperty

    def __init__(self, file_id: str, **data):
        metadata = data["data"]
        begin_position = BeginPosition(position=metadata["timestamp"])
        end_position = EndPosition(position=datetime(year=1970, month=1, day=1))
        time_position = TimePosition(position=datetime(year=1970, month=1, day=1))
        sensor_short_name = "PROBA"
        instrument_short_name = "CHRIS"
        serial_identifier = "1"
        sensor_type = "OPTICAL"
        sensor_code_space = "urn:esa:eop:PROBA:CHRIS:operationalMode"
        operational_mode = f"MODE-{metadata['chris_chris_mode']}"
        orbit_number = "000000*"
        wrs_longitude_grid_code_space = "urn:esa:eop:PROBA:TileColumn"
        wrs_longitude_grid = metadata["formatted_longitude"][0]
        wrs_latitude_grid_code_space = "urn:esa:eop:PROBA:TileRow"
        wrs_latitude_grid = metadata["formatted_latitude"][0]
        uom_deg = "deg"
        illumination_azimuth_angle = metadata["illumination_azimuth_angle"]
        illumination_elevation_angle = metadata["illumination_elevation_angle"]
        # this is the aoi box - leave for now:
        pos_list = "0.43* 112.969 -0.421 112.969 -0.421 113.443 0.43 113.443 0.43 112.969"
        pos = "0.0045000384979* 113.206"  # leave for now
        eo_sip_file_name = f"{file_id}.SIP.ZIP"
        uom_bytes = "bytes"
        file_size = metadata["file_size"]
        acquisition_type = "NOMINAL"
        product_type = data["data"]["product_type"]
        status = "ARCHIVED"
        vendor_specific_data = [  # leave for now
            ("originalName", "CHRIS_PA_151114_1E77_41*"),
            ("siteName", "Punta Alta*"),
            ("targetCode", "PA*"),
        ]

        vendor_specific_list = []
        for key, value in vendor_specific_data:
            vendor_specific_list.append(
                VendorSpecific(
                    specific_information=SpecificInformation(local_attribute=key, local_value=value)
                )
            )

        phenomenon_time = PhenomenonTime(
            time_period=TimePeriod(
                id=f"{file_id}_2", begin_position=begin_position, end_position=end_position
            ),
        )
        result_time = ResultTime(
            time_instant=TimeInstant(id=f"{file_id}_3", time_position=time_position)
        )

        procedure = Procedure(
            earth_observation_equipment=EarthObservationEquipment(
                id=f"{file_id}_4",
                platform=PlatformTop(
                    platform=PlatformBottom(
                        short_name=sensor_short_name,
                        serial_identifier=serial_identifier,
                    )
                ),
                instrument=InstrumentTop(
                    instrument=InstrumentBottom(short_name=instrument_short_name)
                ),
                sensor=SensorTop(
                    sensor=SensorBottom(
                        sensor_type=sensor_type,
                        operational_mode=SensorOperationalMode(
                            code_space=sensor_code_space, value=operational_mode
                        ),
                    )
                ),
                acquisition_parameters=AcquisitionParameters(
                    parameters=Acquisition(
                        orbit_number=orbit_number,
                        wrs_longitude_grid=WrsGrid(
                            code_space=wrs_longitude_grid_code_space,
                            value=wrs_longitude_grid,
                        ),
                        wrs_latitude_grid=WrsGrid(
                            code_space=wrs_latitude_grid_code_space,
                            value=wrs_latitude_grid,
                        ),
                        illumination_azimuth_angle=IlluminationAngle(
                            uom=uom_deg, value=illumination_azimuth_angle
                        ),
                        illumination_elevation_angle=IlluminationAngle(
                            uom=uom_deg, value=illumination_elevation_angle
                        ),
                    )
                ),
            )
        )
        observed_property = ObservedProperty(nil_reason="inapplicable", nil="true")
        feature_of_interest = FeatureOfInterest(
            footprint=Footprint(
                id=f"{file_id}_5",
                multi_extent_of=MultiExtentOf(
                    multi_surface=MultiSurface(
                        id=f"{file_id}_6",
                        surface_member=SurfaceMember(
                            polygon=Polygon(
                                id=f"{file_id}_7",
                                exterior=Exterior(
                                    linear_ring=LinearRing(pos_list=PosList(value=pos_list))
                                ),
                            )
                        ),
                    )
                ),
                center_of=CenterOf(point=Point(id=f"{file_id}_8", pos=Pos(value=pos))),
            )
        )
        result = Result(
            earth_observation_result=EarthObservationResult(
                id=f"{file_id}_9",
                product=Product(
                    product_information=ProductInformation(
                        file_name=FileName(
                            service_reference=ServiceReference(
                                href=eo_sip_file_name, request_message=RequestMessage()
                            )
                        ),
                        size=Size(uom=uom_bytes, value=file_size),
                    )
                ),
            )
        )
        meta_data_property = MetaDataProperty(
            earth_observation_meta_data=EarthObservationMetaData(
                identifier=file_id,
                acquisition_type=acquisition_type,
                product_type=product_type,
                status=status,
                vendor_specific=vendor_specific_list,
            )
        )
        super().__init__(
            id=file_id,
            phenomenon_time=phenomenon_time,
            result_time=result_time,
            procedure=procedure,
            observed_property=observed_property,
            feature_of_interest=feature_of_interest,
            result=result,
            meta_data_property=meta_data_property,
            **data,
        )


if __name__ == "__main__":

    file_id = "PR1_OPER_CHR_MO3_1P_20100328T011431_N01-800_W078-260_0001"
    parent_instance = EarthObservation(file_id=file_id)

    xml = parent_instance.to_xml(pretty_print=False, encoding="UTF-8", standalone=True).decode(
        "utf-8"
    )

    print("complete")
