import json
from datetime import date, datetime

import pytest

from radar.core import Resultado
from radar.models import Route, Trip
from radar.registro import RegistroPrecos, chave_viagem

ROTA = Route("Niterói", "Cabo Frio", (3,), 30.0)
D1, D2, D3 = date(2026, 11, 14), date(2026, 11, 15), date(2026, 11, 16)


def viagem(dia=date(2026, 11, 19), hora=(7, 20), preco=50.0, empresa="Buser", fonte="buser"):
    return Trip(dia, datetime(dia.year, dia.month, dia.day, *hora), preco, empresa, "Niterói", "Cabo Frio", fonte=fonte)


def res(*viagens, erros=()):
    return Resultado(rota=ROTA, todas=list(viagens), vistas=len(viagens), consultas=1, erros=list(erros))


def test_registra_todas_as_viagens_inclusive_as_caras():
    """Regressão: o histórico antigo só guardava o que cabia no preço máximo (R$ 30)."""
    reg = RegistroPrecos("/tmp/nao-usado.json")
    reg.registrar([res(viagem(preco=21.9), viagem(hora=(10, 20), preco=90.9))], D1)
    precos = sorted(v["p"][0][1] for v in reg.dados["rotas"]["niteroi-cabo-frio"]["viagens"].values())
    assert precos == [21.9, 90.9]


def test_so_guarda_pontos_quando_o_preco_muda_e_atualiza_ate():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    k = chave_viagem(viagem())
    for dia, preco in [(D1, 50.0), (D2, 50.0), (D3, 45.0)]:
        reg.registrar([res(viagem(preco=preco))], dia)
    s = reg.dados["rotas"]["niteroi-cabo-frio"]["viagens"][k]
    assert s["p"] == [["2026-11-14", 50.0], ["2026-11-16", 45.0]]
    assert s["ate"] == "2026-11-16"


def test_duas_coletas_no_mesmo_dia_valem_a_ultima():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    reg.registrar([res(viagem(preco=50.0))], D1)
    reg.registrar([res(viagem(preco=47.0))], D1)
    s = next(iter(reg.dados["rotas"]["niteroi-cabo-frio"]["viagens"].values()))
    assert s["p"] == [["2026-11-14", 47.0]]
    assert len(reg.dados["rotas"]["niteroi-cabo-frio"]["coletas"]) == 1


def test_resumo_diario_da_coleta():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    reg.registrar([res(viagem(preco=20.0), viagem(hora=(9, 0), preco=40.0))], D1)
    assert reg.dados["rotas"]["niteroi-cabo-frio"]["coletas"] == [{"d": "2026-11-14", "n": 2, "min": 20.0, "med": 30.0, "max": 40.0}]


def test_coleta_com_erro_nao_gera_resumo_mas_guarda_as_viagens_lidas():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    reg.registrar([res(viagem(), erros=["buser 2026-11-20: 404"])], D1)
    rota = reg.dados["rotas"]["niteroi-cabo-frio"]
    assert rota["coletas"] == [] and len(rota["viagens"]) == 1


def test_sem_viagens_nao_registra_nada():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    assert reg.registrar([res()], D1) == 0
    assert reg.dados["rotas"] == {} and reg.dados["primeira_coleta"] is None


def test_fontes_diferentes_sao_viagens_diferentes():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    reg.registrar([res(viagem(fonte="buser"), viagem(fonte="outra"))], D1)
    assert len(reg.dados["rotas"]["niteroi-cabo-frio"]["viagens"]) == 2


def test_poda_viagens_muito_antigas():
    reg = RegistroPrecos("/tmp/nao-usado.json")
    antiga = viagem(dia=date(2025, 1, 10))
    reg.registrar([res(antiga)], date(2025, 1, 5))
    reg.registrar([res(viagem())], date(2026, 11, 14))
    chaves = reg.dados["rotas"]["niteroi-cabo-frio"]["viagens"]
    assert chave_viagem(antiga) not in chaves and chave_viagem(viagem()) in chaves


def test_salvar_e_recarregar(tmp_path):
    f = tmp_path / "site" / "historico.json"
    reg = RegistroPrecos(f)
    reg.registrar([res(viagem())], D1)
    reg.salvar()
    assert RegistroPrecos(f).dados == reg.dados
    assert json.loads(f.read_text(encoding="utf-8"))["versao"] == 1
    assert not f.with_suffix(".tmp").exists()


def test_nao_sobrescreve_historico_ilegivel_nem_de_outra_versao(tmp_path):
    f = tmp_path / "h.json"
    f.write_text("{quebrado")
    with pytest.raises(ValueError, match="ilegível"):
        RegistroPrecos(f)
    f.write_text('{"versao": 99}')
    with pytest.raises(ValueError, match="Versão"):
        RegistroPrecos(f)
