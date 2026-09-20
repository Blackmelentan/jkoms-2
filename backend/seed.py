"""
One-shot local seed script — creates an admin account, the six network
locations, per-mode rates, a couple of demo clients, and a couple of demo
shipments, so the database has something in it that lines up with what the
frontend prototypes already show as mock data.

Run once after `init_db()` (or `alembic upgrade head`):

    python seed.py

Safe to re-run — it checks for existing rows by unique field before
inserting anything.
"""

import asyncio

from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import select

from app.database import engine
from app.models import (
    Profile, UserRole, Location, LocationType, Rate, TransportMode,
    Client, Shipment, ShipmentStage, JourneyEvent, JourneyEventMethod,
)
from app.security import hash_password


async def seed():
    async with AsyncSession(engine) as session:

        # --- Admin account ---
        existing_admin = (await session.exec(select(Profile).where(Profile.email == "admin@jkomsglobal.com"))).first()
        if not existing_admin:
            admin = Profile(
                email="admin@jkomsglobal.com",
                hashed_password=hash_password("ChangeMe123!"),
                full_name="Operations Admin",
                role=UserRole.admin,
                must_change_password=True,
            )
            session.add(admin)
            await session.flush()
            print("Created admin@jkomsglobal.com / ChangeMe123! (forced password change on first login)")
        else:
            admin = existing_admin
            print("Admin account already exists — skipping.")

        # --- Locations (matches the network shown across all four prototypes) ---
        location_defs = [
            ("Edinburgh Warehouse", "EDI-WH", LocationType.depot, "United Kingdom"),
            ("London Collection Point", "LON-CP", LocationType.collection_point, "United Kingdom"),
            ("Banjul Depot", "BJL-DEPOT", LocationType.depot, "The Gambia"),
            ("Accra Collection Point", "ACC-CP", LocationType.collection_point, "Ghana"),
            ("Lagos Collection Point", "LOS-CP", LocationType.collection_point, "Nigeria"),
            ("Dubai Depot", "DXB-DEPOT", LocationType.depot, "United Arab Emirates"),
        ]
        locations = {}
        for name, code, ltype, country in location_defs:
            existing = (await session.exec(select(Location).where(Location.code == code))).first()
            if not existing:
                existing = Location(name=name, code=code, type=ltype, country=country)
                session.add(existing)
                await session.flush()
            locations[code] = existing
        print(f"Locations ready: {', '.join(l.name for l in locations.values())}")

        # --- Rates (matches the AQE Quote Engine defaults in rates.py) ---
        rate_defs = [
            ("Ocean Freight", TransportMode.sea, 1.85),
            ("Air Cargo", TransportMode.air, 4.20),
            ("Road Freight / RORO", TransportMode.road, 2.10),
        ]
        for service_type, mode, per_kg in rate_defs:
            existing = (await session.exec(
                select(Rate).where(Rate.service_type == service_type, Rate.transport_mode == mode)
            )).first()
            if not existing:
                session.add(Rate(service_type=service_type, transport_mode=mode, price_per_kg=per_kg, currency="GBP"))
        print("Rates ready: Ocean £1.85/kg, Air £4.20/kg, Road £2.10/kg")

        # --- Demo clients (business records — no login of their own by default) ---
        client_defs = [
            ("Amara Distribution", "+2207712245", "amara@example.com"),
            ("Binta Jallow", "+447700900123", None),
        ]
        clients = []
        for name, phone, email in client_defs:
            existing = (await session.exec(select(Client).where(Client.full_name == name))).first()
            if not existing:
                existing = Client(client_code=f"JKC-{1000+len(clients)}", full_name=name, phone=phone, email=email)
                session.add(existing)
                await session.flush()
            clients.append(existing)
        print(f"Clients ready: {', '.join(c.full_name for c in clients)}")

        # --- A client WITH a portal login, for testing the Client Portal ---
        # This is what actually exercises the Profile <-> Client link that
        # get_own_client_id() resolves — every 'my shipments/bookings/
        # invoices' filter depends on this row existing.
        existing_client_login = (await session.exec(select(Profile).where(Profile.email == "amara@example.com"))).first()
        if not existing_client_login:
            client_login = Profile(
                email="amara@example.com",
                hashed_password=hash_password("ClientDemo123!"),
                full_name="Amara Distribution",
                role=UserRole.client,
                must_change_password=True,
            )
            session.add(client_login)
            await session.flush()
            amara_client = next(c for c in clients if c.full_name == "Amara Distribution")
            amara_client.profile_id = client_login.id
            session.add(amara_client)
            print("Created client login amara@example.com / ClientDemo123! (linked to Amara Distribution)")
        else:
            print("Client login amara@example.com already exists — skipping.")

        # --- A courier login, for testing JKOMS Field's "My Jobs" ---
        existing_courier = (await session.exec(select(Profile).where(Profile.email == "musa@jkomsglobal.com"))).first()
        if not existing_courier:
            courier = Profile(
                email="musa@jkomsglobal.com",
                hashed_password=hash_password("CourierDemo123!"),
                full_name="Musa Jallow",
                role=UserRole.courier,
                location_id=locations["EDI-WH"].id,
                must_change_password=True,
            )
            session.add(courier)
            await session.flush()
            print("Created courier login musa@jkomsglobal.com / CourierDemo123! (Edinburgh Warehouse)")
        else:
            courier = existing_courier
            print("Courier login musa@jkomsglobal.com already exists — skipping.")

        # --- Demo shipment, so GET /shipments returns something on a fresh DB ---
        existing_shipment = (await session.exec(select(Shipment).where(Shipment.tracking_code == "JKG-DEMO-000001"))).first()
        if not existing_shipment:
            shipment = Shipment(
                tracking_code="JKG-DEMO-000001",
                qr_payload="JKG-DEMO-000001",
                client_id=clients[0].id,
                sender_name=clients[0].full_name,
                sender_address="12 Leith Walk, Edinburgh, UK",
                recipient_name="Kaddy Touray",
                recipient_phone="+2207712345",
                recipient_address="Bakau, The Gambia",
                origin_location_id=locations["EDI-WH"].id,
                destination_location_id=locations["BJL-DEPOT"].id,
                current_stage=ShipmentStage.transit,
                service_level="Ocean · FCL",
                weight_kg=840,
                assigned_courier_id=courier.id,
                created_by=admin.id,
            )
            session.add(shipment)
            await session.flush()
            session.add(JourneyEvent(
                shipment_id=shipment.id, stage=ShipmentStage.booking,
                method=JourneyEventMethod.system, recorded_by=admin.id,
            ))
            session.add(JourneyEvent(
                shipment_id=shipment.id, stage=ShipmentStage.transit,
                method=JourneyEventMethod.manual, recorded_by=admin.id,
                location_id=locations["EDI-WH"].id,
            ))
            print("Demo shipment JKG-DEMO-000001 created (Edinburgh → Banjul, in transit)")

        await session.commit()
        print("\nSeed complete.")
        print("Staff login:   admin@jkomsglobal.com / ChangeMe123!")
        print("Client login:  amara@example.com / ClientDemo123!")
        print("Courier login: musa@jkomsglobal.com / CourierDemo123!")


if __name__ == "__main__":
    asyncio.run(seed())
