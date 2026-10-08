NAV_ITEMS = [
    {"slug": "booking", "label": "Booking", "allowed_roles": ("REQUESTER",)},
    {"slug": "key-handling", "label": "Key Handling", "allowed_roles": ("OPERATOR",)},
    {
        "slug": "reports-audit",
        "label": "Reports / Audit",
        "allowed_roles": ("AUDITOR",),
    },
    {
        "slug": "user-management",
        "label": "User Management",
        "allowed_roles": ("ADMIN",),
    },
    {
        "slug": "room-management",
        "label": "Room Management",
        "allowed_roles": ("ADMIN",),
    },
    {
        "slug": "key-management",
        "label": "Key Management",
        "allowed_roles": ("ADMIN",),
    },
    {
        "slug": "booking-management",
        "label": "Booking Management",
        "allowed_roles": ("ADMIN",),
    },
]


def find_nav_item(slug):
    return next((item for item in NAV_ITEMS if item["slug"] == slug), None)


def can_access(role, item):
    return role == "ADMIN" or role in item["allowed_roles"]


def can_access_module(role, slug):
    item = find_nav_item(slug)
    if item is None:
        return False
    return can_access(role, item)


def visible_nav_items(role):
    return [item for item in NAV_ITEMS if can_access(role, item)]
