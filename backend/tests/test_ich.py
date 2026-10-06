"""Das Profil oben rechts fragt `/api/v1/ich` (CI HB-KONTO, ABGLEICH G8).

Es zeigt einen Namen und ein Kürzel — nie einen leeren Kreis, und nie mehr
als den Namen: Olares meldet an, Insilo kennt sonst nichts Persönliches.
"""

from __future__ import annotations

from uuid import uuid4

from app.auth import CurrentUser
from app.routers.ich import IchRead, ich_aus


def _user(name: str | None) -> CurrentUser:
    return CurrentUser(olares_username="kaivostudio", user_id=uuid4(), org_id=uuid4(), display_name=name)


def test_ohne_anzeigename_steht_der_olares_name() -> None:
    assert ich_aus(_user(None)) == IchRead(anmeldename="kaivostudio", name="kaivostudio")
    assert ich_aus(_user("   ")).name == "kaivostudio"


def test_mit_anzeigename_steht_er_vorn() -> None:
    assert ich_aus(_user("Kai Böhm")) == IchRead(anmeldename="kaivostudio", name="Kai Böhm")


def test_nur_name_und_anmeldename() -> None:
    assert set(IchRead.model_fields) == {"anmeldename", "name"}
