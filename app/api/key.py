from apiflask import APIBlueprint, EmptySchema, abort

from app.schemas.key import KeyIn, KeyOut
from app.services.key import (
    create_key,
    delete_key,
    get_key,
    list_keys,
    update_key,
)

keys_blp = APIBlueprint("keys", __name__, url_prefix="/api/keys", tag="Keys")


@keys_blp.get("/")
@keys_blp.output(KeyOut(many=True))
def get_keys():
    return list_keys()


@keys_blp.post("/")
@keys_blp.input(KeyIn)
@keys_blp.output(KeyOut, status_code=201)
def create_key_view(json_data):
    try:
        key = create_key(json_data)
        return key
    except ValueError as err:
        abort(422, message=str(err))


@keys_blp.get("/<int:key_id>/")
@keys_blp.output(KeyOut)
def get_key_view(key_id):
    key = get_key(key_id)
    if key is None:
        abort(404, message="Key not found.")
    return key


@keys_blp.patch("/<int:key_id>/")
@keys_blp.input(KeyIn(partial=True))
@keys_blp.output(KeyOut)
def update_key_view(key_id, json_data):
    key = get_key(key_id)
    if key is None:
        abort(404, message="Key not found.")
    try:
        key = update_key(key, json_data)
        return key
    except ValueError as err:
        abort(422, message=str(err))


@keys_blp.delete("/<int:key_id>/")
@keys_blp.output(EmptySchema, status_code=204)
def delete_key_view(key_id):
    key = get_key(key_id)
    if key is None:
        abort(404, message="Key not found.")
    delete_key(key)
