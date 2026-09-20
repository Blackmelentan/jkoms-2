"""API request/response shapes — kept separate from the table models in
models.py so we never accidentally serialize a hashed_password field back
to the frontend, and so create/update payloads can require a different set
of fields than the full table row does."""

from datetime import datetime, date
from uuid import UUID

from sqlmodel import SQLModel

from app.models import UserRole, BookingStatus, ShipmentStage, JourneyEventMethod, ContainerStatus, TransportMode, InvoiceStatus


# ---- Auth ----
class LoginRequest(SQLModel):
    email: str
    password: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"


class ChangePasswordRequest(SQLModel):
    new_password: str


class ProfileCreate(SQLModel):
    email: str
    password: str
    full_name: str
    role: UserRole
    phone: str | None = None
    location_id: UUID | None = None


class ProfileRead(SQLModel):
    id: UUID
    email: str
    full_name: str
    role: UserRole
    phone: str | None
    location_id: UUID | None
    avatar_url: str | None
    must_change_password: bool
    created_at: datetime


class ProfileUpdate(SQLModel):
    """Every field optional — admin edits only whatever it sends. Deliberately
    excludes email and password: email changes and password resets are
    sensitive enough to deserve their own dedicated flow later rather than
    silently piggybacking on a generic PATCH."""
    full_name: str | None = None
    role: UserRole | None = None
    phone: str | None = None
    location_id: UUID | None = None
    avatar_url: str | None = None


class ProfileUpdate(SQLModel):
    full_name: str | None = None
    phone: str | None = None
    role: UserRole | None = None
    location_id: UUID | None = None
    avatar_url: str | None = None


# ---- Clients ----
class ClientCreate(SQLModel):
    full_name: str
    phone: str | None = None
    email: str | None = None
    home_address: str | None = None
    home_lat: float | None = None
    home_lng: float | None = None


class ClientRead(SQLModel):
    id: UUID
    profile_id: UUID | None
    client_code: str
    full_name: str
    phone: str | None
    email: str | None
    home_address: str | None
    created_at: datetime


# ---- Bookings ----
class BookingCreate(SQLModel):
    client_id: UUID | None = None
    requester_name: str
    requester_phone: str | None = None
    requester_email: str | None = None
    service_type: str
    destination: str
    preferred_date: date | None = None
    notes: str | None = None


class BookingRead(SQLModel):
    id: UUID
    booking_ref: str
    client_id: UUID | None
    requester_name: str
    requester_phone: str | None
    service_type: str
    destination: str
    preferred_date: date | None
    quoted_price: float | None
    quoted_currency: str | None
    status: BookingStatus
    converted_shipment_id: UUID | None
    created_at: datetime


class BookingReview(SQLModel):
    status: BookingStatus
    quoted_price: float | None = None
    quoted_currency: str | None = None


# ---- Shipments ----
class ShipmentCreate(SQLModel):
    client_id: UUID | None = None
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
    origin_location_id: UUID | None = None
    destination_location_id: UUID | None = None
    locker_id: UUID | None = None
    service_level: str = "standard"
    weight_kg: float | None = None
    declared_value: float | None = None
    shipping_fee: float | None = None
    notes: str | None = None
    from_booking_id: UUID | None = None


class ShipmentUpdate(SQLModel):
    """Every field optional — a PATCH shape, not a full replacement. Only the
    fields the caller actually sends get changed; everything else on the
    shipment stays as-is. This is what lets admin/staff go back and correct
    a package's weight, a vehicle's details, an address typo, etc. after
    the shipment was already created — creation alone was never going to be
    the last word on a shipment's details."""
    sender_name: str | None = None
    sender_phone: str | None = None
    sender_address: str | None = None
    recipient_name: str | None = None
    recipient_phone: str | None = None
    recipient_address: str | None = None
    origin_location_id: UUID | None = None
    destination_location_id: UUID | None = None
    service_level: str | None = None
    weight_kg: float | None = None
    declared_value: float | None = None
    shipping_fee: float | None = None
    notes: str | None = None


class ShipmentRead(SQLModel):
    id: UUID
    tracking_code: str
    qr_payload: str
    client_id: UUID | None
    sender_name: str
    sender_phone: str | None
    sender_address: str
    recipient_name: str
    recipient_phone: str
    recipient_address: str
    origin_location_id: UUID | None
    destination_location_id: UUID | None
    assigned_courier_id: UUID | None
    locker_id: UUID | None
    current_stage: ShipmentStage
    service_level: str
    weight_kg: float | None
    declared_value: float | None
    shipping_fee: float | None
    client_accepted: bool
    client_accepted_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ShipmentStageUpdate(SQLModel):
    stage: ShipmentStage
    method: JourneyEventMethod = JourneyEventMethod.manual
    location_id: UUID | None = None
    carrier_name: str | None = None
    vehicle_ref: str | None = None
    lat: float | None = None
    lng: float | None = None
    notes: str | None = None


