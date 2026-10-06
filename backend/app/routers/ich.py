"""Wer bin ich — für das Profil oben rechts (CI HB-KONTO, ABGLEICH G8).

Insilo meldet nicht selbst an: Olares prüft und reicht die Identität als
`X-Bfl-User` durch. Das Profil braucht davon nur Namen und Kürzel; mehr
gibt dieser Endpunkt nicht heraus. Abmelden gibt es in Insilo nicht —
das wäre eine Attrappe, Olares meldet an und ab.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api/v1", tags=["ich"])


class IchRead(BaseModel):
    anmeldename: str
    name: str


def ich_aus(user: CurrentUser) -> IchRead:
    """Ohne eigenen Anzeigenamen steht der Olares-Name — nie ein leerer Kreis."""
    name = (user.display_name or "").strip() or user.olares_username
    return IchRead(anmeldename=user.olares_username, name=name)


@router.get("/ich", response_model=IchRead)
async def ich(user: CurrentUser = Depends(get_current_user)) -> IchRead:
    return ich_aus(user)
