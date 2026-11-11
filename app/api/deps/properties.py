"""The ONE property lookup. Every handler that loads a property for a caller goes through load_property.

Rule (decided 2026-11-11): a missing property is a 404 and a forbidden one is a 403; existence is not hidden (guessing
an id is answered by unguessable UUIDs plus this check on every lookup). A malformed id is a missing property.
State rules (active property, 409s, agreement missing) are not ownership and stay in the handlers.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, require_user_property_scope
from app.models import Property


def load_property(db: Session, principal: Principal, property_id: str | UUID) -> Property:
    if isinstance(property_id, str):
        try:
            property_id = UUID(property_id)
        except ValueError:
            raise HTTPException(status_code=404, detail="Property not found") from None
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if principal.user_type == "institution_user":
        if prop.institutionId != principal.institution_id:
            raise HTTPException(status_code=403, detail="Loan officer not authorized for institution")
    else:
        require_user_property_scope(prop.id, principal, db)
    return prop
