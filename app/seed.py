from app.models.user import USER_ROLES, User
from app.services.preferences import mark_installed, mark_uninstalled
from app.services.user import create_user

SEED_PASSWORD = "Password123456!!"


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

        mark_installed()

    @app.cli.command("uninstall")
    def uninstall():
        mark_uninstalled()
        print("Instance marked as not installed. The next request will be")
        print("redirected to /install.")
