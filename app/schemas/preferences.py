from apiflask import Schema, fields, validators


class PreferencesIn(Schema):
    no_show_grace_minutes = fields.Integer(
        required=True,
        validate=validators.Range(min=1, error="Must be at least 1 minute."),
    )
