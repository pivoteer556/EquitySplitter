from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import (
    Principal,
    require_user_or_institution_user_unrotated,
    require_user_unrotated,
    rotate_session,
)
from app.db.session import get_db
from app.models import ConnectionRequest, InstitutionUser, Property, User, UserProperty
from app.schemas.connection_request import (
    ConnectionRequestCreate,
    ConnectionRequestRead,
    IncomingConnectionRequestRead,
)
from app.schemas.institution import PROFESSIONAL_ROLES

router = APIRouter()

_ORDER = (ConnectionRequest.createdAt.desc(), ConnectionRequest.id)


def _check_targets(db: Session, buyer_id, payload: ConnectionRequestCreate) -> None:
    # A missing professional and one outside the role vocabulary are indistinguishable; likewise for properties
    # that are missing vs. no longer pending.
    pro = db.query(InstitutionUser).filter(InstitutionUser.id == payload.professionalId).first()
    if pro is None or pro.role not in PROFESSIONAL_ROLES:
        raise HTTPException(status_code=404, detail="Professional not found")
    prop = db.query(Property).filter(Property.id == payload.propertyId).first()
    if prop is None or prop.status != "pending_acknowledgement":
        raise HTTPException(status_code=404, detail="Property not found")
    owner = db.query(UserProperty).filter(UserProperty.userId == buyer_id, UserProperty.propertyId == prop.id)
    if owner.first() is not None:
        raise HTTPException(status_code=409, detail="Already an owner of this property")
    dup = db.query(ConnectionRequest).filter(
        ConnectionRequest.buyerId == buyer_id,
        ConnectionRequest.professionalId == payload.professionalId,
        ConnectionRequest.propertyId == payload.propertyId,
    )
    if dup.first() is not None:
        raise HTTPException(status_code=409, detail="Connection already requested")


@router.post("/connection-requests", response_model=ConnectionRequestRead, status_code=status.HTTP_201_CREATED)
def create_connection_request(
    payload: ConnectionRequestCreate,
    response: Response,
    principal: Principal = Depends(require_user_unrotated),
    db: Session = Depends(get_db),
):
    _check_targets(db, principal.user_id, payload)
    request = ConnectionRequest(buyerId=principal.user_id, **payload.model_dump(), status="pending")
    db.add(request)
    try:
        db.commit()
    except IntegrityError:  # lost a race with an identical request: the UNIQUE constraint is the backstop
        db.rollback()
        raise HTTPException(status_code=409, detail="Connection already requested") from None
    db.refresh(request)
    # Rotate only now: a rejection above (404/409/422) cannot carry X-Refreshed-Token, so rotating earlier would
    # strand the buyer with a dead token.
    rotate_session(db, principal, response)
    return request


def _incoming(db: Session, professional_id, limit: int, offset: int) -> list[IncomingConnectionRequestRead]:
    # Only requests addressed to this very professional, not to colleagues at the same institution.
    query = (
        db.query(ConnectionRequest, User.name)
        .join(User, User.id == ConnectionRequest.buyerId)
        .filter(ConnectionRequest.professionalId == professional_id)
    )
    rows = query.order_by(*_ORDER).limit(limit).offset(offset).all()
    return [
        IncomingConnectionRequestRead(**ConnectionRequestRead.model_validate(req).model_dump(), buyerName=name)
        for req, name in rows
    ]


@router.get("/connection-requests", response_model=list[IncomingConnectionRequestRead] | list[ConnectionRequestRead])
def list_connection_requests(
    response: Response,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_user_or_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    # The unrotated dependency leaves the session alone so a 422 on limit/offset cannot strand the caller; rotate
    # here, on the success path only.
    if principal.user_type == "institution_user":
        result = _incoming(db, principal.user_id, limit, offset)
        rotate_session(db, principal, response)
        return result
    query = db.query(ConnectionRequest).filter(ConnectionRequest.buyerId == principal.user_id)
    rows = query.order_by(*_ORDER).limit(limit).offset(offset).all()
    rotate_session(db, principal, response)
    return rows
