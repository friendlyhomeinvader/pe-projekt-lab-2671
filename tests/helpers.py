def assert_status(response, expected_status):
    if response.status_code == expected_status:
        return
    detail = response.get_json(silent=True)
    if detail is None:
        detail = response.data
    raise AssertionError(
        f"expected status {expected_status}, got {response.status_code}: {detail!r}"
    )


def assert_fields_absent(body, *field_names):
    for field_name in field_names:
        assert field_name not in body


def assert_only_fields_changed(before, after, *changed_fields):
    unchanged_fields = set(before) - set(changed_fields)
    for field_name in unchanged_fields:
        assert after[field_name] == before[field_name], (
            f"expected {field_name!r} to stay {before[field_name]!r}, got {after[field_name]!r}"
        )
