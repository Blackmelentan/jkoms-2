"""
Database models — Phase 1 of the JKOMS Master Ecosystem Blueprint.

Two things worth calling out:

1. journey_events is the single unified log for everything that happens to
   a shipment — barcode scans, staff-logged freight steps, status changes,
   all of it, distinguished only by `method`. This directly replaces the
   old split between scan_events and shipment_legs that was causing the
   double-entry risk in the previous build.

2. clients is separate from profiles. A client doesn't need a login to be
   a sender/recipient on a shipment — profile_id is nullable and only gets
   set once/if that person actually creates a portal account.
"""

from datetime import datetime, date
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import Column, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlmodel import SQLModel, Field


def _uuid_pk() -> Field:
    return Field(default_factory=uuid4, sa_column=Column(PGUUID(as_uuid=True), primary_key=True))


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class UserRole(str, Enum):
    admin = "admin"
    chairman = "chairman"
    supervisor = "supervisor"
    hr = "hr"
    depot_staff = "depot_staff"
    customs_finance = "customs_finance"
    courier = "courier"
    client = "client"


class LocationType(str, Enum):
    depot = "depot"
    port = "port"
    locker_hub = "locker_hub"
    collection_point = "collection_point"


class TransportMode(str, Enum):
    road = "road"
    air = "air"
    sea = "sea"


class BookingStatus(str, Enum):
    new = "new"
    quoted = "quoted"
    confirmed = "confirmed"
    converted = "converted"
    declined = "declined"


class ShipmentStage(str, Enum):
    booking = "booking"
    collection = "collection"
    warehouse_intake = "warehouse_intake"
    consolidation = "consolidation"
    transit = "transit"
    customs = "customs"
    last_mile = "last_mile"
    delivered = "delivered"
    closed = "closed"
    exception = "exception"


class JourneyEventMethod(str, Enum):
    camera_scan = "camera_scan"
    hid_scanner = "hid_scanner"
    manual = "manual"
    system = "system"


class ContainerStatus(str, Enum):
    building = "building"
    ready = "ready"
    departed = "departed"
    arrived = "arrived"
    cleared = "cleared"


class LockerStatus(str, Enum):
    empty = "empty"
    occupied = "occupied"
    overdue = "overdue"


class InvoiceStatus(str, Enum):
    unpaid = "unpaid"
    partial = "partial"
    paid = "paid"
    void = "void"


class NotificationChannel(str, Enum):
    sms = "sms"
    whatsapp = "whatsapp"
    email = "email"


class NotificationStatus(str, Enum):
    sent = "sent"
    failed = "failed"


