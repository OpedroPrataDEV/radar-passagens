from __future__ import annotations

from datetime import date, timedelta


def datas_da_janela(dias_semana: tuple[int, ...], inicio: date, janela_dias: int) -> list[date]:
    """Todas as datas entre `inicio` e `inicio + janela_dias` que caem nos dias da semana pedidos."""
    datas = []
    for i in range(janela_dias + 1):
        d = inicio + timedelta(days=i)
        if d.weekday() in dias_semana:
            datas.append(d)
    return datas
