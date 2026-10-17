import pytest
from src.imar import taban_alani, toplam_insaat_alani, kat_sayisi


def test_taban_alani():
    assert taban_alani(1000, 0.30) == pytest.approx(300)


def test_toplam_insaat_alani():
    assert toplam_insaat_alani(1000, 1.50) == pytest.approx(1500)


def test_kat_sayisi_emsalden():
    # 1.50 / 0.30 = 5 kat
    assert kat_sayisi(0.30, 1.50) == 5


def test_kat_sayisi_asagi_yuvarlanir():
    # 1.40 / 0.30 = 4.67 -> 4 tam kat
    assert kat_sayisi(0.30, 1.40) == 4


def test_kat_sayisi_plan_siniri():
    # emsal 5 kata izin verse de plan 4 kat diyorsa 4
    assert kat_sayisi(0.30, 1.50, max_kat=4) == 4


def test_gecersiz_taks():
    with pytest.raises(ValueError):
        taban_alani(1000, 1.5)  # TAKS 1'den büyük olamaz


def test_negatif_alan():
    with pytest.raises(ValueError):
        toplam_insaat_alani(-100, 1.5)
