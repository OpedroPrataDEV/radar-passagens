from __future__ import annotations

import hashlib
from datetime import date, datetime, time

from ..models import Route, Trip

EMPRESAS = ["Viação Exemplo", "Expresso Demo", "Litoral Bus"]
HORARIOS = ["05:30", "07:00", "09:15", "12:00", "15:40", "18:30", "21:00"]


class MockProvider:
    nome = "mock"

    """Dados fake e determinísticos: serve para testar o fluxo inteiro sem depender de site nenhum."""

    def search(self, route: Route, day: date) -> list[Trip]:
        trips = []
        for i, hhmm in enumerate(HORARIOS):
            seed = hashlib.sha256(f"{route.titulo}|{day}|{hhmm}".encode()).digest()
            preco = 22 + seed[0] % 40 + (seed[1] % 100) / 100  # entre ~22 e ~62
            h, m = map(int, hhmm.split(":"))
            trips.append(
                Trip(
                    data=day,
                    saida=datetime.combine(day, time(h, m)),
                    preco=round(preco, 2),
                    empresa=EMPRESAS[i % len(EMPRESAS)],
                    origem=route.origem,
                    destino=route.destino,
                    link="https://exemplo.com/comprar",
                    fonte="mock",
                )
            )
        return trips
