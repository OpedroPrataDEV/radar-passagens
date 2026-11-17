from datetime import date, datetime

from radar.models import Route
from radar.providers.json_endpoint import JsonEndpointProvider, get_path, parse_preco, parse_saida

ROTA = Route("Niterói", "Cabo Frio", (3,), 30.0)
CFG = {
    "url": "https://exemplo.com/busca",
    "link": "https://exemplo.com/comprar?d={data}",
    "mapeamento": {
        "lista": "result.trips",
        "horario": "departure",
        "preco": "price",
        "empresa": "company.name",
    },
}


def test_get_path():
    data = {"a": [{"b": 1}, {"b": 2}]}
    assert get_path(data, "a.1.b") == 2
    assert get_path(data, "a.5.b") is None
    assert get_path(data, "x.y") is None


def test_parse_preco():
    assert parse_preco(29.9) == 29.9
    assert parse_preco("R$ 29,90") == 29.9
    assert parse_preco("1.029,90") == 1029.9
    assert parse_preco(2990, divisor=100) == 29.9
    assert parse_preco(None) is None
    assert parse_preco("esgotado") is None


def test_parse_saida():
    dia = date(2026, 11, 19)
    assert parse_saida("06:30", dia) == datetime(2026, 11, 19, 6, 30)
    assert parse_saida("2026-11-19T06:30:00-03:00", dia) == datetime(2026, 11, 19, 6, 30)
    assert parse_saida("lixo", dia) is None


def test_parse_ignora_itens_incompletos():
    data = {
        "result": {
            "trips": [
                {"departure": "2026-11-19T06:30:00", "price": 27.9, "company": {"name": "A"}},
                {"departure": "2026-11-19T08:00:00", "price": None, "company": {"name": "B"}},  # esgotada
                {"price": 20},  # sem horário
            ]
        }
    }
    trips = JsonEndpointProvider(CFG).parse(data, ROTA, date(2026, 11, 19))
    assert len(trips) == 1
    assert trips[0].empresa == "A"
    assert trips[0].link == "https://exemplo.com/comprar?d=2026-11-19"
