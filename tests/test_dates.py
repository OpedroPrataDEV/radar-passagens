from datetime import date

from radar.config import parse_dia
from radar.dates import datas_da_janela


def test_quintas_de_novembro_2026():
    # 13/11/2026 é sexta; as quintas dos próximos 30 dias são 19/11, 26/11, 03/12, 10/12
    ds = datas_da_janela((3,), date(2026, 11, 13), 30)
    assert ds == [date(2026, 11, 19), date(2026, 11, 26), date(2026, 12, 3), date(2026, 12, 10)]


def test_inclui_hoje_se_cair_no_dia():
    assert datas_da_janela((3,), date(2026, 11, 12), 0) == [date(2026, 11, 12)]


def test_varios_dias():
    ds = datas_da_janela((3, 6), date(2026, 11, 13), 7)
    assert [d.weekday() for d in ds] == [6, 3]  # sexta 13/11 -> domingo 15/11, quinta 19/11


def test_parse_dia():
    assert parse_dia("Quinta") == 3
    assert parse_dia("quinta-feira") == 3
    assert parse_dia("sábado") == 5
