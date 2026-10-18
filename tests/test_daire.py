import pytest
from src.daire import kullanilabilir_alan, daire_dagilimi

BOYUT = {"1+1": 50, "2+1": 100}


def test_kullanilabilir_alan():
    # 1000 m2'nin %15'i ortak alan -> 850 m2
    assert kullanilabilir_alan(1000, 0.15) == pytest.approx(850)


def test_ortak_alan_orani_gecersiz():
    with pytest.raises(ValueError):
        kullanilabilir_alan(1000, 1.2)


def test_tek_tip():
    # 1000 m2 tamamen 2+1 (100 m2) -> 10 daire, artan yok
    s = daire_dagilimi(1000, {"2+1": 1.0}, BOYUT)
    assert s["adetler"] == {"2+1": 10}
    assert s["artan_alan"] == pytest.approx(0)


def test_karisik_dagilim():
    # 1000 m2: %40 1+1 -> 400/50 = 8 ; %60 2+1 -> 600/100 = 6
    s = daire_dagilimi(1000, {"1+1": 0.4, "2+1": 0.6}, BOYUT)
    assert s["adetler"] == {"1+1": 8, "2+1": 6}
    assert s["kullanilan_alan"] == pytest.approx(1000)


def test_artan_alan_hesaplanir():
    # 1030 m2 tamamen 2+1 -> 10 daire, 30 m2 artar
    s = daire_dagilimi(1030, {"2+1": 1.0}, BOYUT)
    assert s["adetler"] == {"2+1": 10}
    assert s["artan_alan"] == pytest.approx(30)


def test_oranlar_toplami_1_olmali():
    with pytest.raises(ValueError):
        daire_dagilimi(1000, {"1+1": 0.5, "2+1": 0.3}, BOYUT)


def test_tanimsiz_tip():
    with pytest.raises(ValueError):
        daire_dagilimi(1000, {"4+1": 1.0}, BOYUT)


def test_varsayilan_buyuklukler_kullanilir():
    # 950 m2 tamamen 2+1, varsayilan 95 m2 -> 10 daire
    s = daire_dagilimi(950, {"2+1": 1.0})
    assert s["adetler"] == {"2+1": 10}
