"""Helpers for lookups scoped to the current authenticated company."""

from flask import g, has_request_context


def get_tenant_scoped(model, identifier):
    """Return a tenant model by primary key, or ``None`` outside its scope."""
    if not has_request_context():
        return None

    empresa_id = getattr(g, "current_empresa_id", None)
    if empresa_id is None:
        return None

    return model.query.filter_by(id=identifier, empresa_id=empresa_id).first()
