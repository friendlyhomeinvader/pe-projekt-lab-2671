from apiflask import APIBlueprint, EmptySchema, abort
from flask_login import current_user

from app.schemas.feature import FeatureIn, FeatureOut
from app.services.audit import log_action
from app.services.auth import role_required
from app.services.feature import (
    create_feature,
    delete_feature,
    get_feature,
    list_features,
    update_feature,
)

features_blp = APIBlueprint(
    "features", __name__, url_prefix="/api/features", tag="Features"
)


@features_blp.get("/")
@features_blp.output(FeatureOut(many=True))
def get_features():
    return list_features()


@features_blp.post("/")
@features_blp.input(FeatureIn)
@features_blp.output(FeatureOut, status_code=201)
@role_required("ADMIN")
def create_feature_view(json_data):
    feature = create_feature(json_data)
    log_action(
        current_user.id if current_user.is_authenticated else None,
        "feature.create",
        entity_type="feature",
        entity_id=feature.id,
        details=feature.name,
    )
    return feature


@features_blp.get("/<int:feature_id>/")
@features_blp.output(FeatureOut)
def get_feature_view(feature_id):
    feature = get_feature(feature_id)
    if feature is None:
        abort(404, message="Feature not found.")
    return feature


@features_blp.patch("/<int:feature_id>/")
@features_blp.input(FeatureIn(partial=True))
@features_blp.output(FeatureOut)
@role_required("ADMIN")
def update_feature_view(feature_id, json_data):
    feature = get_feature(feature_id)
    if feature is None:
        abort(404, message="Feature not found.")
    feature = update_feature(feature, json_data)
    log_action(
        current_user.id if current_user.is_authenticated else None,
        "feature.update",
        entity_type="feature",
        entity_id=feature.id,
        details=feature.name,
    )
    return feature


@features_blp.delete("/<int:feature_id>/")
@features_blp.output(EmptySchema, status_code=204)
@role_required("ADMIN")
def delete_feature_view(feature_id):
    feature = get_feature(feature_id)
    if feature is None:
        abort(404, message="Feature not found.")
    feature_id = feature.id
    name = feature.name
    delete_feature(feature)
    log_action(
        current_user.id if current_user.is_authenticated else None,
        "feature.delete",
        entity_type="feature",
        entity_id=feature_id,
        details=name,
    )
