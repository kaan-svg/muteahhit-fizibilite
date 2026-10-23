"""Ollama gerektirmeyen testler: prompt dogru kuruluyor mu, cevap dogru okunuyor mu."""
from src.llm import SISTEM_MESAJI, acikla, mesajlar, sonuc_metni
from src.senaryo import fizibilite

SONUC = fizibilite(arsa_alani=1000, taks=0.30, emsal=1.50, mahalle="x",
                   oranlar={"2+1": 1.0}, buyuklukler={"2+1": 100},
                   ortak_alan_orani=0.0, m2_fiyat=50_000, birim_maliyet=20_000,
                   arsa_sahibi_payi=0.4, ad="Test")


class SahteIstemci:
    def __init__(self):
        self.gelen = None

    def chat(self, model, messages):
        self.gelen = {"model": model, "messages": messages}
        return {"message": {"content": "  Proje karli.  "}}


def test_sonuc_metni_rakamlari_icerir():
    metin = sonuc_metni(SONUC)
    assert "15 adet 2+1" in metin
    assert "75,0 milyon TL" in metin   # brut gelir 15 x 100 x 50.000
    assert "Kat sayisi: 5" in metin


def test_mesajlar_sistem_ve_kullanici():
    m = mesajlar(SONUC)
    assert m[0] == {"role": "system", "content": SISTEM_MESAJI}
    assert m[1]["role"] == "user"
    assert sonuc_metni(SONUC) in m[1]["content"]


def test_acikla_sahte_istemci():
    istemci = SahteIstemci()
    cevap = acikla(SONUC, model="deneme", istemci=istemci)
    assert cevap == "Proje karli."
    assert istemci.gelen["model"] == "deneme"
