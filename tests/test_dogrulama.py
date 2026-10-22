"""Hatali girdilerin yakalandigini ve sonuclarin mantikli davrandigini test eder."""
import pytest

from src.daire import daire_dagilimi, kullanilabilir_alan
from src.gelir import m2_fiyati, satis_geliri
from src.maliyet import insaat_maliyeti, konut_sinifi
from src.senaryo import fizibilite

BOYUT = {"1+1": 50}


@pytest.mark.parametrize("cagri", [
    lambda: kullanilabilir_alan(0),
    lambda: kullanilabilir_alan(100, ortak_alan_orani=1.0),
    lambda: daire_dagilimi(0, {"1+1": 1.0}, BOYUT),
    lambda: daire_dagilimi(100, {}, BOYUT),
    lambda: daire_dagilimi(100, {"1+1": 1.5, "2+1": -0.5}, {"1+1": 50, "2+1": 90}),
    lambda: daire_dagilimi(100, {"1+1": 1.0}, {"1+1": 0}),
    lambda: konut_sinifi(5, yapi_yuksekligi=0),
    lambda: insaat_maliyeti(0, "III-B"),
    lambda: insaat_maliyeti(100, "III-B", piyasa_carpani=0),
    lambda: insaat_maliyeti(100, "III-B", birim_maliyet=-1),
    lambda: satis_geliri({"1+1": 1}, BOYUT, -1),
    lambda: satis_geliri({"1+1": -1}, BOYUT, 1000),
], ids=[
    "alan-sifir", "ortak-oran-1", "dagilim-alan-sifir", "oran-bos",
    "oran-negatif", "buyukluk-sifir", "yukseklik-sifir", "maliyet-alan-sifir",
    "carpan-sifir", "birim-negatif", "fiyat-negatif", "adet-negatif",
])
def test_gecersiz_girdi_hata_verir(cagri):
    with pytest.raises(ValueError):
        cagri()


def test_varsayilan_pazar_dosyasindan_fiyat():
    assert m2_fiyati("Mahmutlar") > 0


TEMEL = dict(arsa_alani=1000, taks=0.30, emsal=1.50, mahalle="x",
             oranlar={"2+1": 1.0}, m2_fiyat=50_000, birim_maliyet=20_000)


def test_arsa_sahibi_payi_artinca_kar_azalir():
    karlar = [fizibilite(**TEMEL, arsa_sahibi_payi=p)["kar"] for p in (0.3, 0.4, 0.5)]
    assert karlar == sorted(karlar, reverse=True)


def test_fiyat_artinca_kar_artar():
    karlar = [fizibilite(**{**TEMEL, "m2_fiyat": f})["kar"] for f in (40_000, 50_000, 60_000)]
    assert karlar == sorted(karlar)


def test_daha_yuksek_emsal_daha_fazla_daire():
    az = fizibilite(**TEMEL)["daireler"]["2+1"]
    cok = fizibilite(**{**TEMEL, "emsal": 2.10})["daireler"]["2+1"]
    assert cok > az
