from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session, selectinload

from app.api.deps.auth import (
    Principal,
    require_institution_user,
    require_institution_user_unrotated,
    require_user,
    require_user_or_institution_user,
    require_user_property_scope,
)
from app.db.session import get_db
from app.models import (
    Institution,
    InstitutionUser,
    Loan,
    OwnerAcknowledgement,
    Property,
    PropertyAgreement,
    User,
    UserProperty,
)
from app.schemas.institution import (
    PROFESSIONAL_ROLES,
    InstitutionCreate,
    InstitutionRead,
    InstitutionUserCreate,
    InstitutionUserCreated,
    InstitutionUserRead,
    ProfessionalRole,
)
from app.schemas.listing import ListingRead
from app.schemas.owner_acknowledgement import (
    AcknowledgementRead,
    OwnerInviteRead,
    PropertyDetailRead,
    PropertyOwnersRead,
    PropertyOwnerStatus,
)
from app.schemas.professional import ProfessionalRead
from app.schemas.property import PropertyCreate, PropertyRead, PropertyUpdate
from app.schemas.property_agreement import PropertyAgreementCreate, PropertyAgreementRead
from app.schemas.user_property import OwnerInviteCreate
from app.services.auth import (
    issue_institution_invite_token,
    issue_invite_token,
    refresh_and_store_institution_token,
    unusable_password_hash,
)

router = APIRouter()


