from __future__ import annotations

import logging
import time as _time
from dataclasses import dataclass, field
from datetime import date, datetime

from .dates import datas_da_janela
from .models import Route, Trip
from .providers.base import Provider

log = logging.getLogger("radar")


@dataclass
class Resultado:
    rota: Route
    viagens: list[Trip] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    consultas: int = 0
    todas: list[Trip] = field(default_factory=list)  # todas as viagens futuras, sem filtro de preço
    vistas: int = 0  # viagens lidas pelo provedor, antes de qualquer filtro


def _no_horario(trip: Trip, route: Route) -> bool:
    hhmm = trip.saida.strftime("%H:%M")
    if route.horario_min and hhmm < route.horario_min:
        return False
    if route.horario_max and hhmm > route.horario_max:
        return False
    return True


def buscar(
    rotas: list[Route],
    provedor: Provider | list[Provider],
    janela_dias: int,
    hoje: date | None = None,
    agora: datetime | None = None,
    pausa: float = 0.0,
) -> list[Resultado]:
    """Para cada rota: calcula as datas, consulta cada uma e filtra por preço e horário."""
    provedores = list(provedor) if isinstance(provedor, (list, tuple)) else [provedor]
    hoje = hoje or date.today()
    agora = agora or datetime.now()
    resultados = []

    for rota in rotas:
        res = Resultado(rota=rota)
        coletar = tuple(sorted(set(rota.dias) | set(rota.dias_site)))
        for dia in datas_da_janela(coletar, hoje, janela_dias):
            for prov in provedores:
                if res.consultas:
                    _time.sleep(pausa)  # gentileza com o site
                res.consultas += 1
                try:
                    viagens = prov.search(rota, dia)
                except Exception as e:  # uma consulta falhar não derruba as outras
                    log.warning("Falha em %s %s (%s): %s", rota.titulo, dia, getattr(prov, "nome", "?"), e)
                    res.erros.append(f"{getattr(prov, 'nome', '?')} {dia}: {e}")
                    continue
                res.vistas += len(viagens)
                res.todas.extend(v for v in viagens if v.saida > agora)
                res.viagens.extend(
                    v for v in viagens
                    if v.data.weekday() in rota.dias and v.preco <= rota.preco_max and v.saida > agora and _no_horario(v, rota)
                )
        res.viagens.sort(key=lambda v: (v.saida, v.preco))
        resultados.append(res)
    return resultados
