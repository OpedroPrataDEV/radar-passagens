from __future__ import annotations

import re
import time as _time
from datetime import date, datetime, time
from typing import Any

import requests

from ..models import Route, Trip


class ProviderError(RuntimeError):
    pass


def get_path(data: Any, path: str) -> Any:
    """Acessa JSON aninhado por caminho com pontos: 'a.b.0.c'. Retorna None se não existir."""
    atual = data
    for parte in path.split("."):
        if isinstance(atual, list):
            try:
                atual = atual[int(parte)]
            except (ValueError, IndexError):
                return None
        elif isinstance(atual, dict):
            if parte not in atual:
                return None
            atual = atual[parte]
        else:
            return None
    return atual


def parse_preco(valor: Any, divisor: float = 1.0) -> float | None:
    """Aceita 29.9, "29.90", "R$ 29,90", "1.029,90"."""
    if valor is None:
        return None
    if isinstance(valor, (int, float)):
        return round(float(valor) / divisor, 2)
    texto = re.sub(r"[^\d,.\-]", "", str(valor))
    if not texto:
        return None
    if "," in texto:  # formato brasileiro: ponto separa milhar, vírgula separa decimal
        texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto) / divisor, 2)
    except ValueError:
        return None


def parse_saida(valor: Any, dia: date) -> datetime | None:
    """Aceita ISO ('2026-11-19T06:30:00', com ou sem fuso) ou só 'HH:MM'."""
    if valor is None:
        return None
    texto = str(valor).strip()
    m = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", texto)
    if m:
        return datetime.combine(dia, time(int(m.group(1)), int(m.group(2))))
    try:
        dt = datetime.fromisoformat(texto.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=None)  # compara sempre em horário "de relógio" local


def _substituir(valor: Any, ctx: dict[str, str]) -> Any:
    """Troca {placeholders} em strings, dicts e listas (sem usar str.format, por causa de chaves em JSON)."""
    if isinstance(valor, str):
        for k, v in ctx.items():
            valor = valor.replace("{" + k + "}", v)
        return valor
    if isinstance(valor, dict):
        return {k: _substituir(v, ctx) for k, v in valor.items()}
    if isinstance(valor, list):
        return [_substituir(v, ctx) for v in valor]
    return valor


class JsonEndpointProvider:
    nome = "json"

    """Provedor genérico: chama um endpoint que devolve JSON e mapeia os campos via config.

    Todo o "conhecimento" sobre o site fica no config.toml (URL, parâmetros, mapeamento).
    Se o site mudar, você ajusta o config em vez de mexer no código.
    """

    def __init__(self, cfg: dict, session: requests.Session | None = None):
        if "url" not in cfg or "mapeamento" not in cfg:
            raise ProviderError(
                "Faltam 'url' e 'mapeamento' em [provedor.buser] no config.toml. "
                "Veja o README (seção 'Descobrindo o endpoint')."
            )
        self.cfg = cfg
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": "radar-passagens (projeto pessoal de estudo)", **cfg.get("headers", {})}
        )

    def _contexto(self, route: Route, day: date) -> dict[str, str]:
        return {
            "origem": route.origem,
            "destino": route.destino,
            "origem_id": route.origem_id or route.origem,
            "destino_id": route.destino_id or route.destino,
            "data": day.isoformat(),
            "data_br": day.strftime("%d/%m/%Y"),
        }

    def _requisitar(self, route: Route, day: date) -> Any:
        ctx = self._contexto(route, day)
        metodo = self.cfg.get("metodo", "GET").upper()
        url = _substituir(self.cfg["url"], ctx)
        params = _substituir(self.cfg.get("params", {}), ctx) or None
        corpo = _substituir(self.cfg.get("corpo"), ctx) if self.cfg.get("corpo") else None

        ultimo_erro: Exception | None = None
        for tentativa in range(3):
            try:
                resp = self.session.request(metodo, url, params=params, json=corpo, timeout=20)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise ProviderError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ProviderError, ValueError) as e:
                ultimo_erro = e
                _time.sleep(2 ** tentativa)
        raise ProviderError(f"Falha ao consultar {route.titulo} em {day}: {ultimo_erro}")

    def search(self, route: Route, day: date) -> list[Trip]:
        return self.parse(self._requisitar(route, day), route, day)

    def parse(self, data: Any, route: Route, day: date) -> list[Trip]:
        m = self.cfg["mapeamento"]
        itens = get_path(data, m["lista"]) if m.get("lista") else data
        if not isinstance(itens, list):
            raise ProviderError(
                f"Não achei a lista de viagens em '{m.get('lista')}'. O formato da resposta mudou?"
            )

        divisor = float(m.get("preco_divisor", 1))
        link_padrao = self.cfg.get("link", "")
        trips = []
        for item in itens:
            preco = parse_preco(get_path(item, m["preco"]), divisor)
            saida = parse_saida(get_path(item, m["horario"]), day)
            if preco is None or saida is None:
                continue  # item sem preço (esgotado) ou sem horário: ignora
            empresa = get_path(item, m["empresa"]) if m.get("empresa") else None
            link = get_path(item, m["link"]) if m.get("link") else None
            trips.append(
                Trip(
                    data=day,
                    saida=saida,
                    preco=preco,
                    empresa=str(empresa or "—"),
                    origem=route.origem,
                    destino=route.destino,
                    link=str(link or _substituir(link_padrao, self._contexto(route, day))),
                    fonte=str(self.cfg.get("fonte", "json")),
                )
            )
        return trips
