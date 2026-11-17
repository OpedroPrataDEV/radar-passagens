from __future__ import annotations

import logging
import re
import time as _time
from datetime import date, datetime, time, timedelta
from html.parser import HTMLParser

import requests

from ..models import Route, Trip

log = logging.getLogger("radar")

BASE = "https://www.buser.com.br/onibus"
DIAS_SLUG = ["segunda-feira", "terca-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sabado", "domingo"]
MESES = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4, "maio": 5, "junho": 6,
    "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10, "novembro": 11, "dezembro": 12,
}
USER_AGENT = "Mozilla/5.0 (compatible; radar-passagens; projeto pessoal de estudo)"

# O texto visível de cada viagem na página segue esta ordem:
#   "quinta-feira, 19 de novembro" (cabeçalho do dia)
#   [N vagas ...]  07:20  19/11  <embarque>  10:10  <desembarque>  2h50min  Poltrona  Executivo  R$ 39,90  ...
_CABECALHO = re.compile(
    r"^(?:(?:segunda|ter[çc]a|quarta|quinta|sexta)-feira|s[áa]bado|domingo),\s*(\d{1,2})\s+de\s+([a-zçãé]+)$", re.I
)
_HORA = re.compile(r"^(\d{1,2}):(\d{2})$")
_DATA = re.compile(r"^(\d{2})/(\d{2})$")
_PRECO = re.compile(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})")
_VAGAS = re.compile(r"(\d+)\s+vagas?", re.I)
_JANELA_LINHAS = 18  # quantas linhas após o horário ainda pertencem ao card da viagem


class ProviderError(RuntimeError):
    pass


class PaginaNaoEncontrada(ProviderError):
    pass

class ErroNaoRepetivel(ProviderError):
    pass


