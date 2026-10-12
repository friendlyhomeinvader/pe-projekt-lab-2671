from apiflask import APIBlueprint, EmptySchema, abort

from app.schemas.feature import FeatureIn, FeatureOut
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
def create_feature_view(json_data):
    feature = create_feature(json_data)
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
def update_feature_view(feature_id, json_data):
    feature = get_feature(feature_id)
    if feature is None:
        abort(404, message="Feature not found.")
    feature = update_feature(feature, json_data)
    return feature


@features_blp.delete("/<int:feature_id>/")
@features_blp.output(EmptySchema, status_code=204)
def delete_feature_view(feature_id):
    feature = get_feature(feature_id)
    if feature is None:
        abort(404, message="Feature not found.")
    delete_feature(feature)
