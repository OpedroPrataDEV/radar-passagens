from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from itertools import groupby

import requests

from .core import Resultado

DIAS_ABREV = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]


def _brl(valor: float) -> str:
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar(resultados: list[Resultado]) -> str:
    """Monta o texto do aviso, agrupado por rota e por dia."""
    blocos = []
    for res in resultados:
        if not res.viagens:
            continue
        linhas = [f"🚌 {res.rota.titulo} — até {_brl(res.rota.preco_max)}"]
        for dia, viagens in groupby(res.viagens, key=lambda v: v.data):
            linhas.append(f"\n{DIAS_ABREV[dia.weekday()]} {dia:%d/%m}")
            for v in viagens:
                extra = f" — {v.link}" if v.link else ""
                vagas = f" ({v.vagas} vagas)" if v.vagas else ""
                linhas.append(f"  • {v.saida:%H:%M}  {_brl(v.preco)}  {v.empresa}{vagas}{extra}")
        blocos.append("\n".join(linhas))
    return "\n\n".join(blocos)


def enviar_console(texto: str) -> None:
    print(texto)


def enviar_telegram(texto: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for i in range(0, len(texto), 3800):  # limite do Telegram é 4096 por mensagem
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": texto[i : i + 3800], "disable_web_page_preview": True},
            timeout=20,
        )
        r.raise_for_status()
    return True


def enviar_email(texto: str, assunto: str = "Radar de Passagens: achei passagem barata") -> bool:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    senha = os.environ.get("SMTP_PASSWORD")
    destino = os.environ.get("EMAIL_TO", user)
    if not (host and user and senha and destino):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = assunto, user, destino
    msg.set_content(texto)
    with smtplib.SMTP_SSL(host, int(os.environ.get("SMTP_PORT", "465")), timeout=20) as s:
        s.login(user, senha)
        s.send_message(msg)
    return True
