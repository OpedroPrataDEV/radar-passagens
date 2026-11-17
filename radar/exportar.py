from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .core import Resultado

VERSAO = 2


def exportar_json(resultados: list[Resultado], caminho: str, demo: bool = False) -> None:
    """Grava o que o site precisa: todas as viagens futuras de cada rota (o filtro de preço é feito no site)."""
    dados = {
        "versao": VERSAO,
        "atualizado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fontes": sorted({v.fonte for r in resultados for v in r.todas}),
        "demo": demo,
        "rotas": [
            {
                "id": r.rota.id,
                "origem": r.rota.origem,
                "destino": r.rota.destino,
                "dias": list(r.rota.dias),
                "preco_max": r.rota.preco_max,
                "horario_min": r.rota.horario_min,
                "horario_max": r.rota.horario_max,
                "viagens": [
                    {"fonte": v.fonte, "data": v.data.isoformat(), "hora": v.saida.strftime("%H:%M"),
                     "preco": v.preco, "vagas": v.vagas, "empresa": v.empresa, "link": v.link}
                    for v in sorted(r.todas, key=lambda v: (v.saida, v.preco))
                ],
            }
            for r in resultados
        ],
    }
    destino = Path(caminho)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
