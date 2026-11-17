import json
from datetime import date, datetime

import pytest

from radar import cli
from radar.config import load_config
from radar.core import buscar
from radar.models import Route, Trip
from radar.providers import criar_provedor
from radar.providers.mock import MockProvider

HOJE, AGORA = date(2026, 11, 13), datetime(2026, 11, 13, 10, 0)


def test_rota_id_e_ids_por_fonte():
    r = Route("Niterói", "Cabo Frio", (3,), 30.0, origem_id="niteroi-rj", destino_id="cabo-frio-rj",
              ids={"clickbus": {"origem": "X1", "destino": "Y2"}})
    assert r.id == "niteroi-cabo-frio"
    assert r.ids_para("buser") == ("niteroi-rj", "cabo-frio-rj")   # atalho legado
    assert r.ids_para("clickbus") == ("X1", "Y2")
    assert r.ids_para("outra") == (None, None)


def test_config_le_ids_e_lista_de_provedores(tmp_path):
    f = tmp_path / "c.toml"
    f.write_text('''
[provedor]
nome = ["buser", "mock"]
[provedor.buser]
modo = "por_data"
[[rota]]
origem = "A"
destino = "B"
dias = ["quinta"]
preco_max = 30
ids = { buser = { origem = "a-rj", destino = "b-rj" } }
''')
    cfg = load_config(f)
    assert cfg.provedores == ["buser", "mock"] and cfg.provedores_cfg["buser"] == {"modo": "por_data"}
    assert cfg.rotas[0].ids_para("buser") == ("a-rj", "b-rj")


def test_provedor_nao_implementado_explica_o_motivo():
    with pytest.raises(ValueError, match="ClickBus"):
        criar_provedor("clickbus")
    with pytest.raises(ValueError, match="desconhecido"):
        criar_provedor("naoexiste")


def test_varios_provedores_juntam_resultados_e_marcam_a_fonte():
    class Outra:
        nome = "outra"

        def search(self, route, day):
            return [Trip(day, datetime(day.year, day.month, day.day, 6, 0), 19.9, "Viação Y", route.origem, route.destino, fonte="outra")]

    rota = Route("Niterói", "Cabo Frio", (3,), 30.0, dias_site=(3,))
    [res] = buscar([rota], [MockProvider(), Outra()], 30, hoje=HOJE, agora=AGORA)
    assert res.consultas == 8                      # 4 quintas × 2 fontes
    assert {v.fonte for v in res.todas} == {"mock", "outra"}
    assert any(v.fonte == "outra" and v.preco == 19.9 for v in res.viagens)


def test_falha_de_uma_fonte_nao_derruba_a_outra():
    class Quebrada:
        nome = "quebrada"

        def search(self, route, day):
            raise RuntimeError("fora do ar")

    rota = Route("A", "B", (3,), 30.0, dias_site=(3,))
    [res] = buscar([rota], [Quebrada(), MockProvider()], 30, hoje=HOJE, agora=AGORA)
    assert res.todas and all(e.startswith("quebrada") for e in res.erros)


def test_cli_ponta_a_ponta_exporta_e_registra_historico(tmp_path, monkeypatch):
    cfg = tmp_path / "c.toml"
    db_path = (tmp_path / "radar.db").as_posix()

    cfg.write_text(f'''
[busca]
db_path = "{db_path}"
pausa_segundos = 0
[provedor]
nome = "buser"
[[rota]]
origem = "Niterói"
destino = "Cabo Frio"
dias = ["quinta"]
dias_site = ["quinta"]
preco_max = 30
''', encoding="utf-8")

    monkeypatch.setattr(cli, "criar_provedor", lambda nome, cfg=None: MockProvider())
    dados, hist = tmp_path / "site" / "dados.json", tmp_path / "site" / "historico.json"

    assert cli.main(["-c", str(cfg), "--sem-aviso", "--exportar", str(dados), "--historico", str(hist)]) == 0

    d = json.loads(dados.read_text(encoding="utf-8"))
    h = json.loads(hist.read_text(encoding="utf-8"))

    assert d["demo"] is False and d["rotas"][0]["id"] == "niteroi-cabo-frio"
    assert len(h["rotas"]["niteroi-cabo-frio"]["viagens"]) == len(d["rotas"][0]["viagens"]) > 0


def test_cli_com_mock_nao_grava_historico(tmp_path):
    cfg = tmp_path / "c.toml"
    db_path = (tmp_path / "r.db").as_posix()

    cfg.write_text(
        f'''[busca]
db_path = "{db_path}"
pausa_segundos = 0

[[rota]]
origem = "A"
destino = "B"
dias = ["quinta"]
dias_site = ["quinta"]
preco_max = 30
''',
        encoding="utf-8",
    )

    hist, dados = tmp_path / "h.json", tmp_path / "d.json"

    assert cli.main([
        "-c", str(cfg),
        "--provedor", "mock",
        "--sem-aviso",
        "--exportar", str(dados),
        "--historico", str(hist),
    ]) == 0

    assert not hist.exists()
    assert json.loads(dados.read_text(encoding="utf-8"))["demo"] is True


def test_cli_provedor_inexistente_da_erro_limpo(tmp_path, capsys):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[provedor]\nnome = "clickbus"\n[[rota]]\norigem="A"\ndestino="B"\ndias=["quinta"]\npreco_max=30\n')
    assert cli.main(["-c", str(cfg)]) == 2
    assert "ClickBus" in capsys.readouterr().err


def test_cli_sem_viagens_nao_sobrescreve_dados_do_site(tmp_path, monkeypatch):
    class Vazio:
        nome = "vazio"

        def search(self, route, day):
            return []

    cfg = tmp_path / "c.toml"
    db_path = (tmp_path / "r.db").as_posix()

    cfg.write_text(
        f'''[busca]
db_path = "{db_path}"
pausa_segundos = 0

[[rota]]
origem = "A"
destino = "B"
dias = ["quinta"]
dias_site = ["quinta"]
preco_max = 30
''',
        encoding="utf-8",
    )

    dados = tmp_path / "d.json"
    dados.write_text('{"versao": 2, "bom": true}', encoding="utf-8")

    monkeypatch.setattr(cli, "criar_provedor", lambda nome, cfg=None: Vazio())

    cli.main(["-c", str(cfg), "--provedor", "vazio", "--sem-aviso", "--exportar", str(dados)])

    assert dados.read_text(encoding="utf-8") == '{"versao": 2, "bom": true}'
