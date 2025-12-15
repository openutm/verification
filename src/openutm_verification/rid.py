from dataclasses import dataclass
from enum import Enum

SpecificSessionID = str


@dataclass
class LatLngPoint:
    lat: float
    lng: float


class Reference1(str, Enum):
    W84 = "W84"


class Units(str, Enum):
    M = "M"


class Category(str, Enum):
    EUCategoryUndefined = "EUCategoryUndefined"
    Open = "Open"
    Specific = "Specific"
    Certified = "Certified"


class Class(str, Enum):
    EUClassUndefined = "EUClassUndefined"
    Class0 = "Class0"
    Class1 = "Class1"
    Class2 = "Class2"
    Class3 = "Class3"
    Class4 = "Class4"
    Class5 = "Class5"
    Class6 = "Class6"


@dataclass
class Altitude:
    value: float
    reference: Reference1
    units: Units


class AltitudeType(Enum):
    Takeoff = "Takeoff"
    Dynamic = "Dynamic"
    Fixed = "Fixed"


@dataclass
class RIDAuthData:
    data: str | None = ""
    format: int | None = 0


@dataclass
class OperatorLocation:
    position: LatLngPoint
    altitude: Altitude | None = None
    altitude_type: AltitudeType | None = None


@dataclass
class UASID:
    specific_session_id: SpecificSessionID | None = None
    serial_number: str | None = ""
    registration_id: str | None = ""
    utm_id: str | None = ""


@dataclass
class UAClassificationEU:
    category: Category | None = Category.EUCategoryUndefined
    class_: Class | None = Class.EUClassUndefined


@dataclass
class RIDOperatorDetails:
    id: str
    eu_classification: UAClassificationEU | None = None
    uas_id: UASID | None = None
    operator_location: OperatorLocation | None = None
    auth_data: RIDAuthData | None = None
    operator_id: str | None = ""
    operation_description: str | None = ""
