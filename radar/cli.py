from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

from . import notifiers
from .config import load_config
from .core import buscar
from .dates import datas_da_janela
from .exportar import exportar_json
from .history import Historico
from .providers import criar_provedor
from .registro import RegistroPrecos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="radar", description="Radar de Passagens")
    p.add_argument("-c", "--config", default="config.toml")
    p.add_argument("--provedor", help="sobrescreve os provedores do config (ex: mock)")
    p.add_argument("--datas", action="store_true", help="só mostra quais datas seriam consultadas")
    p.add_argument("--tudo", action="store_true", help="mostra tudo, ignorando o que já foi avisado")
    p.add_argument("--sem-aviso", action="store_true", help="não envia Telegram/e-mail (só imprime)")
    p.add_argument("--exportar", metavar="ARQUIVO", help="grava os dados atuais para o site (ex.: site/dados.json)")
    p.add_argument("--historico", metavar="ARQUIVO", help="registra o histórico real de preços (ex.: site/historico.json)")
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING, format="%(message)s")
    cfg = load_config(args.config)

    if args.datas:
        for r in cfg.rotas:
            ds = datas_da_janela(r.dias, date.today(), cfg.janela_dias)
            print(f"{r.titulo}: " + ", ".join(f"{d:%d/%m}" for d in ds))
        return 0

    nomes = [args.provedor] if args.provedor else cfg.provedores
    try:
        provedores = []
        for nome in nomes:
            cfg_prov = {} if args.provedor else dict(cfg.provedores_cfg.get(nome, {}))
            if nome == "buser":
                cfg_prov.setdefault("pausa_segundos", cfg.pausa_segundos)  # o provedor controla a pausa
            provedores.append(criar_provedor(nome, cfg_prov))
    except ValueError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2

    demo = "mock" in nomes
    pausa = 0.0 if set(nomes) <= {"buser"} else cfg.pausa_segundos
    resultados = buscar(cfg.rotas, provedores, cfg.janela_dias, pausa=pausa)

    lidas = sum(r.vistas for r in resultados)
    if args.exportar:
        if lidas == 0:
            print("(nenhuma viagem lida: dados do site não alterados)")  # nunca sobrescreve com lista vazia
        else:
            exportar_json(resultados, args.exportar, demo=demo)
    if args.historico:
        if demo:
            print("(provedor mock: histórico não gravado, para não misturar dados de teste com dados reais)")
        elif lidas == 0:
            print("(nenhuma viagem lida: histórico não alterado)")
        else:
            reg = RegistroPrecos(args.historico)
            reg.registrar(resultados, date.today())
            reg.salvar()

    hist = Historico(cfg.db_path)
    try:
        todas = [v for r in resultados for v in r.viagens]

        if not args.tudo:
            novas = {v.chave for v in hist.novidades(todas)}
            for r in resultados:
                r.viagens = [v for v in r.viagens if v.chave in novas]

        texto = notifiers.formatar(resultados)
        consultas = sum(r.consultas for r in resultados)
        erros = sum(len(r.erros) for r in resultados)

        if texto:
            notifiers.enviar_console(texto)
            if not args.sem_aviso and not args.tudo:
                enviou = notifiers.enviar_telegram(texto) | notifiers.enviar_email(texto)
                if not enviou:
                    print("\n(Telegram/e-mail não configurados: aviso só no terminal.)")
                hist.marcar_avisadas([v for r in resultados for v in r.viagens])
        elif not (consultas and erros == consultas):
            print("Nenhuma passagem nova dentro do seu preço desta vez.")

        vistas = sum(r.vistas for r in resultados)
        if consultas and not erros and vistas == 0:
            print(
                "\nERRO: as consultas funcionaram mas nenhuma viagem foi lida. A página pode ter mudado "
                "ou exigir JavaScript; abra a URL no navegador e compare.",
                file=sys.stderr,
            )
            return 2
        if consultas and erros == consultas:
            print(
                "\nERRO: todas as consultas falharam (site fora do ar, bloqueio ou página mudou). Veja as mensagens acima.",
                file=sys.stderr,
            )
            return 2
        if erros:
            print(f"\nAviso: {erros} de {consultas} consultas falharam.", file=sys.stderr)
        return 0
    finally:
        hist.fechar()
