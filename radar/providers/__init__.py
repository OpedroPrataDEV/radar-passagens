from __future__ import annotations

from .base import Provider
from .buser import BuserProvider
from .json_endpoint import JsonEndpointProvider
from .mock import MockProvider

# Fontes sem integração: só entram aqui com API oficial, parceria ou autorização (veja docs/NOVO_PROVEDOR.md).
NAO_IMPLEMENTADOS = {
    "clickbus": "ClickBus ainda não tem integração: não há API pública para desenvolvedores confirmada. "
                "Veja docs/NOVO_PROVEDOR.md para o que seria necessário.",
}


def criar_provedor(nome: str, cfg: dict | None = None) -> Provider:
    cfg = cfg or {}
    if nome == "mock":
        return MockProvider()
    if nome == "buser":
        return BuserProvider(cfg)
    if nome == "json":
        return JsonEndpointProvider(cfg)
    if nome in NAO_IMPLEMENTADOS:
        raise ValueError(NAO_IMPLEMENTADOS[nome])
    raise ValueError(f"Provedor desconhecido: {nome!r} (disponíveis: buser, json, mock)")
