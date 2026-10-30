"""Degerlendirme scriptinin puanlama mantigi. Ollama gerekmez."""
import json

import pytest

from src.degerlendirme import arac_izleri, ozet, puanla, sayilar, vaka_calistir, vakalar

VAKALAR = {v["ad"]: v for v in vakalar()}


def tool(ad, sonuc):
    return {"role": "tool", "tool_name": ad, "content": json.dumps(sonuc)}


def test_vaka_sayisi_ve_beklenenler_hesaptan_gelir():
    assert len(VAKALAR) == 10
    assert VAKALAR["mahmutlar"]["beklenen_kar"] == [pytest.approx(-1.52, abs=0.01)]
    a, b = VAKALAR["duyarlilik"]["beklenen_kar"]
    assert a > 0 > b


@pytest.mark.parametrize("metin, beklenen", [
    ("Kar -1,52 milyon TL", [-1.52]),
    ("yaklasik 1.5 milyon zarar", [1.5]),
    ("%40: 1,93; %50: −4,97", [40, 1.93, 50, -4.97]),
])
def test_sayilar(metin, beklenen):
    assert sayilar(metin) == pytest.approx(beklenen)


def test_hesap_dogru_cevap_gecer():
    izler = arac_izleri([tool("fizibilite_hesapla", {"kar_milyon_tl": -1.52})])
    p = puanla(VAKALAR["mahmutlar"], "Proje zararda: yaklasik 1,5 milyon TL zarar.", izler)
    assert p == {"arac": True, "rakam": True, "yon": True}


def test_yanlis_arguman_arac_kontrolunu_dusurur():
    izler = arac_izleri([tool("fizibilite_hesapla", {"kar_milyon_tl": 3.0})])
    assert puanla(VAKALAR["mahmutlar"], "3 milyon kar", izler)["arac"] is False


def test_rakam_uydurma_yakalanir():
    izler = arac_izleri([tool("fizibilite_hesapla", {"kar_milyon_tl": -1.52})])
    p = puanla(VAKALAR["mahmutlar"], "Proje 2,4 milyon zarar ediyor.", izler)
    assert p["arac"] and not p["rakam"]


def test_yanlis_yon_yakalanir():
    izler = arac_izleri([tool("fizibilite_hesapla", {"kar_milyon_tl": -1.52})])
    assert puanla(VAKALAR["mahmutlar"], "Proje karli, 1,52 milyon.", izler)["yon"] is False


def test_duyarlilik_iki_rakam_gerekir():
    v = VAKALAR["duyarlilik"]
    a, b = v["beklenen_kar"]
    izler = arac_izleri([tool("duyarlilik_analizi", {"sonuclar": [{"kar_milyon_tl": a}, {"kar_milyon_tl": b}]})])
    assert all(puanla(v, f"%40: {a} milyon kar, %50: {b} milyon zarar", izler).values())
    assert puanla(v, f"%40: {a} milyon kar", izler)["rakam"] is False


def test_eksik_bilgide_uydurma_yakalanir():
    v = VAKALAR["eksik_bilgi"]
    assert puanla(v, "Hesap icin TAKS ve emsal degerlerini yazar misin?", [])["sormali"]
    uydurma = arac_izleri([tool("fizibilite_hesapla", {"kar_milyon_tl": 1.0})])
    assert not puanla(v, "Emsal 1.5 varsaydim. Baska?", uydurma)["sormali"]
    # Hata donse bile cagri yapilmissa deger uydurulmustur (gercek bir hata ornegi)
    hatali = arac_izleri([tool("fizibilite_hesapla", {"hata": "Konakli icin fiyat verisi yok"})])
    assert not puanla(v, "Konakli icin fiyat yok. TAKS ve emsal?", hatali)["sormali"]


def test_marj_ile_cevap_rakam_sayilir():
    v = VAKALAR["avsallar_buyuk"]
    izler = arac_izleri([tool("fizibilite_hesapla", {"kar_milyon_tl": v["beklenen_kar"][0]})])
    gercek_cevap = "Karlı olmamış ve kar marjı -16.2% olarak hesaplanmıştır. Kar elde edilememiştir."
    assert puanla(v, gercek_cevap, izler) == {"arac": True, "rakam": True, "yon": True}


def test_balkon_yasak_ifade():
    v = VAKALAR["balkon"]
    izler = arac_izleri([tool("yonetmelik_ara", {"sonuclar": []})])
    assert all(puanla(v, "Madde 22'ye gore emsale dahil edilmez.", izler).values())
    p = puanla(v, "Madde 22'ye gore emsal hesabına dahil edilebilir.", izler)
    assert p["madde"] and not p["yasak"]


def test_vaka_calistir_sahte_model():
    class Sahte:
        def __init__(self):
            self.n = 0

        def chat(self, model, messages, tools, **kw):
            self.n += 1
            if self.n == 1:
                return {"message": {"role": "assistant", "content": "", "tool_calls": [
                    {"function": {"name": "mahalle_fiyatlari", "arguments": {}}}]}}
            return {"message": {"role": "assistant", "content": "Kestel, Mahmutlar, Oba..."}}

    s = vaka_calistir(VAKALAR["mahalleler"], istemci=Sahte())
    assert s["gecti"] and s["araclar"] == ["mahalle_fiyatlari"]
    assert s["cagrilar"] == [{"ad": "mahalle_fiyatlari", "argumanlar": {}}]


def test_ozet_tablosu():
    sonuclar = [{"vaka": "a", "gecti": True, "kontroller": {"x": True}, "sure_sn": 2},
                {"vaka": "a", "gecti": False, "kontroller": {"x": False}, "sure_sn": 4}]
    metin = ozet(sonuclar)
    assert "1/2 (%50)" in metin and "| a | 1/2 | x x1 | 3 sn |" in metin
