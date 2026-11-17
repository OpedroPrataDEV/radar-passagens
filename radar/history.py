from __future__ import annotations

import sqlite3
from datetime import datetime

from .models import Trip


class Historico:
    """SQLite só para lembrar o que já foi avisado (o histórico de preços vive em registro.py)."""

    def __init__(self, path: str = "radar.db"):
        self.con = sqlite3.connect(path)
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS avisados (chave TEXT PRIMARY KEY, preco REAL, avisado_em TEXT)"
        )

    def novidades(self, viagens: list[Trip]) -> list[Trip]:
        """Só o que é novo ou ficou mais barato desde o último aviso."""
        novas = []
        for v in viagens:
            row = self.con.execute("SELECT preco FROM avisados WHERE chave = ?", (v.chave,)).fetchone()
            if row is None or v.preco < row[0]:
                novas.append(v)
        return novas

    def marcar_avisadas(self, viagens: list[Trip]) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        self.con.executemany(
            "INSERT OR REPLACE INTO avisados VALUES (?,?,?)",
            [(v.chave, v.preco, agora) for v in viagens],
        )
        self.con.commit()

    def fechar(self) -> None:
        self.con.close()
