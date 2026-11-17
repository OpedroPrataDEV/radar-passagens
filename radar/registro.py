from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from statistics import fmean

from .core import Resultado
from .models import Trip

VERSAO = 1
GUARDAR_APOS_SAIDA = 365  # dias que uma viagem já realizada continua no histórico


def chave_viagem(v: Trip) -> str:
    """Mesma chave que o site usa: fonte|AAAA-MM-DDTHH:MM|empresa."""
    return f"{v.fonte}|{v.saida.strftime('%Y-%m-%dT%H:%M')}|{v.empresa}"


class RegistroPrecos:
    """Histórico real de preços, em um JSON versionado (a fonte única do histórico).

    Por viagem guarda só os dias em que o preço MUDOU (`p`) e o último dia em que foi vista (`ate`);
    o site reconstrói o preço de cada dia a partir disso. Nada é inventado: dia sem coleta fica sem ponto.
    """

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)
        self.dados = self._carregar()

    def _carregar(self) -> dict:
        if not self.caminho.exists():
            return {"versao": VERSAO, "primeira_coleta": None, "atualizado_em": None, "rotas": {}}
        try:
            dados = json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            # nunca sobrescreve em silêncio um histórico que não conseguiu ler
            raise ValueError(f"Histórico ilegível em {self.caminho}: {e}") from e
        if dados.get("versao") != VERSAO:
            raise ValueError(f"Versão de histórico não suportada: {dados.get('versao')!r}")
        return dados

    def registrar(self, resultados: list[Resultado], hoje: date) -> int:
        """Registra TODAS as viagens futuras observadas (sem filtro de preço). Devolve quantas viagens viu."""
        dia = hoje.isoformat()
        vistas = 0
        for res in resultados:
            if not res.todas:
                continue  # nada lido (falha ou rota sem viagens): não registra coleta vazia
            rota = self.dados["rotas"].setdefault(res.rota.id, {"titulo": res.rota.titulo, "coletas": [], "viagens": {}})
            for v in res.todas:
                self._viagem(rota["viagens"], chave_viagem(v), v.preco, dia)
            if not res.erros:  # coleta incompleta não vira resumo do dia
                self._coleta(rota["coletas"], [v.preco for v in res.todas], dia)
            self._podar(rota, hoje)
            vistas += len(res.todas)
        if vistas:
            self.dados["primeira_coleta"] = self.dados["primeira_coleta"] or dia
            self.dados["atualizado_em"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return vistas

    @staticmethod
    def _viagem(viagens: dict, chave: str, preco: float, dia: str) -> None:
        s = viagens.setdefault(chave, {"p": [], "ate": dia})
        p = s["p"]
        if not p:
            p.append([dia, preco])
        elif p[-1][1] != preco:
            if p[-1][0] == dia:
                p[-1][1] = preco  # duas coletas no mesmo dia: vale a última
            else:
                p.append([dia, preco])
        s["ate"] = max(s["ate"], dia)

    @staticmethod
    def _coleta(coletas: list, precos: list[float], dia: str) -> None:
        entrada = {"d": dia, "n": len(precos), "min": min(precos), "med": round(fmean(precos), 2), "max": max(precos)}
        if coletas and coletas[-1]["d"] == dia:
            coletas[-1] = entrada
        else:
            coletas.append(entrada)

    @staticmethod
    def _podar(rota: dict, hoje: date) -> None:
        limite = (hoje - timedelta(days=GUARDAR_APOS_SAIDA)).isoformat()
        for chave in [k for k in rota["viagens"] if k.split("|")[1][:10] < limite]:
            del rota["viagens"][chave]

    def salvar(self) -> None:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.caminho.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.dados, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(self.caminho)  # gravação atômica
