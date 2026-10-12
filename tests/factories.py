def user_payload(**overrides):
    payload = {
        "username": "john.doe",
        "display_name": "John Doe",
        "email": "john.doe@uni.su",
        "role": "OPERATOR",
        "password": "Password123456!!",
    }
    payload.update(overrides)
    return payload


def room_payload(**overrides):
    payload = {
        "code": "A101",
        "location": "Building A",
        "capacity": 10,
    }
    payload.update(overrides)
    return payload
