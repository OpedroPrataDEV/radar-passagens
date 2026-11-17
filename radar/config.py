from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .models import Route

DIAS_SEMANA = {
    "segunda": 0, "segunda-feira": 0, "monday": 0,
    "terca": 1, "terça": 1, "terca-feira": 1, "terça-feira": 1, "tuesday": 1,
    "quarta": 2, "quarta-feira": 2, "wednesday": 2,
    "quinta": 3, "quinta-feira": 3, "thursday": 3,
    "sexta": 4, "sexta-feira": 4, "friday": 4,
    "sabado": 5, "sábado": 5, "saturday": 5,
    "domingo": 6, "sunday": 6,
}


@dataclass
class Config:
    janela_dias: int = 30
    pausa_segundos: float = 2.0
    db_path: str = "radar.db"
    provedores: list[str] = field(default_factory=lambda: ["mock"])
    provedores_cfg: dict = field(default_factory=dict)  # {"nome": {config do provedor}}
    rotas: list[Route] = field(default_factory=list)


def parse_dia(valor: str | int) -> int:
    if isinstance(valor, int):
        if 0 <= valor <= 6:
            return valor
        raise ValueError(f"Dia da semana inválido: {valor}")
    chave = valor.strip().lower()
    if chave not in DIAS_SEMANA:
        raise ValueError(f"Dia da semana desconhecido: {valor!r}")
    return DIAS_SEMANA[chave]


def load_config(path: str | Path) -> Config:
    with open(path, "rb") as f:
        raw = tomllib.load(f)

    busca = raw.get("busca", {})
    prov = raw.get("provedor", {})
    nomes = prov.get("nome", "mock")
    nomes = [nomes] if isinstance(nomes, str) else list(nomes)

    def dias_site(r: dict) -> tuple[int, ...]:
        v = r.get("dias_site", "todos")
        if v == "todos":
            return (0, 1, 2, 3, 4, 5, 6)
        return tuple(parse_dia(d) for d in v)

    rotas = []
    for r in raw.get("rota", []):
        rotas.append(
            Route(
                origem=r["origem"],
                destino=r["destino"],
                dias=tuple(parse_dia(d) for d in r["dias"]),
                preco_max=float(r["preco_max"]),
                origem_id=r.get("origem_id"),
                destino_id=r.get("destino_id"),
                horario_min=r.get("horario_min"),
                horario_max=r.get("horario_max"),
                dias_site=dias_site(r),
                ids={fonte: dict(par) for fonte, par in r.get("ids", {}).items()},
            )
        )
    if not rotas:
        raise ValueError("Configure ao menos uma [[rota]] no config.toml")

    return Config(
        janela_dias=int(busca.get("janela_dias", 30)),
        pausa_segundos=float(busca.get("pausa_segundos", 2.0)),
        db_path=busca.get("db_path", "radar.db"),
        provedores=nomes,
        provedores_cfg={n: prov.get(n, {}) for n in nomes},
        rotas=rotas,
    )
