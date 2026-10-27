"""Arayuz fonksiyonlarinin testleri. Sunucu acilmaz, Ollama gerekmez."""
from src.arayuz import BAGLANTI_HATASI, gecmisten_mesajlar, hesapla, mahalleler, sohbet, yorumla

# arsa_alani, taks, emsal, mahalle, 1+1, 2+1, 3+1, max_kat, pay, ek_gider, m2_fiyat
FORM = (1000, 0.30, 1.50, "Mahmutlar", 50, 50, 0, 0, 45, 25, 0)


def test_mahalleler_listesi():
    assert "Mahmutlar" in mahalleler()


def test_hesapla_ozet_ve_duyarlilik():
    ozet, duyarlilik = hesapla(*FORM)
    assert "Zararlı" in ozet and "-1,52 M TL" in ozet
    assert "%45 ← şu an" in duyarlilik
    assert "%40" in duyarlilik and "1,93 M TL" in duyarlilik


def test_hesapla_hata_gosterir():
    form = list(FORM)
    form[3] = "Atlantis"
    ozet, duyarlilik = hesapla(*form)
    assert ozet.startswith("**Hata:**") and duyarlilik == ""


def test_yorumla_sahte_model():
    assert yorumla(*FORM, acikla=lambda s: f"kar {s['kar']:.0f}").startswith("kar -")


def test_yorumla_baglanti_hatasi():
    def coker(s):
        raise ConnectionError("yok")
    assert yorumla(*FORM, acikla=coker) == BAGLANTI_HATASI


def test_gecmis_donusumu_arac_kutusunu_atlar():
    gecmis = [
        {"role": "user", "content": "soru"},
        {"role": "assistant", "content": "-> arac(...)", "metadata": {"title": "🔧 Çağrılan araçlar"}},
        {"role": "assistant", "content": [{"type": "text", "text": "cevap"}]},
    ]
    m = gecmisten_mesajlar(gecmis)
    assert [x["role"] for x in m] == ["system", "user", "assistant"]
    assert m[-1]["content"] == "cevap"


def test_sohbet_arac_gunlugu_ayri_mesaj():
    def sahte(mesajlar, gunluk):
        gunluk("  ... model calisiyor (adim 1)")
        gunluk("  -> fizibilite_hesapla({})")
        return "Zararlı."
    cevap = sohbet("karlı mı?", [], calistir_fn=sahte)
    assert cevap[0].metadata["title"].endswith("araçlar")
    assert cevap[0].content == "-> fizibilite_hesapla({})"   # ilerleme satirlari gizli
    assert cevap[1].content == "Zararlı."


def test_sohbet_arac_yoksa_duz_metin():
    assert sohbet("selam", [], calistir_fn=lambda m, gunluk: "Merhaba") == "Merhaba"


def test_sohbet_baglanti_hatasi():
    def coker(m, gunluk):
        raise ConnectionError()
    assert sohbet("x", [], calistir_fn=coker) == BAGLANTI_HATASI


def test_arayuz_kurulur():
    from src.arayuz import arayuz
    assert arayuz() is not None
