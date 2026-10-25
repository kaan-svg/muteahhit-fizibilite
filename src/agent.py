"""Fizibilite agent'i: model araclari cagirir, sonuclari gorur, cevap yazar.

Dongu:
  1. Kullanici sorusu + arac tanimlari modele gider.
  2. Model arac isterse (tool_calls) araclari calistir, sonuclari
     "tool" mesaji olarak geri ver, 1'e don.
  3. Model arac istemeden cevap verirse dur.
Sonsuz donguye karsi en fazla MAKS_ADIM tur doner.

Calistirma:
    python -m src.agent                 # sohbet modu
    python -m src.agent "soru..."       # tek soru
"""
import json
import os
import time

from src.araclar import ARACLAR, arac_calistir
from src.llm import VARSAYILAN_MODEL

MAKS_ADIM = 6

# qwen3 gibi modeller cevap vermeden once uzun uzun "dusunur" (thinking).
# Arac secimi icin buna gerek yok ve cevabi 5-10 kat yavaslatiyor, o yuzden kapali.
# Acmak icin: FIZIBILITE_DUSUN=1 python -m src.agent
DUSUN = os.environ.get("FIZIBILITE_DUSUN") == "1"

SISTEM_MESAJI = (
    "Sen Alanya'daki kucuk muteahhitlere arsa fizibilitesinde yardim eden bir asistansin.\n"
    "Kurallar:\n"
    "1. Her rakami araclarla hesapla. Kendin hesap yapma, rakam uydurma.\n"
    "2. Zorunlu bilgiler sadece arsa_alani, taks, emsal ve mahalle. Bunlardan biri eksikse "
    "tahmin etme, kullaniciya sor. Diger alanlar istege bagli; kullanici vermediyse bos birak "
    "ve kullaniciya sorma.\n"
    "3. Arac {\"hata\": ...} donerse hatayi oku. Arguman adi veya bicimi yanlissa duzeltip "
    "araci hemen tekrar cagir, kullaniciya sorma. Sadece kullanicidan gelmesi gereken bir "
    "bilgi eksikse (or. mahalle icin fiyat verisi yok) kullaniciya acikla.\n"
    "4. Kar = muteahhit geliri - toplam gider. Brut geliri giderle karsilastirma.\n"
    "5. 'Kar neye bagli', 'X olsa ne olur' sorularinda duyarlilik_analizi kullan.\n"
    "6. Turkce, kisa ve net yaz. Sonuclarin tahmini oldugunu belirt, yatirim tavsiyesi verme."
)


def _sohbet(istemci, model, mesajlar):
    try:
        return istemci.chat(model=model, messages=mesajlar, tools=ARACLAR, think=DUSUN)
    except Exception as e:
        # Dusunme ozelligi olmayan modeller 'think' parametresini kabul etmeyebilir.
        if "think" not in str(e).lower():
            raise
        return istemci.chat(model=model, messages=mesajlar, tools=ARACLAR)


def calistir(mesajlar, model=VARSAYILAN_MODEL, istemci=None, maks_adim=MAKS_ADIM, gunluk=print):
    """Mesaj listesini (yerinde) gunceller ve modelin son cevabini dondurur.

    mesajlar: sistem + onceki konusma + yeni kullanici mesaji.
    gunluk: arac cagrilarini yazdirmak icin; sessiz olmasi icin lambda *a: None.
    """
    if istemci is None:
        import ollama
        istemci = ollama

    for adim in range(1, maks_adim + 1):
        gunluk(f"  ... model calisiyor (adim {adim})")
        baslangic = time.perf_counter()
        mesaj = _sohbet(istemci, model, mesajlar)["message"]
        gunluk(f"      {time.perf_counter() - baslangic:.1f} sn")
        mesajlar.append(mesaj)
        cagrilar = mesaj.get("tool_calls") or []
        if not cagrilar:
            return (mesaj.get("content") or "").strip()

        for c in cagrilar:
            ad, argumanlar = c["function"]["name"], c["function"]["arguments"] or {}
            sonuc = arac_calistir(ad, argumanlar)
            gunluk(f"  -> {ad}({json.dumps(argumanlar, ensure_ascii=False)})")
            if "hata" in sonuc:
                gunluk(f"     ! {sonuc['hata']}")
            mesajlar.append({"role": "tool", "tool_name": ad,
                             "content": json.dumps(sonuc, ensure_ascii=False)})

    return "Cok fazla arac cagrisi yapildi, cevap uretilemedi. Soruyu daha net sorar misin?"


def yeni_konusma():
    return [{"role": "system", "content": SISTEM_MESAJI}]


def sor(soru, **kw):
    """Tek seferlik soru: yeni konusma acar, cevabi dondurur."""
    mesajlar = yeni_konusma() + [{"role": "user", "content": soru}]
    return calistir(mesajlar, **kw)


def sohbet_modu(model=VARSAYILAN_MODEL):
    print(f"Fizibilite asistani ({model}). Cikmak icin 'q'.\n")
    mesajlar = yeni_konusma()
    while True:
        try:
            soru = input("Sen: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if soru.lower() in {"q", "quit", "exit", "cik"}:
            break
        if not soru:
            continue
        mesajlar.append({"role": "user", "content": soru})
        print(f"\nAsistan: {calistir(mesajlar, model=model)}\n")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        print(sor(" ".join(sys.argv[1:])))
    else:
        sohbet_modu()

