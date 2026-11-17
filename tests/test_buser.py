from datetime import date
from pathlib import Path

import pytest

from radar.models import Route
from radar.providers.buser import (
    BuserProvider,
    ErroNaoRepetivel,
    PaginaNaoEncontrada,
    ProviderError,
    parse_pagina,
)
HTML = (Path(__file__).parent / "fixtures" / "buser_quinta.html").read_text(encoding="utf-8")
ROTA = Route("Niterói", "Cabo Frio", (3,), 30.0, origem_id="niteroi-rj", destino_id="cabo-frio-rj", dias_site=(3,))
LINK = "https://www.buser.com.br/onibus/niteroi-rj/cabo-frio-rj?ida=2026-11-19"


def test_le_todas_as_viagens_com_preco():
    trips = parse_pagina(HTML, date(2026, 11, 19), ROTA, LINK)
    resumo = sorted((t.data.isoformat(), t.saida.strftime("%H:%M"), t.preco) for t in trips)
    assert resumo == [
        ("2026-11-19", "07:20", 39.90),   # a parcela "3x R$ 14,79" não vira preço
        ("2026-11-19", "10:20", 29.90),
        ("2026-11-19", "22:40", 24.90),   # a data de chegada (20/11) não vira uma 2ª viagem
        ("2026-11-26", "07:20", 27.90),   # "R$&nbsp;27,90"
        ("2026-12-03", "07:20", 35.90),
    ]


def test_ignora_esgotada_e_precos_de_script_e_rodape():
    trips = parse_pagina(HTML, date(2026, 11, 19), ROTA, LINK)
    assert all(t.saida.strftime("%H:%M") != "17:35" for t in trips)
    assert all(t.preco not in (1.0, 2.0, 61.06, 34.9, 104.9) for t in trips)


def test_vagas():
    trips = {t.saida.strftime("%d/%m %H:%M"): t for t in parse_pagina(HTML, date(2026, 11, 19), ROTA, LINK)}
    assert trips["19/11 10:20"].vagas == 2
    assert trips["19/11 07:20"].vagas == 13


def test_deduz_virada_de_ano():
    html = HTML.replace("26 de novembro", "07 de janeiro").replace("26/11", "07/01")
    trips = parse_pagina(html, date(2026, 12, 31), ROTA, LINK)
    assert date(2027, 1, 7) in {t.data for t in trips}


def test_layout_quebrado_gera_erro_claro():
    with pytest.raises(ProviderError, match="layout"):
        parse_pagina("<html><body><p>Preço R$ 50,90 sem estrutura</p></body></html>", date(2026, 11, 19), ROTA, LINK)


def test_pagina_sem_preco_nenhum_devolve_vazio():
    assert parse_pagina("<html><body>Nenhum horário</body></html>", date(2026, 11, 19), ROTA, LINK) == []


class FakeResp:
    def __init__(self, status=200, text=""):
        self.status_code, self.text = status, text

    def raise_for_status(self):
        pass


class FakeSession:
    def __init__(self, respostas):
        self.headers, self.respostas, self.urls = {}, respostas, []

    def get(self, url, timeout=0):
        self.urls.append(url)
        return self.respostas[url] if url in self.respostas else FakeResp(404)


def test_modo_dia_da_semana_faz_uma_requisicao_para_varias_datas():
    url = "https://www.buser.com.br/onibus/quinta-feira/niteroi-rj/cabo-frio-rj"
    sess = FakeSession({url: FakeResp(200, HTML)})
    prov = BuserProvider({}, session=sess)
    a = prov.search(ROTA, date(2026, 11, 19))
    b = prov.search(ROTA, date(2026, 11, 26))
    assert [t.preco for t in a] == [39.90, 29.90, 24.90]
    assert [t.preco for t in b] == [27.90]
    assert sess.urls == [url]  # cache: a 2ª data não baixa de novo
    assert all(t.data == date(2026, 11, 19) for t in a)
    assert a[0].link.endswith("?ida=2026-11-19")


def test_fallback_para_ida_quando_pagina_do_dia_nao_existe():
    ida = "https://www.buser.com.br/onibus/niteroi-rj/cabo-frio-rj?ida=2026-11-19"
    sess = FakeSession({ida: FakeResp(200, HTML)})
    trips = BuserProvider({}, session=sess).search(ROTA, date(2026, 11, 19))
    assert len(trips) == 3
    assert sess.urls[-1] == ida


def test_exige_slugs():
    with pytest.raises(ProviderError, match="origem_id"):
        BuserProvider({}, session=FakeSession({})).search(Route("A", "B", (3,), 30.0), date(2026, 11, 19))


def test_fluxo_completo_com_o_motor():
    """Rota + provedor Buser + filtro de R$ 30: só as passagens baratas das quintas."""
    from datetime import datetime

    from radar.core import buscar

    url = "https://www.buser.com.br/onibus/quinta-feira/niteroi-rj/cabo-frio-rj"
    prov = BuserProvider({}, session=FakeSession({url: FakeResp(200, HTML)}))
    [res] = buscar([ROTA], prov, 30, hoje=date(2026, 11, 13), agora=datetime(2026, 11, 13, 12, 0))
    achados = [(v.data.isoformat(), v.saida.strftime("%H:%M"), v.preco) for v in res.viagens]
    assert achados == [
        ("2026-11-19", "10:20", 29.90),
        ("2026-11-19", "22:40", 24.90),
        ("2026-11-26", "07:20", 27.90),
    ]
    assert res.vistas == 5 and not res.erros
@pytest.mark.parametrize("status", [403, 429])
def test_nao_repete_requisicao_quando_acesso_e_bloqueado(status):
    url = "https://www.buser.com.br/onibus/quinta-feira/niteroi-rj/cabo-frio-rj"

    sess = FakeSession({url: FakeResp(status)})
    prov = BuserProvider({}, session=sess)

    with pytest.raises(ErroNaoRepetivel, match=f"HTTP {status}"):
        prov.search(ROTA, date(2026, 11, 19))

    assert len(sess.urls) == 1