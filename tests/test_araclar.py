import pytest

from src.araclar import ARAC_FONKSIYONLARI, ARACLAR, _oran, arac_calistir

ARSA = {"arsa_alani": 1000, "taks": 0.30, "emsal": 1.50, "mahalle": "Mahmutlar",
        "oran_1_1": 0.5, "oran_2_1": 0.5, "arsa_sahibi_payi": 0.45, "ek_gider_orani": 0.25}


def test_her_tanimin_fonksiyonu_var():
    adlar = {a["function"]["name"] for a in ARACLAR}
    assert adlar == set(ARAC_FONKSIYONLARI)


def test_fizibilite_senaryo_ile_ayni_sonuc():
    s = arac_calistir("fizibilite_hesapla", ARSA)
    assert s["daireler"] == {"1+1": 10, "2+1": 6}
    assert s["kar_milyon_tl"] == pytest.approx(-1.52, abs=0.01)


@pytest.mark.parametrize("girdi", [0.45, "0.45", 45, "%45", "45", "0,45"])
def test_oran_bicimleri(girdi):
    assert _oran(girdi, "x") == pytest.approx(0.45)


def test_yuzde_olarak_gelen_argumanlar_ayni_sonucu_verir():
    yuzde = {**ARSA, "oran_1_1": 50, "oran_2_1": 50, "arsa_sahibi_payi": "%45", "ek_gider_orani": 25}
    assert arac_calistir("fizibilite_hesapla", yuzde) == arac_calistir("fizibilite_hesapla", ARSA)


def test_oranlar_normalize_edilir():
    s = arac_calistir("fizibilite_hesapla", {**ARSA, "oran_1_1": 1, "oran_2_1": 1})
    assert s["daireler"] == {"1+1": 10, "2+1": 6}


def test_daire_orani_yoksa_varsayilan():
    arsa = {k: v for k, v in ARSA.items() if not k.startswith("oran")}
    assert arac_calistir("fizibilite_hesapla", arsa)["daireler"] == {"1+1": 10, "2+1": 6}


def test_duyarlilik_pay_artinca_kar_azalir():
    s = arac_calistir("duyarlilik_analizi", {"arsa": ARSA, "parametre": "arsa_sahibi_payi",
                                             "degerler": [0.40, 0.45, 0.50]})
    karlar = [r["kar_milyon_tl"] for r in s["sonuclar"]]
    assert karlar == sorted(karlar, reverse=True)
    assert karlar[0] > 0 > karlar[1]


def test_mahalle_fiyatlari():
    assert arac_calistir("mahalle_fiyatlari")["Mahmutlar"] == 58979


@pytest.mark.parametrize("ad, argumanlar", [
    ("yok_boyle_arac", {}),
    ("fizibilite_hesapla", {"arsa_alani": 1000}),                       # eksik bilgi
    ("fizibilite_hesapla", {**ARSA, "mahalle": "Atlantis"}),            # bilinmeyen mahalle
    ("fizibilite_hesapla", {**ARSA, "emsal": "cok"}),                   # sayi degil
    ("fizibilite_hesapla", {**ARSA, "fazladan": 1}),                    # bilinmeyen arguman
    ("duyarlilik_analizi", {"arsa": ARSA, "parametre": "taks", "degerler": [0.3]}),
    ("duyarlilik_analizi", {"arsa": ARSA, "parametre": "emsal", "degerler": []}),
])
def test_hatalar_cokmez_hata_doner(ad, argumanlar):
    assert "hata" in arac_calistir(ad, argumanlar)