class _Texto(HTMLParser):
    """Converte HTML em uma lista de linhas de texto visível (ignora script/style)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.linhas: list[str] = []
        self._ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._ignorar += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self._ignorar:
            self._ignorar -= 1

    def handle_data(self, data):
        if self._ignorar:
            return
        texto = " ".join(data.split())  # também normaliza espaços não separáveis
        if texto:
            self.linhas.append(texto)


def _resolver_data(dia: int, mes: int, ref: date) -> date | None:
    """A página mostra só dd/mm; deduz o ano usando a data consultada como referência."""
    try:
        cand = date(ref.year, mes, dia)
        if cand < ref - timedelta(days=30):
            cand = date(ref.year + 1, mes, dia)
        return cand
    except ValueError:
        return None


def parse_pagina(html: str, ref: date, route: Route, link: str) -> list[Trip]:
    """Extrai as viagens (data, horário, preço, vagas) do texto da página da Buser."""
    p = _Texto()
    p.feed(html)
    linhas = p.linhas

    cabecalho: tuple[int, int | None] | None = None
    viagens: list[Trip] = []
    atual: dict | None = None

    def fechar() -> None:
        nonlocal atual
        if atual is None:
            return
        texto = " ".join(atual["linhas"][:_JANELA_LINHAS])
        preco = None
        for m in _PRECO.finditer(texto):
            if re.search(r"\dx\s*$", texto[max(0, m.start() - 6) : m.start()]):
                continue  # "3x R$ 18,87" é parcela, não o preço
            preco = float(m.group(1).replace(".", "").replace(",", "."))
            break
        dia = _resolver_data(atual["dia"], atual["mes"], ref)
        if preco is not None and dia is not None:  # sem preço = esgotada
            viagens.append(
                Trip(
                    data=dia,
                    saida=datetime.combine(dia, time(atual["h"], atual["m"])),
                    preco=preco,
                    empresa="Buser",
                    origem=route.origem,
                    destino=route.destino,
                    link=link,
                    vagas=atual["vagas"],
                    fonte="buser",
                )
            )
        atual = None

    for i, linha in enumerate(linhas):
        cab = _CABECALHO.match(linha)
        if cab:
            fechar()
            cabecalho = (int(cab.group(1)), MESES.get(cab.group(2).lower()))
            continue

        hora = _HORA.match(linha)
        if hora and i + 1 < len(linhas):
            data = _DATA.match(linhas[i + 1])
            # só é "início de viagem" se a data bate com o cabeçalho do dia;
            # isso evita confundir "horário de chegada + data de chegada" (viagem que cruza a meia-noite)
            if data and (cabecalho is None or (int(data.group(1)), int(data.group(2))) == cabecalho):
                fechar()
                vagas = None
                for anterior in linhas[max(0, i - 3) : i]:
                    mv = _VAGAS.search(anterior)
                    if mv:
                        vagas = int(mv.group(1))
                atual = {
                    "h": int(hora.group(1)), "m": int(hora.group(2)),
                    "dia": int(data.group(1)), "mes": int(data.group(2)),
                    "vagas": vagas, "linhas": [],
                }
                continue

        if atual is not None:
            atual["linhas"].append(linha)
    fechar()

    unicas: dict[tuple, Trip] = {}  # a página repete a viagem "melhor preço" no topo
    for v in viagens:
        unicas.setdefault((v.saida, v.preco), v)
    resultado = list(unicas.values())

    if not resultado and any("R$" in l for l in linhas):
        raise ProviderError(
            "Há preços na página mas não consegui ler nenhuma viagem: o layout da Buser mudou?"
        )
    return resultado


class BuserProvider:
    nome = "buser"

    """Lê as páginas públicas de busca da Buser (sem login) e extrai as viagens.

    modo = "dia_da_semana": 1 requisição traz as próximas ~12 semanas daquele dia da semana
                            (ex.: todas as quintas) — a mais econômica.
    modo = "por_data":      1 requisição por data, usando ?ida=AAAA-MM-DD.
    """

    def __init__(self, cfg: dict | None = None, session: requests.Session | None = None):
        cfg = cfg or {}
        self.modo = cfg.get("modo", "dia_da_semana")
        self.pausa = float(cfg.get("pausa_segundos", 0))
        self._rede = False
        if self.modo not in ("dia_da_semana", "por_data"):
            raise ProviderError("'modo' deve ser 'dia_da_semana' ou 'por_data'")
        self.session = session or requests.Session()
        self.session.headers.update(
            {"User-Agent": cfg.get("user_agent", USER_AGENT), "Accept-Language": "pt-BR,pt;q=0.9", **cfg.get("headers", {})}
        )
        self._cache: dict[str, str] = {}
        self._falhas: dict[str, Exception] = {}  # não insiste na mesma página que já falhou

    @staticmethod
    def _slugs(route: Route) -> tuple[str, str]:
        origem, destino = route.ids_para("buser")
        if not (origem and destino):
            raise ProviderError(
                f"Defina origem_id e destino_id na rota {route.titulo} "
                "(ex.: origem_id = \"niteroi-rj\", destino_id = \"cabo-frio-rj\"; "
                "é o trecho final do endereço da Buser)."
            )
        return origem, destino

    def _baixar(self, url: str) -> str:
        if url in self._cache:
            return self._cache[url]
        if url in self._falhas:
            raise self._falhas[url]
        if self._rede and self.pausa:
            _time.sleep(self.pausa)  # gentileza com o site: só espera antes de uma nova requisição
        self._rede = True
        ultimo: Exception | None = None
        for tentativa in range(3):
            try:
                r = self.session.get(url, timeout=20)
                if r.status_code == 404:
                    raise PaginaNaoEncontrada(f"404 em {url}")
                if r.status_code in (403, 429):
                    raise ErroNaoRepetivel(f"HTTP {r.status_code} em {url}")

                if r.status_code >= 500:
                    raise ProviderError(f"HTTP {r.status_code} em {url}")
                r.raise_for_status()
                self._cache[url] = r.text
                return r.text
            except PaginaNaoEncontrada:
                raise
            except ErroNaoRepetivel as e:
                self._falhas[url] = e
                raise
            except (requests.RequestException, ProviderError) as e:
                ultimo = e
                _time.sleep(2 ** tentativa)
        erro = ProviderError(f"Falha ao baixar {url}: {ultimo}")
        self._falhas[url] = erro
        return self._raise(erro)

    @staticmethod
    def _raise(erro: Exception):
        raise erro

    def search(self, route: Route, day: date) -> list[Trip]:
        origem, destino = self._slugs(route)
        link = f"{BASE}/{origem}/{destino}?ida={day.isoformat()}"
        if self.modo == "dia_da_semana":
            url = f"{BASE}/{DIAS_SLUG[day.weekday()]}/{origem}/{destino}"
            try:
                html = self._baixar(url)
            except PaginaNaoEncontrada:
                log.warning("Página por dia da semana não existe (%s); usando ?ida=", url)
                html = self._baixar(link)
        else:
            html = self._baixar(link)
        return [t for t in parse_pagina(html, day, route, link) if t.data == day]
