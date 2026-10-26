"""Hesap fonksiyonlarini LLM'in cagirabilecegi araclar (tools) olarak tanimlar.

Her aracin iki parcasi var:
- ARACLAR: modele gosterilen tanim (ad, aciklama, JSON Schema). Model bunu
  okuyup hangi araci hangi argumanlarla cagiracagina karar verir.
- ARAC_FONKSIYONLARI: o ad cagrildiginda calisan gercek Python fonksiyonu.

Kucuk modeller argumanlari bazen yanlis bicimde gonderir ("0.45" yerine 45,
sayi yerine metin gibi). _oran() ve _sayi() bunlari duzeltir; duzeltilemeyen
hatalar programi cokertmek yerine {"hata": ...} olarak modele geri doner.
"""
from src.gelir import pazar_yukle
from src.senaryo import fizibilite

DAIRE_TIPLERI = {"oran_1_1": "1+1", "oran_2_1": "2+1", "oran_3_1": "3+1"}
DEGISTIRILEBILIR = ["arsa_sahibi_payi", "ek_gider_orani", "m2_fiyat", "emsal", "max_kat", "mahalle"]

_ORAN = {"type": "number", "description": "0 ile 1 arasi oran, or. 0.45"}

ARACLAR = [
    {
        "type": "function",
        "function": {
            "name": "fizibilite_hesapla",
            "description": (
                "Bir arsa icin kat sayisi, daire sayisi, maliyet, gelir ve kari hesaplar. "
                "Kullanici bir arsanin karli olup olmadigini sordugunda kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "arsa_alani": {"type": "number", "description": "Arsa alani, m2"},
                    "taks": {"type": "number", "description": "TAKS, or. 0.30"},
                    "emsal": {"type": "number", "description": "Emsal (KAKS), or. 1.50"},
                    "mahalle": {"type": "string", "description": "Alanya mahallesi, or. Mahmutlar"},
                    "oran_1_1": {**_ORAN, "description": "Istege bagli. 1+1 dairelerin alan payi, 0-1"},
                    "oran_2_1": {**_ORAN, "description": "Istege bagli. 2+1 dairelerin alan payi, 0-1"},
                    "oran_3_1": {**_ORAN, "description": "Istege bagli. 3+1 dairelerin alan payi, 0-1. Hic oran verilmezse %50 1+1, %50 2+1"},
                    "max_kat": {"type": "integer", "description": "Istege bagli. Plandaki kat siniri"},
                    "arsa_sahibi_payi": {**_ORAN, "description": "Istege bagli. Kat karsiliginda arsa sahibine birakilan pay, or. 0.45"},
                    "ek_gider_orani": {**_ORAN, "description": "Istege bagli. KDV, ruhsat, pazarlama icin insaat maliyetine eklenen oran, or. 0.25"},
                    "m2_fiyat": {"type": "number", "description": "Istege bagli. Satis fiyati TL/m2; verilmezse mahalle ortalamasi kullanilir"},
                },
                "required": ["arsa_alani", "taks", "emsal", "mahalle"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "duyarlilik_analizi",
            "description": (
                "Ayni arsada tek bir parametreyi degistirip her deger icin kari hesaplar. "
                "'Pay %40 olsa ne olur', 'karin en cok neye bagli' gibi sorularda kullan. "
                "Arsa bilgileri fizibilite_hesapla ile aynidir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "arsa": {"type": "object", "description": "fizibilite_hesapla ile ayni arsa bilgileri"},
                    "parametre": {"type": "string", "enum": DEGISTIRILEBILIR},
                    "degerler": {"type": "array", "items": {}, "description": "Denenecek degerler, or. [0.40, 0.45, 0.50]"},
                },
                "required": ["arsa", "parametre", "degerler"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "yonetmelik_ara",
            "description": (
                "Planli Alanlar Imar Yonetmeligi'nde arama yapar, en ilgili maddeleri dondurur. "
                "Emsal/TAKS'a neyin dahil oldugu, balkon, bodrum, cati, otopark, cekme mesafesi, "
                "kat yuksekligi gibi mevzuat sorularinda kullan."
            ),
            "parameters": {
                "type": "object",
                "properties": {"soru": {"type": "string", "description": "Aranacak konu, or. 'balkonlar emsale dahil mi'"}},
                "required": ["soru"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mahalle_fiyatlari",
            "description": "Fiyat verisi olan Alanya mahallelerini ve ortalama m2 satis fiyatlarini listeler.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ---------- Arguman temizleme ----------

def _sayi(deger, ad):
    if isinstance(deger, str):
        deger = deger.replace("%", "").replace(",", ".").strip()
    try:
        return float(deger)
    except (TypeError, ValueError):
        raise ValueError(f"{ad} sayi olmali, gelen: {deger!r}")


def _oran(deger, ad):
    """0.45, '0.45', 45 ve '%45' degerlerinin hepsini 0.45'e cevirir."""
    x = _sayi(deger, ad)
    return x / 100 if x > 1 else x


def _arsa_argumanlari(a):
    """Model argumanlarini fizibilite() parametrelerine cevirir."""
    gecerli = ARACLAR[0]["function"]["parameters"]["properties"]
    bilinmeyen = [k for k in a if k not in gecerli]
    if bilinmeyen:
        raise ValueError(f"Bilinmeyen arguman: {', '.join(bilinmeyen)}. Gecerli: {', '.join(gecerli)}")
    eksik = [k for k in ("arsa_alani", "taks", "emsal", "mahalle") if a.get(k) in (None, "")]
    if eksik:
        raise ValueError(f"Eksik bilgi: {', '.join(eksik)}")

    oranlar = {tip: _oran(a[k], k) for k, tip in DAIRE_TIPLERI.items() if a.get(k) not in (None, "", 0)}
    if not oranlar:
        oranlar = {"1+1": 0.5, "2+1": 0.5}  # varsayilan karisim
    toplam = sum(oranlar.values())
    oranlar = {t: o / toplam for t, o in oranlar.items()}  # toplam 1'e normalize

    p = {
        "arsa_alani": _sayi(a["arsa_alani"], "arsa_alani"),
        "taks": _oran(a["taks"], "taks"),
        "emsal": _sayi(a["emsal"], "emsal"),
        "mahalle": str(a["mahalle"]),
        "oranlar": oranlar,
        "arsa_sahibi_payi": _oran(a.get("arsa_sahibi_payi") or 0, "arsa_sahibi_payi"),
        "ek_gider_orani": _oran(a.get("ek_gider_orani") or 0, "ek_gider_orani"),
    }
    if a.get("max_kat") not in (None, "", 0):
        p["max_kat"] = int(_sayi(a["max_kat"], "max_kat"))
    if a.get("m2_fiyat") not in (None, "", 0):
        p["m2_fiyat"] = _sayi(a["m2_fiyat"], "m2_fiyat")
    return p


def _ozet(s):
    """Modele gidecek kisa, yuvarlanmis sonuc."""
    m = lambda x: round(x / 1e6, 2)
    return {
        "kat_sayisi": s["kat_sayisi"],
        "insaat_alani_m2": round(s["insaat_alani"]),
        "daireler": {t: a for t, a in s["daireler"].items() if a},
        "m2_fiyat_tl": round(s["m2_fiyat"]),
        "brut_gelir_milyon_tl": m(s["brut_gelir"]),
        "arsa_sahibine_kalan_milyon_tl": m(s["arsa_sahibine_kalan"]),
        "muteahhit_geliri_milyon_tl": m(s["musteahhit_geliri"]),
        "toplam_gider_milyon_tl": m(s["toplam_gider"]),
        "kar_milyon_tl": m(s["kar"]),
        "kar_marji_yuzde": round(s["kar_marji"] * 100, 1) if s["kar_marji"] is not None else None,
    }


# ---------- Araclar ----------

def fizibilite_hesapla(**a):
    return _ozet(fizibilite(**_arsa_argumanlari(a)))


def duyarlilik_analizi(arsa, parametre, degerler):
    if parametre not in DEGISTIRILEBILIR:
        raise ValueError(f"Bu parametre degistirilemez: {parametre}. Secenekler: {DEGISTIRILEBILIR}")
    if not degerler:
        raise ValueError("En az bir deger gerekli")
    sonuclar = []
    for d in degerler:
        s = fizibilite_hesapla(**{**arsa, parametre: d})
        sonuclar.append({parametre: d, "kar_milyon_tl": s["kar_milyon_tl"],
                         "kar_marji_yuzde": s["kar_marji_yuzde"]})
    return {"parametre": parametre, "sonuclar": sonuclar}


def mahalle_fiyatlari():
    return {m.title(): round(f) for m, f in sorted(pazar_yukle().items())}


def yonetmelik_ara(soru):
    from src.yonetmelik import ara
    if not str(soru).strip():
        raise ValueError("Soru bos olamaz")
    return {"sonuclar": [{"madde": s["madde"], "baslik": s["baslik"], "metin": s["metin"]}
                         for s in ara(str(soru), k=3)]}


ARAC_FONKSIYONLARI = {
    "yonetmelik_ara": yonetmelik_ara,
    "fizibilite_hesapla": fizibilite_hesapla,
    "duyarlilik_analizi": duyarlilik_analizi,
    "mahalle_fiyatlari": mahalle_fiyatlari,
}


def _kucuk_harf(a):
    """{'TAKS': 0.3} -> {'taks': 0.3}. Ic ice sozlukleri de cevirir."""
    if not isinstance(a, dict):
        return a
    return {str(k).strip().lower(): _kucuk_harf(v) for k, v in a.items()}


def arac_calistir(ad, argumanlar=None):
    """Modelin istedigi araci calistirir. Hata olursa cokmez, hatayi dondurur
    ki model argumanlarini duzeltip tekrar deneyebilsin."""
    argumanlar = _kucuk_harf(argumanlar or {})
    if ad not in ARAC_FONKSIYONLARI:
        return {"hata": f"Bilinmeyen arac: {ad}. Mevcut: {list(ARAC_FONKSIYONLARI)}"}
    try:
        return ARAC_FONKSIYONLARI[ad](**(argumanlar or {}))
    except (ValueError, KeyError, TypeError, FileNotFoundError) as e:
        return {"hata": str(e).strip("'\"")}


if __name__ == "__main__":
    # Gun 9 demosu: model sadece hangi araci cagiracagina karar veriyor.
    # Sonucu modele geri verip cevap urettirmek Gun 10'un isi.
    import json
    import sys

    import ollama

    from src.llm import VARSAYILAN_MODEL

    soru = " ".join(sys.argv[1:]) or (
        "Mahmutlar'da 1000 m2 arsam var, TAKS 0.30, emsal 1.50. Kat karsiliginda "
        "arsa sahibine %45 veriyoruz, ek giderler %25. Pay %40 ve %50 olsa kar nasil degisir?"
    )
    print(f"Soru: {soru}\n")
    yanit = ollama.chat(model=VARSAYILAN_MODEL, messages=[{"role": "user", "content": soru}], tools=ARACLAR)
    cagrilar = yanit.message.tool_calls or []
    if not cagrilar:
        print("Model arac cagirmadi, dogrudan cevap verdi:\n" + yanit.message.content)
    for c in cagrilar:
        print(f"-> Model cagirdi: {c.function.name}")
        print(json.dumps(c.function.arguments, ensure_ascii=False, indent=2))
        print("<- Sonuc:")
        print(json.dumps(arac_calistir(c.function.name, c.function.arguments), ensure_ascii=False, indent=2))
        print()