class CourierAssignRequest(SQLModel):
    courier_id: UUID | None


# ---- Journey events ----
class JourneyEventRead(SQLModel):
    id: UUID
    shipment_id: UUID
    stage: ShipmentStage
    location_id: UUID | None
    recorded_by: UUID | None
    method: JourneyEventMethod
    carrier_name: str | None
    vehicle_ref: str | None
    photo_url: str | None
    signature_url: str | None
    notes: str | None
    occurred_at: datetime


# ---- Containers ----
class ContainerCreate(SQLModel):
    container_number: str
    seal_number: str | None = None
    transport_mode: TransportMode = TransportMode.sea
    carrier_name: str | None = None
    destination_port: str | None = None
    capacity_cbm: float | None = None
    closing_at: datetime | None = None
    notes: str | None = None


class ContainerRead(SQLModel):
    id: UUID
    container_number: str
    seal_number: str | None
    transport_mode: TransportMode
    carrier_name: str | None
    destination_port: str | None
    capacity_cbm: float | None
    fill_pct: float | None
    status: ContainerStatus
    closing_at: datetime | None
    departed_at: datetime | None
    arrived_at: datetime | None
    created_at: datetime


class ContainerStatusUpdate(SQLModel):
    status: ContainerStatus


# ---- Locations ----
class LocationCreate(SQLModel):
    name: str
    code: str
    type: str
    address: str | None = None
    country: str | None = None
    lat: float | None = None
    lng: float | None = None


class LocationRead(SQLModel):
    id: UUID
    name: str
    code: str
    type: str
    address: str | None
    country: str | None


# ---- Rates / AQE Quote Engine ----
class RateCreate(SQLModel):
    service_type: str
    origin_location_id: UUID | None = None
    destination_location_id: UUID | None = None
    transport_mode: TransportMode | None = None
    price_per_kg: float | None = None
    base_fee: float | None = None
    currency: str = "GBP"


class RateRead(SQLModel):
    id: UUID
    service_type: str
    origin_location_id: UUID | None
    destination_location_id: UUID | None
    transport_mode: TransportMode | None
    price_per_kg: float | None
    base_fee: float | None
    currency: str
    active: bool


class QuoteRequest(SQLModel):
    """What the public website's AQE Quote Engine form submits. destination_country
    is matched loosely against active rates / a country->duty% table rather than
    requiring an exact location_id, since a website visitor is picking a country
    from a dropdown, not a depot."""
    origin: str
    destination_country: str
    transport_mode: TransportMode
    cargo_category: str
    weight_kg: float
    add_insurance: bool = False
    declared_value: float | None = None


class QuoteResponse(SQLModel):
    quote_ref: str
    transport_mode: TransportMode
    price_per_kg: float
    freight_cost: float
    duty_pct: float
    duty_estimate: float
    insurance_estimate: float
    total_estimate: float
    currency: str = "GBP"


# ---- Invoices ----
class InvoiceCreate(SQLModel):
    shipment_id: UUID | None = None
    client_id: UUID | None = None
    amount: float
    currency: str = "GBP"
    due_at: datetime | None = None


class InvoiceRead(SQLModel):
    id: UUID
    invoice_number: str
    shipment_id: UUID | None
    client_id: UUID | None
    amount: float
    currency: str
    status: InvoiceStatus
    issued_at: datetime
    due_at: datetime | None


# ---- Payments ----
class PaymentCreate(SQLModel):
    invoice_id: UUID
    amount: float
    currency: str = "GBP"
    method: str  # "online_card" | "online_transfer" | "cash" | "in_person_card"
    notes: str | None = None


class PaymentRead(SQLModel):
    id: UUID
    invoice_id: UUID
    amount: float
    currency: str
    method: str | None
    paid_at: datetime
    recorded_by: UUID | None
    notes: str | None


# ---- Documents ----
class DocumentCreate(SQLModel):
    related_type: str
    related_id: UUID
    doc_type: str
    file_url: str


class DocumentRead(SQLModel):
    id: UUID
    related_type: str
    related_id: UUID
    doc_type: str
    file_url: str
    uploaded_by: UUID | None
    created_at: datetime


# ---- Notifications ----
class NotificationCreate(SQLModel):
    shipment_id: UUID | None = None
    recipient_phone: str | None = None
    channel: str  # "sms" | "whatsapp" | "email"
    message: str


class NotificationRead(SQLModel):
    id: UUID
    shipment_id: UUID | None
    recipient_phone: str | None
    channel: str
    message: str
    status: str
    sent_at: datetime


# ---- Audit log ----
class AuditLogRead(SQLModel):
    id: UUID
    actor_name: str
    action: str
    entity_type: str
    entity_id: UUID | None
    details: str
    created_at: datetime
