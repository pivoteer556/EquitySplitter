from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, require_institution_user_unrotated, rotate_session
from app.api.routes.equity_splitter import _readable_property
from app.db.session import get_db
from app.models import PropertyListing
from app.models.property_listing import EDITABLE_LISTING_STATUSES, LISTING_TRANSITIONS
from app.schemas.property_listing import (
    PropertyListingCreate,
    PropertyListingRead,
    PropertyListingTransition,
    PropertyListingUpdate,
)

router = APIRouter()


@router.post(
    "/properties/{property_id}/listings", response_model=PropertyListingRead, status_code=status.HTTP_201_CREATED
)
def create_listing(
    property_id: str,
    payload: PropertyListingCreate,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, property_id)  # another institution's property looks nonexistent
    listing = PropertyListing(propertyId=prop.id, status="draft", **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    rotate_session(db, principal, response)
    return listing


@router.get("/properties/{property_id}/listings", response_model=list[PropertyListingRead])
def list_listings(
    property_id: str,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, property_id)
    listings = (
        db.query(PropertyListing)
        .filter(PropertyListing.propertyId == prop.id)
        .order_by(PropertyListing.createdAt.desc(), PropertyListing.id)
        .all()
    )
    rotate_session(db, principal, response)
    return listings


def _own_listing(db: Session, principal: Principal, listing_id: str) -> PropertyListing:
    """Another institution's listing looks nonexistent, exactly like an unknown id."""
    try:
        uid = UUID(listing_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Property not found") from None
    listing = db.get(PropertyListing, uid)
    if listing is None:
        raise HTTPException(status_code=404, detail="Property not found")
    _readable_property(db, principal, str(listing.propertyId))
    return listing


def _has_listed(db: Session, property_id: UUID) -> bool:
    return (
        db.query(PropertyListing.id)
        .filter(PropertyListing.propertyId == property_id, PropertyListing.status == "listed")
        .first()
        is not None
    )


_ALREADY_LISTED = "This property already has a listed listing; withdraw it first"


def _apply_transition(db: Session, listing: PropertyListing, to: str) -> None:
    if to == "sold":
        # BACKLOG 2h: sold requires the loan pipeline (full underwriting), which is not built.
        raise HTTPException(status_code=409, detail="Not available yet")
    if to not in LISTING_TRANSITIONS[listing.status]:
        raise HTTPException(status_code=409, detail=f"Cannot move a {listing.status} listing to {to}")
    now = datetime.now(UTC)
    if to == "listed":
        if _has_listed(db, listing.propertyId):
            raise HTTPException(status_code=409, detail=_ALREADY_LISTED)
        listing.listedAt = now
    elif listing.status == "listed":  # delistedAt marks leaving the market; a withdrawn draft was never on it
        listing.delistedAt = now
    listing.status = to


@router.post("/property-listings/{listing_id}/transition", response_model=PropertyListingRead)
def transition_listing(
    listing_id: str,
    payload: PropertyListingTransition,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    listing = _own_listing(db, principal, listing_id)
    _apply_transition(db, listing, payload.to)
    try:
        db.commit()
    except IntegrityError:  # lost a race with another listed listing; the partial unique index is the backstop
        db.rollback()
        raise HTTPException(status_code=409, detail=_ALREADY_LISTED) from None
    db.refresh(listing)
    rotate_session(db, principal, response)
    return listing


@router.patch("/property-listings/{listing_id}", response_model=PropertyListingRead)
def update_listing(
    listing_id: str,
    payload: PropertyListingUpdate,
    response: Response,
    principal: Principal = Depends(require_institution_user_unrotated),
    db: Session = Depends(get_db),
):
    listing = _own_listing(db, principal, listing_id)
    if listing.status not in EDITABLE_LISTING_STATUSES:
        raise HTTPException(status_code=409, detail=f"A {listing.status} listing cannot be edited")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(listing, field, value)
    db.commit()
    db.refresh(listing)
    rotate_session(db, principal, response)
    return listing
