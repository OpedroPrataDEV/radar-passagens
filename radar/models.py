from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime

TODOS_OS_DIAS = (0, 1, 2, 3, 4, 5, 6)


def _slug(texto: str) -> str:
    ascii_ = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_.lower()).strip("-")


@dataclass(frozen=True)
class Route:
    origem: str
    destino: str
    dias: tuple[int, ...]          # 0 = segunda ... 6 = domingo (dias de alerta)
    preco_max: float
    origem_id: str | None = None   # atalho: ids da Buser (legado); veja `ids` para outras fontes
    destino_id: str | None = None
    horario_min: str | None = None  # "HH:MM", opcional
    horario_max: str | None = None
    dias_site: tuple[int, ...] = TODOS_OS_DIAS  # dias coletados para o site (alertas usam só `dias`)
    ids: dict = field(default_factory=dict, compare=False, hash=False)  # {"fonte": {"origem": ..., "destino": ...}}

    @property
    def titulo(self) -> str:
        return f"{self.origem} → {self.destino}"

    @property
    def id(self) -> str:
        """Identificador estável da rota, usado no histórico e no site."""
        return f"{_slug(self.origem)}-{_slug(self.destino)}"

    def ids_para(self, fonte: str) -> tuple[str | None, str | None]:
        """Identificadores de origem/destino que a `fonte` usa para esta rota."""
        par = self.ids.get(fonte)
        if par:
            return par.get("origem"), par.get("destino")
        if fonte == "buser":
            return self.origem_id, self.destino_id
        return None, None


@dataclass(frozen=True)
class Trip:
    data: date
    saida: datetime
    preco: float
    empresa: str                    # viação/operadora
    origem: str
    destino: str
    link: str = ""
    vagas: int | None = None
    fonte: str = "buser"            # plataforma de onde veio o dado

    @property
    def chave(self) -> str:
        """Identifica a viagem (sem o preço) para evitar avisos repetidos."""
        return f"{self.fonte}|{self.origem}|{self.destino}|{self.saida.isoformat()}|{self.empresa}"
