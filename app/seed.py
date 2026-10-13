from datetime import datetime, time, timedelta, timezone

from app import db
from app.models.booking import Booking
from app.models.room import Feature, Room
from app.models.user import USER_ROLES, User
from app.services.feature import create_feature
from app.services.preferences import mark_installed, mark_uninstalled
from app.services.room import create_room
from app.services.user import create_user

SEED_PASSWORD = "Password123456!!"


def _prior_weekday(start_date, n):
    d = start_date
    count = 0
    while count < n:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def _next_weekday(start_date, n):
    d = start_date
    count = 0
    while count < n:
        d += timedelta(days=1)
        if d.weekday() < 5:
            count += 1
    return d


def _seed_users():
    return [
        {
            "username": role.lower(),
            "display_name": f"John {role.title()}",
            "email": f"{role.lower()}@uni.su",
            "role": role,
            "password": SEED_PASSWORD,
        }
        for role in USER_ROLES
    ]


def _seed_rooms():
    return [
        {
            "code": "PC0",
            "location": "Building I, Ground Floor",
            "capacity": 30,
            "feature_ids": [],
        },
        {
            "code": "I1",
            "location": "Building I, Ground Floor",
            "capacity": 60,
            "feature_ids": [],
        },
        {
            "code": "IK1",
            "location": "Building I, 10th Floor",
            "capacity": 150,
            "feature_ids": [],
        },
    ]


def _seed_features():
    return [
        {"name": "Projector", "description": "Ceiling-mounted projector"},
        {"name": "Whiteboard", "description": "Wall-mounted whiteboard"},
        {"name": "Video Conference", "description": "Camera and conferencing setup"},
    ]


def register_seed_command(app):
    @app.cli.command("seed")
    def seed():
        seed_users = _seed_users()
        created = []

        for data in seed_users:
            if User.query.filter_by(username=data["username"]).first() is not None:
                continue
            create_user(data)
            created.append(data)

        if created:
            print("Created users:")
            for data in created:
                print(f"  {data['username']} / {data['password']}")
        else:
            print("No new users created, all seed users already exist.")

        print("\nSeed accounts:")
        for data in seed_users:
            print(f"  {data['username']} / {data['password']}")

        seed_rooms = _seed_rooms()
        created_rooms = []
        for data in seed_rooms:
            if Room.query.filter_by(code=data["code"]).first() is not None:
                continue
            create_room(data)
            created_rooms.append(data)

        if created_rooms:
            print("\nCreated rooms:")
            for data in created_rooms:
                print(f"  {data['code']}")
        else:
            print("\nNo new rooms created, all seed rooms already exist.")

        seed_features = _seed_features()
        created_features = []
        for data in seed_features:
            if Feature.query.filter_by(name=data["name"]).first() is not None:
                continue
            create_feature(data)
            created_features.append(data)

        if created_features:
            print("\nCreated features:")
            for data in created_features:
                print(f"  {data['name']}")
        else:
            print("\nNo new features created, all seed features already exist.")

        room = Room.query.filter_by(code="IK1").first()
        if room is not None and Booking.query.filter_by(room_id=room.id).count() == 0:
            requester = User.query.filter_by(username="requester").first()
            admin = User.query.filter_by(username="admin").first()
            operator = User.query.filter_by(username="operator").first()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            today = now.date()

            def at(date_, hour, minute=0):
                return datetime.combine(date_, time(hour, minute))

            bookings = [
                Booking(
                    start_date=at(_prior_weekday(today, 1), 10),
                    end_date=at(_prior_weekday(today, 1), 10, 45),
                    state="FINISHED",
                    requester_id=requester.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=at(_prior_weekday(today, 2), 14),
                    end_date=at(_prior_weekday(today, 2), 15, 30),
                    state="FINISHED",
                    requester_id=admin.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=at(_prior_weekday(today, 3), 9),
                    end_date=at(_prior_weekday(today, 3), 9, 45),
                    state="NO_SHOW",
                    requester_id=requester.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=at(today, 6),
                    end_date=at(today, 7, 30),
                    state="NO_SHOW",
                    requester_id=admin.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=now - timedelta(minutes=45),
                    end_date=now + timedelta(minutes=45),
                    state="ACTIVE",
                    requester_id=requester.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=now + timedelta(hours=2),
                    end_date=now + timedelta(hours=2, minutes=45),
                    state="PENDING",
                    requester_id=requester.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=at(_next_weekday(today, 1), 10),
                    end_date=at(_next_weekday(today, 1), 11, 30),
                    state="PENDING",
                    requester_id=admin.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=at(_next_weekday(today, 2), 14),
                    end_date=at(_next_weekday(today, 2), 16, 15),
                    state="PENDING",
                    requester_id=operator.id,
                    room_id=room.id,
                ),
                Booking(
                    start_date=at(_next_weekday(today, 3), 9),
                    end_date=at(_next_weekday(today, 3), 9, 45),
                    state="PENDING",
                    requester_id=requester.id,
                    room_id=room.id,
                ),
            ]
            db.session.add_all(bookings)
            db.session.commit()
            print("\nSeeded showcase bookings on room IK1.")
        else:
            print(
                "\nNo new bookings seeded (room IK1 missing or already has bookings)."
            )

        mark_installed()

    @app.cli.command("uninstall")
    def uninstall():
        mark_uninstalled()
        print("Instance marked as not installed. The next request will be")
        print("redirected to /install.")

    @app.cli.command("clear-all")
    def clear_all():
        db.drop_all()
        db.create_all()
        print("All data cleared from database.")
