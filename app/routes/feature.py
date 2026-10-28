from flask import abort, render_template, request
from marshmallow import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app import db
from app.schemas.feature import FeatureIn
from app.services.auth import role_required
from app.services.feature import (
    create_feature,
    delete_feature,
    get_feature,
    list_features,
    update_feature,
)
from app.services.notify import render_toast
from app.services.page import htmx_only


def _render_feature_form(*, is_edit, values, errors, feature_id=None, status=200):
    kwargs = {
        "is_edit": is_edit,
        "values": values,
        "errors": errors,
    }
    if feature_id is not None:
        kwargs["feature_id"] = feature_id
    html = render_template("partials/features/form.html", **kwargs)
    return (html, status) if status != 200 else html


def _feature_save_success(feature, verb):
    return render_template(
        "partials/features/save_success.html", features=list_features()
    ) + render_toast("success", f"Feature {feature.name} {verb}.")


def register_feature_routes(app):
    @app.get("/features")
    @htmx_only
    @role_required("ADMIN")
    def features_list():
        return render_template("partials/features/list.html", features=list_features())

    @app.get("/features/new")
    @htmx_only
    @role_required("ADMIN")
    def features_new():
        return _render_feature_form(is_edit=False, values={}, errors={})

    @app.get("/features/<int:feature_id>/edit")
    @htmx_only
    @role_required("ADMIN")
    def features_edit(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)
        values = {"name": feature.name, "description": feature.description}
        return _render_feature_form(
            is_edit=True, feature_id=feature.id, values=values, errors={}
        )

    @app.post("/features")
    @role_required("ADMIN")
    def features_create():
        try:
            data = FeatureIn().load(request.form)
        except ValidationError as err:
            return _render_feature_form(
                is_edit=False, values=request.form, errors=err.messages, status=422
            )

        feature = create_feature(data)
        return _feature_save_success(feature, "created")

    @app.patch("/features/<int:feature_id>")
    @role_required("ADMIN")
    def features_update(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)

        try:
            data = FeatureIn(partial=True).load(request.form)
        except ValidationError as err:
            return _render_feature_form(
                is_edit=True,
                feature_id=feature_id,
                values=request.form,
                errors=err.messages,
                status=422,
            )

        feature = update_feature(feature, data)
        return _feature_save_success(feature, "updated")

    @app.get("/features/<int:feature_id>/delete/confirm")
    @htmx_only
    @role_required("ADMIN")
    def features_delete_confirm(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)
        return render_template("partials/features/delete_confirm.html", feature=feature)

    @app.delete("/features/<int:feature_id>")
    @role_required("ADMIN")
    def features_delete(feature_id):
        feature = get_feature(feature_id)
        if feature is None:
            abort(404)
        name = feature.name
        try:
            delete_feature(feature)
        except SQLAlchemyError:
            db.session.rollback()
            return (
                render_template(
                    "partials/features/delete_success.html", features=list_features()
                )
                + render_toast("error", "Failed to delete feature. Please try again."),
                500,
            )
        return render_template(
            "partials/features/delete_success.html", features=list_features()
        ) + render_toast("success", f"Feature {name} deleted.")
