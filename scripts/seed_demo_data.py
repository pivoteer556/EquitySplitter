"""The fictional demo data for scripts/seed_demo.py. Everything here is invented: the address is not a real place
(ZIP 00000 is invalid on purpose), the emails use the reserved example.com domain, and the description is AI-written
sample text. Design of record: docs/design/vertical-slice.md section 3."""

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import NamedTuple

INSTITUTION_NAME = "Willowmere Demo Lending (fictional)"
ADDRESS = "418 Larkspur Court, Willowmere Heights, OH 00000"

LOAN_AMOUNT = Decimal("325000.00")
MONTHLY_PAYMENT = Decimal("2001.08")
INTEREST_RATE_PERCENT = Decimal("6.250")
TERM_MONTHS = 360

PURCHASE_PRICE = Decimal("485000.00")
CLOSING_DATE = date(2026, 12, 18)
APPLICATION_FILED_AT = datetime(2026, 10, 20, tzinfo=UTC)
INTENT_TO_PROCEED_AT = datetime(2026, 11, 5, tzinfo=UTC)

# Agreement values: free text in the schema; these match the vocabulary the tests and officer endpoint use.
NOTICE_DAYS = 60
VALUATION_METHOD = "appraisal"
PARTIAL_CLAIM_METHOD = "pro_rata"

LISTING_ASKING_PRICE = Decimal("489000.00")
LISTING_BEDROOMS = 4
LISTING_BATHROOMS = Decimal("2.5")
LISTING_SQUARE_FEET = 2140
LISTING_LISTED_AT = datetime(2026, 9, 15, tzinfo=UTC)
LISTING_DESCRIPTION = (
    "Set at the quiet end of Larkspur Court, this four-bedroom home pairs a bright, open main floor with the kind "
    "of yard that gets used. The kitchen opens to a sunny dining area and a family room with a gas fireplace, so "
    "the cook is never cut off from the conversation. Upstairs, the primary suite has a walk-in closet and a "
    "double-sink bath; three more bedrooms share a second full bath. A two-car garage, a covered front porch and a "
    "fenced backyard with a small patio round it out. Sidewalks, a neighborhood park and the elementary school are "
    "a short walk away. Built in 2004 and kept up since: new roof in 2022, updated HVAC in 2024. "
    "(Sample listing for demonstration; not a real property.)"
)


class Buyer(NamedTuple):
    name: str
    email: str
    downPayment: Decimal


BUYERS = (
    Buyer("Marisol Vega", "marisol.vega@example.com", Decimal("80000.00")),
    Buyer("Dev Raman", "dev.raman@example.com", Decimal("50000.00")),
    Buyer("Hana Lindqvist", "hana.lindqvist@example.com", Decimal("30000.00")),
)
