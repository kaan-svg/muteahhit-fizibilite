import pytest

from src.koruma import kullanici_sayilari, uydurma_kontrol

ARSA = {"arsa_alani": 1000, "taks": 0.30, "emsal": 1.50, "mahalle": "Mahmutlar"}


def kullanici(metin):
    return [{"role": "system", "content": "TAKS 0.30 ornek"}, {"role": "user", "content": metin}]


@pytest.mark.parametrize("metin", [
    "1000 m2 arsa, TAKS 0.30, emsal 1.50",
    "1.000 m2, taks 0,3, emsal 1,5",
    "arsa 1000 metrekare, taks %30, emsal 1.5",
])
def test_kullanicinin_verdigi_degerler_gecer(metin):
    assert uydurma_kontrol("fizibilite_hesapla", ARSA, kullanici(metin)) is None


def test_uydurulan_degerler_engellenir():
    sonuc = uydurma_kontrol("fizibilite_hesapla", ARSA, kullanici("Mahmutlar'da 1000 m2 arsam var"))
    assert "taks, emsal" in sonuc["hata"]


def test_sistem_ve_asistan_mesajlari_sayilmaz():
    mesajlar = kullanici("1000 m2 arsam var") + [{"role": "assistant", "content": "Emsal 1.50 varsayalim"}]
    assert uydurma_kontrol("fizibilite_hesapla", ARSA, mesajlar) is not None


def test_onceki_mesajlardaki_degerler_gecerli():
    mesajlar = kullanici("1000 m2 arsa, TAKS 0.30, emsal 1.50") + [
        {"role": "assistant", "content": "Zarar."}, {"role": "user", "content": "Pay %40 olsa?"}]
    assert uydurma_kontrol("fizibilite_hesapla", {**ARSA, "TAKS": 0.3}, mesajlar) is None


def test_duyarlilikta_degistirilen_parametre_serbest():
    args = {"arsa": ARSA, "parametre": "emsal", "degerler": [1.2, 1.8]}
    assert uydurma_kontrol("duyarlilik_analizi", args, kullanici("1000 m2, TAKS 0.30, emsal 1.50")) is None
    args = {"arsa": {**ARSA, "emsal": 2.0}, "parametre": "emsal", "degerler": [1.2]}
    assert uydurma_kontrol("duyarlilik_analizi", args, kullanici("1000 m2, TAKS 0.30")) is None
    args = {"arsa": ARSA, "parametre": "arsa_sahibi_payi", "degerler": [0.4]}
    assert "emsal" in uydurma_kontrol("duyarlilik_analizi", args, kullanici("1000 m2, TAKS 0.30"))["hata"]


def test_diger_araclar_kontrol_edilmez():
    assert uydurma_kontrol("yonetmelik_ara", {"soru": "balkon"}, []) is None


def test_binlik_ayirici():
    assert 1000 in kullanici_sayilari(kullanici("1.000 m2"))
    assert 1.5 in kullanici_sayilari(kullanici("emsal 1.5"))


def test_istege_bagli_uydurma_engellenir():
    mesaj = kullanici("Kestel 800 m2, TAKS 0.35, emsal 1.40, pay %40, ek gider %20")
    arsa = {"arsa_alani": 800, "taks": 0.35, "emsal": 1.4, "mahalle": "Kestel",
            "arsa_sahibi_payi": 0.4, "ek_gider_orani": 0.2}
    assert uydurma_kontrol("fizibilite_hesapla", arsa, mesaj) is None
    assert uydurma_kontrol("fizibilite_hesapla", {**arsa, "emsal_disi_orani": 0.2}, mesaj) is None  # %20 mesajda var
    sonuc = uydurma_kontrol("fizibilite_hesapla", {**arsa, "emsal_disi_orani": 0.25}, mesaj)
    assert "emsal_disi_orani" in sonuc["hata"]
    assert uydurma_kontrol("fizibilite_hesapla", {**arsa, "max_kat": 0, "m2_fiyat": None}, mesaj) is None


def test_duyarlilikta_denenen_deger_istege_bagli_icin_de_serbest():
    args = {"arsa": {**ARSA, "arsa_sahibi_payi": 0.45}, "parametre": "arsa_sahibi_payi", "degerler": [0.4]}
    assert uydurma_kontrol("duyarlilik_analizi", args, kullanici("1000 m2, TAKS 0.30, emsal 1.50")) is None


def test_daire_tipi_soylendiyse_oran_zorunlu():
    mesaj = kullanici("Kestel 800 m2, TAKS 0.35, emsal 1.40. Sadece 1+1 yapacagim.")
    arsa = {"arsa_alani": 800, "taks": 0.35, "emsal": 1.4, "mahalle": "Kestel"}
    hata = uydurma_kontrol("fizibilite_hesapla", arsa, mesaj)["hata"]
    assert "1+1" in hata and "oran_1_1" in hata
    assert uydurma_kontrol("fizibilite_hesapla", {**arsa, "oran_1_1": 1}, mesaj) is None


def test_daire_tipi_yoksa_oran_gerekmez():
    assert uydurma_kontrol("fizibilite_hesapla", ARSA, kullanici("1000 m2, TAKS 0.30, emsal 1.50")) is None
