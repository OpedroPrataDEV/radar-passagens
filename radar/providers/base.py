from __future__ import annotations

from datetime import date
from typing import Protocol

from ..models import Route, Trip


class Provider(Protocol):
    """Qualquer fonte de dados precisa só saber responder: quais viagens existem nessa data?"""

    def search(self, route: Route, day: date) -> list[Trip]: ...
