from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps.auth import Principal, require_institution_user
from app.api.routes.equity_splitter import _readable_property
from app.db.session import get_db
from app.models import PropertyListing
from app.schemas.property_listing import PropertyListingCreate, PropertyListingRead

router = APIRouter()


@router.post(
    "/properties/{property_id}/listings", response_model=PropertyListingRead, status_code=status.HTTP_201_CREATED
)
def create_listing(
    property_id: str,
    payload: PropertyListingCreate,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, property_id)  # another institution's property looks nonexistent
    listing = PropertyListing(propertyId=prop.id, status="draft", **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return listing


@router.get("/properties/{property_id}/listings", response_model=list[PropertyListingRead])
def list_listings(
    property_id: str,
    principal: Principal = Depends(require_institution_user),
    db: Session = Depends(get_db),
):
    prop = _readable_property(db, principal, property_id)
    return (
        db.query(PropertyListing)
        .filter(PropertyListing.propertyId == prop.id)
        .order_by(PropertyListing.createdAt.desc(), PropertyListing.id)
        .all()
    )
