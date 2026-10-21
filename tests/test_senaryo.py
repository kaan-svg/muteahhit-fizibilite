import pytest

from src.senaryo import fizibilite, karsilastir, tablo

FIYAT = {"a": 50_000, "b": 70_000}
TEMEL = dict(arsa_alani=1000, taks=0.30, emsal=1.50, mahalle="a",
             oranlar={"2+1": 1.0}, buyuklukler={"2+1": 100},
             ortak_alan_orani=0.0, birim_maliyet=20_000, fiyatlar=FIYAT)


def test_fizibilite_zincir():
    s = fizibilite(**TEMEL)
    assert s["kat_sayisi"] == 5
    assert s["insaat_alani"] == 1500
    assert s["daireler"] == {"2+1": 15}
    assert s["brut_gelir"] == 15 * 100 * 50_000
    assert s["insaat_maliyeti"] == 1500 * 20_000
    assert s["kar"] == s["brut_gelir"] - s["insaat_maliyeti"]


def test_kat_siniri_alani_dusurur():
    s = fizibilite(**{**TEMEL, "max_kat": 4})
    assert s["kat_sayisi"] == 4
    assert s["insaat_alani"] == pytest.approx(1200)  # 300 m2 taban x 4 kat


def test_m2_fiyat_dogrudan_verilebilir():
    s = fizibilite(**{**TEMEL, "m2_fiyat": 10_000})
    assert s["m2_fiyat"] == 10_000


def test_karsilastir_kara_gore_siralar():
    sonuc = karsilastir(TEMEL, {"ucuz": {}, "pahali": {"mahalle": "b"}})
    assert [s["ad"] for s in sonuc] == ["pahali", "ucuz"]


def test_karsilastir_temeli_degistirmez():
    temel = dict(TEMEL)
    karsilastir(temel, {"x": {"mahalle": "b"}})
    assert temel == TEMEL


def test_bos_varyasyon_hata():
    with pytest.raises(ValueError):
        karsilastir(TEMEL, {})


def test_tablo_her_senaryoyu_icerir():
    metin = tablo(karsilastir(TEMEL, {"ilk": {}, "ikinci": {"mahalle": "b"}}))
    assert "ilk" in metin and "ikinci" in metin