# ---------------------------------------------------------------------------
# Core tables
# ---------------------------------------------------------------------------
class Location(SQLModel, table=True):
    __tablename__ = "locations"

    id: UUID = _uuid_pk()
    name: str
    code: str = Field(unique=True, index=True)
    type: LocationType = Field(sa_column=Column(SAEnum(LocationType, name="location_type")))
    address: str | None = None
    country: str | None = None
    lat: float | None = None
    lng: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Profile(SQLModel, table=True):
    __tablename__ = "profiles"

    id: UUID = _uuid_pk()
    email: str = Field(unique=True, index=True)
    hashed_password: str
    full_name: str = ""
    role: UserRole = Field(sa_column=Column(SAEnum(UserRole, name="user_role")))
    phone: str | None = None
    location_id: UUID | None = Field(default=None, foreign_key="locations.id")
    avatar_url: str | None = None
    must_change_password: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Client(SQLModel, table=True):
    __tablename__ = "clients"

    id: UUID = _uuid_pk()
    profile_id: UUID | None = Field(default=None, foreign_key="profiles.id", unique=True)
    client_code: str = Field(unique=True, index=True)
    full_name: str
    phone: str | None = None
    email: str | None = None
    home_address: str | None = None
    home_lat: float | None = None
    home_lng: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Rate(SQLModel, table=True):
    __tablename__ = "rates"

    id: UUID = _uuid_pk()
    service_type: str  # e.g. "Ocean Freight", "Air Cargo", "RORO", "Door to Door"
    origin_location_id: UUID | None = Field(default=None, foreign_key="locations.id")
    destination_location_id: UUID | None = Field(default=None, foreign_key="locations.id")
    transport_mode: TransportMode | None = Field(default=None, sa_column=Column(SAEnum(TransportMode, name="transport_mode")))
    price_per_kg: float | None = None
    base_fee: float | None = None
    currency: str = "GBP"
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Booking(SQLModel, table=True):
    __tablename__ = "bookings"

    id: UUID = _uuid_pk()
    booking_ref: str = Field(unique=True, index=True)
    client_id: UUID | None = Field(default=None, foreign_key="clients.id")
    requester_name: str
    requester_phone: str | None = None
    requester_email: str | None = None
    service_type: str
    destination: str
    preferred_date: date | None = None
    quoted_price: float | None = None
    quoted_currency: str | None = None
    notes: str | None = None
    status: BookingStatus = Field(default=BookingStatus.new, sa_column=Column(SAEnum(BookingStatus, name="booking_status")))
    reviewed_by: UUID | None = Field(default=None, foreign_key="profiles.id")
    reviewed_at: datetime | None = None
    converted_shipment_id: UUID | None = Field(default=None, foreign_key="shipments.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Shipment(SQLModel, table=True):
    __tablename__ = "shipments"

    id: UUID = _uuid_pk()
    tracking_code: str = Field(unique=True, index=True)
    qr_payload: str

    client_id: UUID | None = Field(default=None, foreign_key="clients.id")

    sender_name: str
    sender_phone: str | None = None
    sender_address: str
    sender_lat: float | None = None
    sender_lng: float | None = None

    recipient_name: str
    recipient_phone: str
    recipient_address: str
    recipient_lat: float | None = None
    recipient_lng: float | None = None

    origin_location_id: UUID | None = Field(default=None, foreign_key="locations.id")
    destination_location_id: UUID | None = Field(default=None, foreign_key="locations.id")
    assigned_courier_id: UUID | None = Field(default=None, foreign_key="profiles.id")
    locker_id: UUID | None = Field(default=None, foreign_key="lockers.id")

    current_stage: ShipmentStage = Field(default=ShipmentStage.booking, sa_column=Column(SAEnum(ShipmentStage, name="shipment_stage")))
    service_level: str = "standard"
    weight_kg: float | None = None
    declared_value: float | None = None
    shipping_fee: float | None = None
    notes: str | None = None

    client_accepted: bool = False
    client_accepted_at: datetime | None = None

    created_by: UUID | None = Field(default=None, foreign_key="profiles.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ShipmentItem(SQLModel, table=True):
    """Itemized customs contents — category/description/qty/price per line."""
    __tablename__ = "shipment_items"

    id: UUID = _uuid_pk()
    shipment_id: UUID = Field(foreign_key="shipments.id")
    category: str
    description: str
    quantity: int = 1
    unit_price: float | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class JourneyEvent(SQLModel, table=True):
    """The unified append-only log — every scan and every manually logged
    freight step lives here, in one place, distinguished by `method`."""
    __tablename__ = "journey_events"

    id: UUID = _uuid_pk()
    shipment_id: UUID = Field(foreign_key="shipments.id", index=True)
    stage: ShipmentStage = Field(sa_column=Column(SAEnum(ShipmentStage, name="journey_stage")))
    location_id: UUID | None = Field(default=None, foreign_key="locations.id")
    recorded_by: UUID | None = Field(default=None, foreign_key="profiles.id")
    method: JourneyEventMethod = Field(sa_column=Column(SAEnum(JourneyEventMethod, name="journey_method")))
    carrier_name: str | None = None
    vehicle_ref: str | None = None
    photo_url: str | None = None
    signature_url: str | None = None
    lat: float | None = None
    lng: float | None = None
    notes: str | None = None
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class Container(SQLModel, table=True):
    __tablename__ = "containers"

    id: UUID = _uuid_pk()
    container_number: str = Field(unique=True, index=True)
    seal_number: str | None = None
    transport_mode: TransportMode = Field(default=TransportMode.sea, sa_column=Column(SAEnum(TransportMode, name="container_transport_mode")))
    carrier_name: str | None = None
    destination_port: str | None = None
    capacity_cbm: float | None = None
    fill_pct: float | None = None
    status: ContainerStatus = Field(default=ContainerStatus.building, sa_column=Column(SAEnum(ContainerStatus, name="container_status")))
    closing_at: datetime | None = None
    departed_at: datetime | None = None
    arrived_at: datetime | None = None
    notes: str | None = None
    created_by: UUID | None = Field(default=None, foreign_key="profiles.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContainerShipment(SQLModel, table=True):
    __tablename__ = "container_shipments"

    container_id: UUID = Field(foreign_key="containers.id", primary_key=True)
    shipment_id: UUID = Field(foreign_key="shipments.id", primary_key=True)


class Locker(SQLModel, table=True):
    __tablename__ = "lockers"

    id: UUID = _uuid_pk()
    code: str = Field(unique=True, index=True)
    label: str
    address: str
    country: str = "United Kingdom"
    status: LockerStatus = Field(default=LockerStatus.empty, sa_column=Column(SAEnum(LockerStatus, name="locker_status")))
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Invoice(SQLModel, table=True):
    __tablename__ = "invoices"

    id: UUID = _uuid_pk()
    invoice_number: str = Field(unique=True, index=True)
    shipment_id: UUID | None = Field(default=None, foreign_key="shipments.id")
    client_id: UUID | None = Field(default=None, foreign_key="clients.id")
    amount: float
    currency: str = "GBP"
    status: InvoiceStatus = Field(default=InvoiceStatus.unpaid, sa_column=Column(SAEnum(InvoiceStatus, name="invoice_status")))
    issued_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Payment(SQLModel, table=True):
    __tablename__ = "payments"

    id: UUID = _uuid_pk()
    invoice_id: UUID = Field(foreign_key="invoices.id")
    amount: float
    currency: str = "GBP"
    method: str | None = None
    paid_at: datetime = Field(default_factory=datetime.utcnow)
    recorded_by: UUID | None = Field(default=None, foreign_key="profiles.id")
    notes: str | None = None


class Document(SQLModel, table=True):
    """Polymorphic attachment — customs manifests, invoice PDFs, ID docs,
    anything else that needs to hang off a shipment/booking/container."""
    __tablename__ = "documents"

    id: UUID = _uuid_pk()
    related_type: str  # "shipment" | "booking" | "container" | "client"
    related_id: UUID
    doc_type: str  # "manifest" | "invoice_pdf" | "pod_photo" | "id_document" | "other"
    file_url: str
    uploaded_by: UUID | None = Field(default=None, foreign_key="profiles.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class NotificationLog(SQLModel, table=True):
    __tablename__ = "notifications_log"

    id: UUID = _uuid_pk()
    shipment_id: UUID | None = Field(default=None, foreign_key="shipments.id")
    recipient_phone: str | None = None
    channel: NotificationChannel = Field(sa_column=Column(SAEnum(NotificationChannel, name="notification_channel")))
    message: str
    status: NotificationStatus = Field(sa_column=Column(SAEnum(NotificationStatus, name="notification_status")))
    sent_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(SQLModel, table=True):
    """A generic, append-only record of who changed what. Wired into the
    most sensitive actions first — account creation/edit/delete, shipment
    detail edits, and payments — rather than every single endpoint, so it
    covers the things a real reconciliation or compliance review would
    actually ask about. Extending coverage to more routers later is just
    one call to log_audit() per action, not a redesign."""
    __tablename__ = "audit_log"

    id: UUID = _uuid_pk()
    actor_id: UUID | None = Field(default=None, foreign_key="profiles.id")
    actor_name: str = ""
    action: str  # e.g. "account.create", "shipment.update", "payment.record"
    entity_type: str  # e.g. "profile", "shipment", "payment"
    entity_id: UUID | None = None
    details: str = ""  # short human-readable summary, not a full field diff
    created_at: datetime = Field(default_factory=datetime.utcnow)
