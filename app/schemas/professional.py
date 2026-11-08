from uuid import UUID

from pydantic import BaseModel

from app.schemas.institution import ProfessionalRole


class ProfessionalRead(BaseModel):
    """Directory view of an institution user: deliberately no email, credentials or institution id."""

    id: UUID
    name: str
    role: ProfessionalRole
    institutionName: str
