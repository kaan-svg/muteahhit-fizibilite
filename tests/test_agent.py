"""Agent dongusu testleri. Ollama gerekmez: sahte istemci onceden yazilmis
cevaplari sirayla dondurur."""
import json

from src.agent import calistir, sor, yeni_konusma

ARSA = {"arsa_alani": 1000, "taks": 0.30, "emsal": 1.50, "mahalle": "Mahmutlar",
        "arsa_sahibi_payi": 0.45, "ek_gider_orani": 0.25}


def arac(ad, argumanlar):
    return {"message": {"role": "assistant", "content": "",
                        "tool_calls": [{"function": {"name": ad, "arguments": argumanlar}}]}}


def cevap(metin):
    return {"message": {"role": "assistant", "content": metin}}


class SahteIstemci:
    def __init__(self, *yanitlar):
        self.yanitlar = list(yanitlar)
        self.gorulen = []  # her cagrida modele giden mesajlar

    def chat(self, model, messages, tools):
        self.gorulen.append(list(messages))
        return self.yanitlar.pop(0)


SESSIZ = {"gunluk": lambda *a: None}


def test_arac_yoksa_dogrudan_cevap():
    istemci = SahteIstemci(cevap("Merhaba"))
    assert sor("selam", istemci=istemci, **SESSIZ) == "Merhaba"


def test_arac_sonucu_modele_geri_verilir():
    istemci = SahteIstemci(arac("fizibilite_hesapla", ARSA), cevap("Zarar ediyorsun."))
    assert sor("karli mi?", istemci=istemci, **SESSIZ) == "Zarar ediyorsun."

    ikinci_cagri = istemci.gorulen[1]
    tool_mesaji = ikinci_cagri[-1]
    assert tool_mesaji["role"] == "tool"
    assert tool_mesaji["tool_name"] == "fizibilite_hesapla"
    assert json.loads(tool_mesaji["content"])["kar_milyon_tl"] < 0


def test_birden_fazla_adim():
    istemci = SahteIstemci(
        arac("mahalle_fiyatlari", {}),
        arac("fizibilite_hesapla", {**ARSA, "mahalle": "Kestel"}),
        cevap("Kestel daha karli."),
    )
    assert sor("hangi mahalle?", istemci=istemci, **SESSIZ) == "Kestel daha karli."
    assert len(istemci.gorulen) == 3


def test_hata_modele_iletilir():
    istemci = SahteIstemci(arac("fizibilite_hesapla", {**ARSA, "mahalle": "Konakli"}),
                           cevap("Konakli icin veri yok."))
    sor("Konakli?", istemci=istemci, **SESSIZ)
    assert "hata" in json.loads(istemci.gorulen[1][-1]["content"])


def test_sonsuz_dongu_engellenir():
    istemci = SahteIstemci(*[arac("mahalle_fiyatlari", {}) for _ in range(10)])
    metin = sor("?", istemci=istemci, maks_adim=3, **SESSIZ)
    assert "fazla" in metin
    assert len(istemci.gorulen) == 3


def test_konusma_hafizasi_korunur():
    mesajlar = yeni_konusma() + [{"role": "user", "content": "ilk"}]
    calistir(mesajlar, istemci=SahteIstemci(cevap("bir")), **SESSIZ)
    mesajlar.append({"role": "user", "content": "ikinci"})
    istemci = SahteIstemci(cevap("iki"))
    calistir(mesajlar, istemci=istemci, **SESSIZ)
    icerikler = [m["content"] for m in istemci.gorulen[0]]
    assert "ilk" in icerikler and "bir" in icerikler
