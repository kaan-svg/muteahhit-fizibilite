import pytest

from src.gelir import kar_hesapla, m2_fiyati, pazar_yukle, satis_geliri

BOYUT = {"1+1": 50, "2+1": 100}


def test_pazar_dosyasi_okunuyor():
    fiyatlar = pazar_yukle()
    assert "mahmutlar" in fiyatlar
    assert fiyatlar["mahmutlar"] > 0


def test_m2_fiyati_buyuk_kucuk_harf_duyarsiz():
    fiyatlar = {"oba": 60_000}
    assert m2_fiyati("  OBA ", fiyatlar) == 60_000


def test_bilinmeyen_mahalle():
    with pytest.raises(KeyError):
        m2_fiyati("Yok Mahallesi", {"oba": 60_000})


def test_satis_geliri_basit():
    sonuc = satis_geliri({"1+1": 2, "2+1": 1}, BOYUT, 10_000)
    assert sonuc["tip_bazinda"] == {"1+1": 1_000_000, "2+1": 1_000_000}
    assert sonuc["toplam"] == 2_000_000


def test_satis_geliri_tip_carpani():
    sonuc = satis_geliri({"1+1": 2}, BOYUT, 10_000, tip_carpani={"1+1": 1.1})
    assert sonuc["toplam"] == pytest.approx(1_100_000)


def test_satis_geliri_tanimsiz_tip():
    with pytest.raises(ValueError):
        satis_geliri({"4+1": 1}, BOYUT, 10_000)


def test_kar_arsa_satin_alma():
    s = kar_hesapla(gelir=100, insaat_maliyeti=50, arsa_bedeli=20)
    assert s["kar"] == 30
    assert s["kar_marji"] == pytest.approx(30 / 70)


def test_kar_kat_karsiligi():
    s = kar_hesapla(gelir=100, insaat_maliyeti=40, arsa_sahibi_payi=0.4)
    assert s["musteahhit_geliri"] == pytest.approx(60)
    assert s["arsa_sahibine_kalan"] == pytest.approx(40)
    assert s["kar"] == pytest.approx(20)


def test_kar_ek_gider():
    s = kar_hesapla(gelir=100, insaat_maliyeti=50, ek_gider_orani=0.2)
    assert s["ek_gider"] == pytest.approx(10)
    assert s["kar"] == pytest.approx(40)


def test_kar_zarar_olabilir():
    s = kar_hesapla(gelir=50, insaat_maliyeti=80)
    assert s["kar"] < 0


def test_gecersiz_arsa_sahibi_payi():
    with pytest.raises(ValueError):
        kar_hesapla(gelir=100, insaat_maliyeti=50, arsa_sahibi_payi=1.0)
