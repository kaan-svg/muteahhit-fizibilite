import pytest
from src.maliyet import konut_sinifi, insaat_maliyeti


@pytest.mark.parametrize("kat, yukseklik, beklenen", [
    (3, None, "III-A"),    # uc kata kadar
    (5, None, "III-B"),    # 5 x 3 = 15 m
    (8, None, "III-C"),    # 8 x 3 = 24 m
    (12, None, "IV-A"),    # 12 x 3 = 36 m
    (20, None, "IV-B"),    # 20 x 3 = 60 m
    (7, 21.50, "III-C"),   # 21.50 tam sinirda -> ust sinif
    (7, 21.49, "III-B"),
])
def test_konut_sinifi(kat, yukseklik, beklenen):
    assert konut_sinifi(kat, yukseklik) == beklenen


def test_insaat_maliyeti_resmi_deger():
    # 1500 m2 x 21.050 TL = 31.575.000 TL
    assert insaat_maliyeti(1500, "III-B") == pytest.approx(31_575_000)


def test_insaat_maliyeti_piyasa_carpani():
    assert insaat_maliyeti(1500, "III-B", piyasa_carpani=1.2) == pytest.approx(37_890_000)


def test_insaat_maliyeti_dogrudan_birim():
    # birim maliyet verilirse sinif yok sayilir
    assert insaat_maliyeti(1000, "III-B", birim_maliyet=30_000) == pytest.approx(30_000_000)


def test_bilinmeyen_sinif():
    with pytest.raises(ValueError):
        insaat_maliyeti(1000, "X-Z")


def test_gecersiz_kat():
    with pytest.raises(ValueError):
        konut_sinifi(0)