@router.post("/institutions", response_model=InstitutionRead, status_code=status.HTTP_201_CREATED)
def create_institution(
    payload: InstitutionCreate,
    response: Response,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    if principal.institution_id is None:
        raise HTTPException(status_code=403, detail="Institutional auth required")
    institution = Institution(**payload.model_dump())
    db.add(institution)
    db.commit()
    db.refresh(institution)
    return institution


@router.post("/institution-users", response_model=InstitutionUserCreated, status_code=status.HTTP_201_CREATED)
def create_institution_user(
    payload: InstitutionUserCreate,
    response: Response,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    if principal.institution_id != payload.institutionId:
        raise HTTPException(status_code=403, detail="Loan officer not authorized for institution")
    inst_user = InstitutionUser(**payload.model_dump(), passwordHash=unusable_password_hash(), passwordSetAt=None)
    db.add(inst_user)
    db.commit()
    db.refresh(inst_user)
    token = issue_institution_invite_token(db, inst_user.id)
    read = InstitutionUserRead.model_validate(inst_user)
    return InstitutionUserCreated(**read.model_dump(), activationToken=token, activationPath=f"/activate#token={token}")


@router.get("/professionals", response_model=list[ProfessionalRead])
def list_professionals(
    role: ProfessionalRole | None = None,
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _principal: Principal = Depends(require_user_or_institution_user),
    db: Session = Depends(get_db),
):
    inst_name = Institution.name.label("institutionName")
    columns = (InstitutionUser.id, InstitutionUser.name, InstitutionUser.role, inst_name)
    query = (
        db.query(*columns)
        .join(Institution, Institution.id == InstitutionUser.institutionId)
        .filter(InstitutionUser.role.in_([role] if role else PROFESSIONAL_ROLES))
    )
    rows = query.order_by(InstitutionUser.name, InstitutionUser.id).limit(limit).offset(offset).all()
    return [ProfessionalRead(**row._asdict()) for row in rows]


LOAN_FIELDS = ("loanAmount", "currentBalance", "monthlyPayment", "dynamicBillingEnabled")


def _loan_from(prop: Property) -> Loan:
    # Unset fields (dynamicBillingEnabled before the INSERT default) stay unset so Loan's own default applies.
    return Loan(**{f: getattr(prop, f) for f in LOAN_FIELDS if getattr(prop, f) is not None})


def _property_read(prop: Property) -> PropertyRead:
    # The Loan row is the source of truth for the loan fields; the legacy property columns are only a fallback
    # for a property without a Loan row (until those columns are dropped).
    loan_source = prop.loan if prop.loan is not None else prop
    return PropertyRead(
        id=prop.id,
        institutionId=prop.institutionId,
        address=prop.address,
        status=prop.status,
        createdAt=prop.createdAt,  # type: ignore[arg-type]
        **{f: getattr(loan_source, f) for f in LOAN_FIELDS},
    )


@router.post("/properties", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
def create_property(
    payload: PropertyCreate,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    if principal.institution_id != payload.institutionId:
        raise HTTPException(status_code=403, detail="Loan officer not authorized for institution")

    prop = Property(**payload.model_dump(), status="pending_acknowledgement")
    prop.loan = _loan_from(prop)  # dual-write: the loan table mirrors the property's loan columns
    db.add(prop)
    db.commit()
    db.refresh(prop)
    # Rotate on the success path only: a 403/422 cannot carry X-Refreshed-Token, so rotating earlier would strand the
    # officer with a dead token.
    officer = db.query(InstitutionUser).filter(InstitutionUser.id == principal.user_id).one()
    response.headers["X-Refreshed-Token"] = refresh_and_store_institution_token(db, officer)
    return _property_read(prop)


@router.post(
    "/properties/{propertyId}/agreement", response_model=PropertyAgreementRead, status_code=status.HTTP_201_CREATED
)
def attach_agreement(
    propertyId: str,
    payload: PropertyAgreementCreate,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == UUID(propertyId)).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if principal.institution_id != prop.institutionId:
        raise HTTPException(status_code=403, detail="Loan officer not authorized for institution")
    if prop.status == "active":
        raise HTTPException(status_code=403, detail="Property is active; setup writes are closed")

    existing = db.query(PropertyAgreement).filter(PropertyAgreement.propertyId == prop.id).first()
    if existing is not None:
        raise HTTPException(status_code=409, detail="Agreement already exists for property")

    agreement = PropertyAgreement(propertyId=prop.id, **payload.model_dump())
    db.add(agreement)
    db.commit()
    db.refresh(agreement)
    # Rotate on the success path only: a 403/404/409/422 cannot carry X-Refreshed-Token, so rotating earlier would
    # strand the officer with a dead token.
    officer = db.query(InstitutionUser).filter(InstitutionUser.id == principal.user_id).one()
    response.headers["X-Refreshed-Token"] = refresh_and_store_institution_token(db, officer)
    return agreement


def _with_invite_token(db: Session, user: User, ack: OwnerAcknowledgement) -> OwnerInviteRead:
    # Only passwordless invitees need a token to set their password; re-invites re-issue a fresh one.
    result = OwnerInviteRead.model_validate(ack)
    if user.passwordSetAt is None:
        result.inviteToken = issue_invite_token(db, user.id)
    return result


@router.post("/properties/{propertyId}/owners", response_model=OwnerInviteRead, status_code=status.HTTP_201_CREATED)
def invite_owner(
    propertyId: str,
    payload: OwnerInviteCreate,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == UUID(propertyId)).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    if principal.institution_id != prop.institutionId:
        raise HTTPException(status_code=403, detail="Loan officer not authorized for institution")
    if prop.status == "active":
        raise HTTPException(status_code=403, detail="Property is active; setup writes are closed")

    agreement = db.query(PropertyAgreement).filter(PropertyAgreement.propertyId == prop.id).first()
    if agreement is None:
        raise HTTPException(status_code=400, detail="Property agreement must be attached first")

    user = db.query(User).filter(User.email == payload.email).first()
    if user is None:
        user = User(name=payload.name, email=payload.email, passwordHash=unusable_password_hash())
        db.add(user)
        db.flush()

    user_property = (
        db.query(UserProperty).filter(UserProperty.userId == user.id, UserProperty.propertyId == prop.id).first()
    )
    if user_property is None:
        user_property = UserProperty(
            userId=user.id, propertyId=prop.id, maxOwnershipPercent=payload.maxOwnershipPercent
        )
        db.add(user_property)
        db.flush()

    existing_ack = (
        db.query(OwnerAcknowledgement)
        .filter(
            OwnerAcknowledgement.agreementId == agreement.id,
            OwnerAcknowledgement.userPropertyId == user_property.id,
        )
        .first()
    )
    if existing_ack is not None:
        result = _with_invite_token(db, user, existing_ack)
        # Rotate on the success path only: a 400/403/404/422 cannot carry X-Refreshed-Token, so rotating earlier would
        # strand the officer with a dead token.
        officer = db.query(InstitutionUser).filter(InstitutionUser.id == principal.user_id).one()
        response.headers["X-Refreshed-Token"] = refresh_and_store_institution_token(db, officer)
        return result

    ack = OwnerAcknowledgement(agreementId=agreement.id, userPropertyId=user_property.id, signedAt=None)
    db.add(ack)
    db.commit()
    db.refresh(ack)
    result = _with_invite_token(db, user, ack)
    # Rotate on the success path only: a 400/403/404/422 cannot carry X-Refreshed-Token, so rotating earlier would
    # strand the officer with a dead token.
    officer = db.query(InstitutionUser).filter(InstitutionUser.id == principal.user_id).one()
    response.headers["X-Refreshed-Token"] = refresh_and_store_institution_token(db, officer)
    return result


@router.post("/properties/{propertyId}/acknowledge", response_model=AcknowledgementRead)
def acknowledge_agreement(
    propertyId: str,
    response: Response,
    principal: Principal = Depends(require_user),
    db: Session = Depends(get_db),
):
    prop = db.query(Property).filter(Property.id == UUID(propertyId)).first()
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")

    agreement = db.query(PropertyAgreement).filter(PropertyAgreement.propertyId == prop.id).first()
    if agreement is None:
        raise HTTPException(status_code=404, detail="Agreement not found")

    user_property = (
        db.query(UserProperty)
        .filter(UserProperty.userId == principal.user_id, UserProperty.propertyId == prop.id)
        .first()
    )
    if user_property is None:
        raise HTTPException(status_code=403, detail="User is not an owner on this property")

    ack = (
        db.query(OwnerAcknowledgement)
        .filter(
            OwnerAcknowledgement.agreementId == agreement.id,
            OwnerAcknowledgement.userPropertyId == user_property.id,
        )
        .first()
    )
    if ack is None:
        raise HTTPException(status_code=404, detail="Acknowledgement record not found")

    ack.signedAt = datetime.now(UTC)

    all_acks = db.query(OwnerAcknowledgement).filter(OwnerAcknowledgement.agreementId == agreement.id).all()
    if all(a.signedAt is not None for a in all_acks):
        prop.status = "active"
        if agreement.effectiveAt is None:
            agreement.effectiveAt = datetime.now(UTC)

    db.commit()
    db.refresh(ack)
    return ack


def _visible_properties(db: Session, principal: Principal):
    # Officers see their whole institution; owners see only the properties they are linked to.
    query = db.query(Property)
    if principal.user_type == "institution_user":
        return query.filter(Property.institutionId == principal.institution_id)
    return query.join(UserProperty, UserProperty.propertyId == Property.id).filter(
        UserProperty.userId == principal.user_id
    )


@router.get("/properties", response_model=list[PropertyRead])
def list_properties(
    response: Response,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    principal: Principal = Depends(require_user_or_institution_user),
    db: Session = Depends(get_db),
):
    query = _visible_properties(db, principal).order_by(Property.createdAt.desc(), Property.id)
    # selectinload: one extra query for all loans on the page instead of one lazy load per property.
    rows = query.options(selectinload(Property.loan)).limit(limit).offset(offset).all()
    return [_property_read(p) for p in rows]


def _pending_listings(db: Session):
    # Marketplace: every institution's pending properties; active ones stay institution/owner-scoped.
    return db.query(Property).filter(Property.status == "pending_acknowledgement")


@router.get("/listings", response_model=list[ListingRead])
def list_listings(
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _principal: Principal = Depends(require_user_or_institution_user),
    db: Session = Depends(get_db),
):
    return _pending_listings(db).order_by(Property.createdAt.desc(), Property.id).limit(limit).offset(offset).all()


def _readable_property(db: Session, principal: Principal, property_id: str) -> Property:
    prop = db.query(Property).filter(Property.id == UUID(property_id)).first()
    if principal.user_type == "institution_user":
        # Another institution's property is indistinguishable from a missing one (no existence leak).
        if prop is None or prop.institutionId != principal.institution_id:
            raise HTTPException(status_code=404, detail="Property not found")
        return prop
    if prop is None:
        raise HTTPException(status_code=404, detail="Property not found")
    require_user_property_scope(prop.id, principal, db)
    return prop


@router.get("/properties/{propertyId}", response_model=PropertyDetailRead)
def get_property(
    propertyId: str,
    response: Response,
    principal: Principal = Depends(require_user_or_institution_user),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, propertyId)

    agreement = db.query(PropertyAgreement).filter(PropertyAgreement.propertyId == prop.id).first()
    return {
        "property": _property_read(prop).model_dump(),
        "agreement": PropertyAgreementRead.model_validate(agreement).model_dump() if agreement else None,
    }


@router.patch("/properties/{propertyId}", response_model=PropertyRead)
def update_property(
    propertyId: str,
    payload: PropertyUpdate,
    response: Response,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, propertyId)  # other institutions' properties look nonexistent
    if prop.status == "active":
        raise HTTPException(status_code=403, detail="Property is active; setup writes are closed")
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(prop, field, value)
    if prop.loan is None:
        prop.loan = _loan_from(prop)
    else:
        # Dual-write only what changed, so an unrelated edit never overwrites the Loan row with legacy values.
        for field in LOAN_FIELDS:
            if field in changes:
                setattr(prop.loan, field, changes[field])
    db.commit()
    db.refresh(prop)
    return _property_read(prop)


@router.delete("/properties/{propertyId}", status_code=204)
def delete_property(
    propertyId: str,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, propertyId)  # other institutions' properties look nonexistent
    if prop.status == "active":
        raise HTTPException(status_code=403, detail="Property is active; setup writes are closed")
    db.delete(prop)  # ORM cascades remove agreement, loan, owner links and their acknowledgements; Users stay
    db.commit()
    return Response(status_code=204)


@router.get("/properties/{propertyId}/owners", response_model=PropertyOwnersRead)
def list_owners(
    propertyId: str,
    response: Response,
    principal: Principal = Depends(require_user_or_institution_user),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, propertyId)

    agreement = db.query(PropertyAgreement).filter(PropertyAgreement.propertyId == prop.id).first()
    if agreement is None:
        return {"owners": []}  # no agreement attached, so nobody can have been invited yet

    rows = (
        db.query(UserProperty, User, OwnerAcknowledgement)
        .join(User, User.id == UserProperty.userId)
        .join(
            OwnerAcknowledgement,
            (OwnerAcknowledgement.userPropertyId == UserProperty.id)
            & (OwnerAcknowledgement.agreementId == agreement.id),
            isouter=True,
        )
        .filter(UserProperty.propertyId == prop.id)
        .all()
    )

    owners = [
        PropertyOwnerStatus(
            userPropertyId=up.id,
            userId=u.id,
            name=u.name,
            email=u.email,
            maxOwnershipPercent=float(up.maxOwnershipPercent) if up.maxOwnershipPercent is not None else None,
            signedAt=ack.signedAt if ack else None,
        )
        for up, u, ack in rows
    ]
    return {"owners": owners}
