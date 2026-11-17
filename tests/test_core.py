from datetime import date, datetime

from radar.core import buscar
from radar.history import Historico
from radar.models import Route
from radar.notifiers import formatar
from radar.providers.mock import MockProvider

HOJE = date(2026, 11, 13)
AGORA = datetime(2026, 11, 13, 10, 0)


def rota(**kw):
    base = dict(origem="Niterói", destino="Cabo Frio", dias=(3,), preco_max=30.0, dias_site=(3,))
    return Route(**{**base, **kw})


def test_so_devolve_viagens_dentro_do_preco_e_nos_dias_certos():
    [res] = buscar([rota()], MockProvider(), 30, hoje=HOJE, agora=AGORA)
    assert res.consultas == 4
    assert res.viagens, "o mock deveria gerar ao menos uma passagem <= R$ 30"
    assert all(v.preco <= 30 and v.data.weekday() == 3 for v in res.viagens)


def test_filtro_de_horario():
    [res] = buscar([rota(horario_min="09:00", horario_max="19:00")], MockProvider(), 30, hoje=HOJE, agora=AGORA)
    assert all("09:00" <= v.saida.strftime("%H:%M") <= "19:00" for v in res.viagens)


def test_ignora_viagens_que_ja_sairam():
    [res] = buscar([rota(dias=(4,))], MockProvider(), 0, hoje=HOJE, agora=datetime(2026, 11, 13, 23, 0))
    assert res.viagens == []


def test_erro_em_um_dia_nao_derruba_os_outros():
    class Falha:
        n = 0

        def search(self, route, day):
            self.n += 1
            if self.n == 1:
                raise RuntimeError("bloqueado")
            return MockProvider().search(route, day)

    [res] = buscar([rota()], Falha(), 30, hoje=HOJE, agora=AGORA)
    assert len(res.erros) == 1
    assert res.viagens


def test_historico_so_avisa_novidade_ou_queda_de_preco(tmp_path):
    [res] = buscar([rota()], MockProvider(), 30, hoje=HOJE, agora=AGORA)
    h = Historico(str(tmp_path / "t.db"))
    assert h.novidades(res.viagens) == res.viagens
    h.marcar_avisadas(res.viagens)
    assert h.novidades(res.viagens) == []
    mais_barata = type(res.viagens[0])(**{**res.viagens[0].__dict__, "preco": res.viagens[0].preco - 1})
    assert h.novidades([mais_barata]) == [mais_barata]


def test_formatar_mensagem():
    [res] = buscar([rota()], MockProvider(), 30, hoje=HOJE, agora=AGORA)
    texto = formatar([res])
    assert "Niterói → Cabo Frio" in texto and "R$" in texto and "qui" in texto


def test_exportar_json_para_o_site(tmp_path):
    import json

    from radar.exportar import exportar_json

    resultados = buscar([rota()], MockProvider(), 30, hoje=HOJE, agora=AGORA)
    destino = tmp_path / "site" / "dados.json"
    exportar_json(resultados, str(destino))
    dados = json.loads(destino.read_text(encoding="utf-8"))
    r = dados["rotas"][0]
    assert r["origem"] == "Niterói" and r["dias"] == [3] and r["preco_max"] == 30.0
    assert len(r["viagens"]) == 4 * 7  # sem filtro de preço: o site filtra
    assert set(r["viagens"][0]) == {"fonte", "data", "hora", "preco", "vagas", "empresa", "link"}
    assert dados["versao"] == 2 and r["id"] == "niteroi-cabo-frio" and dados["fontes"] == ["mock"]


def test_coleta_todos_os_dias_para_o_site_mas_avisa_so_nos_dias_escolhidos():
    [res] = buscar([rota(dias_site=(0, 1, 2, 3, 4, 5, 6))], MockProvider(), 30, hoje=HOJE, agora=AGORA)
    assert res.consultas == 31                                  # todos os dias da janela
    assert {v.data.weekday() for v in res.todas} == set(range(7))   # o site recebe tudo
    assert {v.data.weekday() for v in res.viagens} == {3}           # o alerta só vale para quinta


def test_config_dias_site(tmp_path):
    from radar.config import load_config

    f = tmp_path / "c.toml"
    f.write_text('[[rota]]\norigem="A"\ndestino="B"\ndias=["quinta"]\npreco_max=30\n')
    assert load_config(f).rotas[0].dias_site == (0, 1, 2, 3, 4, 5, 6)
    f.write_text('[[rota]]\norigem="A"\ndestino="B"\ndias=["quinta"]\ndias_site=["quinta","sexta"]\npreco_max=30\n')
    assert load_config(f).rotas[0].dias_site == (3, 4)
