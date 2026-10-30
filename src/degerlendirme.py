"""Agent'in ne kadar dogru calistigini olcen degerlendirme.

Her vaka modele N kez sorulur (model her seferinde farkli cevap verebilir).
Beklenen rakamlar modelden degil, dogrudan hesap kodundan alinir; yani bu
script formulleri degil, LLM'in araclari kullanmasini ve sonucu aktarmasini olcer.

Kontroller:
  arac      dogru arac cagrildi ve beklenen sonucu dondurdu mu (argumanlar dogru mu)
  rakam     cevaptaki kar (veya kar marji) aractan donenle ayni mi (+-0.06 milyon)
  yon       karli/zararli dogru soylendi mi
  madde     mevzuat cevabinda beklenen madde numarasi var mi
  yasak     cevapta yanlis oldugu bilinen bir ifade var mi
  sormali   eksik bilgide (TAKS/emsal) hesap araci hic cagrilmadan bu bilgiler soruldu mu

Calistirma (Ollama acik olmali, 10 vaka x 3 tekrar ~5-10 dk):
    python -m src.degerlendirme
    python -m src.degerlendirme --tekrar 1 --vaka balkon
"""
import argparse
import json
import re
import time
from datetime import datetime
from pathlib import Path

from src.agent import calistir, yeni_konusma
from src.araclar import arac_calistir

RAPOR_KLASORU = Path(__file__).resolve().parent.parent / "eval"
TOLERANS = 0.06  # milyon TL; 1,52 -> "1,5 milyon" kabul edilir


def _arsa(alan, taks, emsal, mahalle, pay, ek, **ek_alanlar):
    return {"arsa_alani": alan, "taks": taks, "emsal": emsal, "mahalle": mahalle,
            "arsa_sahibi_payi": pay, "ek_gider_orani": ek, **ek_alanlar}


def _kar(arsa):
    return arac_calistir("fizibilite_hesapla", arsa)["kar_milyon_tl"]


def _marj(arsa):
    return arac_calistir("fizibilite_hesapla", arsa)["kar_marji_yuzde"]


# ---------- Vakalar ----------

HESAP_VAKALARI = [
    ("mahmutlar", "Mahmutlar'da 1000 m2 arsam var, TAKS 0.30, emsal 1.50. Arsa sahibine %45 veriyorum, "
                  "ek giderler %25. Karli mi?",
     _arsa(1000, 0.30, 1.50, "Mahmutlar", 0.45, 0.25)),
    ("kestel_1+1", "Kestel'de 800 m2 arsa, TAKS 0.35, emsal 1.40. Sadece 1+1 yapacagim. Arsa sahibi payi "
                   "%40, ek gider %20. Kar ne kadar?",
     _arsa(800, 0.35, 1.40, "Kestel", 0.40, 0.20, oran_1_1=1.0)),
    ("oba_kat_siniri", "Oba'da 1500 m2 arsa var, TAKS 0.25, emsal 1.25, planda en fazla 4 kat izni var. "
                       "Kat karsiligi %45, ek gider %25. Bu is karli mi?",
     _arsa(1500, 0.25, 1.25, "Oba", 0.45, 0.25, max_kat=4)),
    ("tosmur_kendi_arsam", "Tosmur'da 600 m2 arsa benim, kat karsiligi yok. TAKS 0.40, emsal 1.60, "
                           "ek gider %30. Kar ne olur?",
     _arsa(600, 0.40, 1.60, "Tosmur", 0, 0.30)),
    ("avsallar_buyuk", "Avsallar'da 1200 m2 arsa, TAKS 0.30, emsal 1.20. Yarisi 2+1 yarisi 3+1 olsun. "
                       "Arsa sahibine %50, ek gider %25. Karli mi?",
     _arsa(1200, 0.30, 1.20, "Avsallar", 0.50, 0.25, oran_2_1=0.5, oran_3_1=0.5)),
]


def vakalar():
    liste = []
    for ad, soru, arsa in HESAP_VAKALARI:
        liste.append({"ad": ad, "tur": "hesap", "soru": soru, "beklenen_kar": [_kar(arsa)],
                      "beklenen_marj": _marj(arsa)})

    mahmutlar = HESAP_VAKALARI[0][2]
    liste.append({
        "ad": "duyarlilik", "tur": "hesap",
        "soru": HESAP_VAKALARI[0][1].replace("Karli mi?", "Pay %40 ve %50 olsa kar nasil degisir?"),
        "beklenen_kar": [_kar({**mahmutlar, "arsa_sahibi_payi": p}) for p in (0.40, 0.50)],
    })
    liste += [
        {"ad": "eksik_bilgi", "tur": "sormali",
         "soru": "Konakli'da 500 m2 arsam var, karli olur mu?"},
        {"ad": "balkon", "tur": "mevzuat", "soru": "Balkonlar emsale dahil mi?",
         "madde": "22", "yasak": ["dahil edilebilir", "emsale dahildir", "hesabına dahil edilir"]},
        {"ad": "emsal_disi_sinir", "tur": "mevzuat",
         "soru": "Emsal disi alanlarin toplami en fazla yuzde kac olabilir?",
         "madde": "5", "anahtar": ["30"]},
        {"ad": "mahalleler", "tur": "liste", "soru": "Hangi mahallelerin fiyat verisi var?",
         "arac": "mahalle_fiyatlari", "anahtar": ["Kestel", "Mahmutlar"]},
    ]
    return liste


# ---------- Puanlama ----------

def sayilar(metin):
    """Metindeki sayilari bulur: '-1,52', '1.5', '−4,97' -> [-1.52, 1.5, -4.97]"""
    metin = metin.replace("−", "-")
    return [float(s.replace(",", ".")) for s in re.findall(r"-?\d+(?:[.,]\d+)?", metin)]


def _alan(m, ad):
    return m.get(ad) if hasattr(m, "get") else getattr(m, ad, None)


def arac_izleri(mesajlar):
    """Konusmadan [(arac_adi, sonuc_dict)] listesi cikarir."""
    izler = []
    for m in mesajlar:
        if _alan(m, "role") == "tool":
            try:
                izler.append((_alan(m, "tool_name"), json.loads(_alan(m, "content"))))
            except (TypeError, json.JSONDecodeError):
                izler.append((_alan(m, "tool_name"), {}))
    return izler


def cagri_izleri(mesajlar):
    """Modelin yaptigi arac cagrilari ve argumanlari (hata ayiklama icin)."""
    cagrilar = []
    for m in mesajlar:
        for c in _alan(m, "tool_calls") or []:
            f = c["function"]
            cagrilar.append({"ad": f["name"], "argumanlar": dict(f["arguments"] or {})})
    return cagrilar


def _kar_sonuclari(izler):
    """Arac sonuclarindaki tum kar rakamlari (fizibilite ve duyarlilik)."""
    karlar = []
    for _, s in izler:
        if "kar_milyon_tl" in s:
            karlar.append(s["kar_milyon_tl"])
        for r in s.get("sonuclar", []) if isinstance(s.get("sonuclar"), list) else []:
            if isinstance(r, dict) and "kar_milyon_tl" in r:
                karlar.append(r["kar_milyon_tl"])
    return karlar


def _yakin(a, b):
    return abs(a - b) <= TOLERANS


def _zarar_diyor(cevap):
    c = cevap.lower()
    return any(k in c for k in ("zarar", "karlı değil", "kârlı değil", "karli degil", "negatif", "kayıp",
                                "karlı olmamış", "kârlı olmamış", "elde edilemem", "karlı olmadığı",
                                "kârlı olmadığı", "kar edilemez"))


def puanla(vaka, cevap, izler):
    """{kontrol_adi: True/False} dondurur. Hepsi True ise vaka gecti."""
    p = {}
    if vaka["tur"] == "hesap":
        karlar = _kar_sonuclari(izler)
        sayi = [abs(x) for x in sayilar(cevap)]
        p["arac"] = all(any(_yakin(b, k) for k in karlar) for b in vaka["beklenen_kar"])
        p["rakam"] = all(any(_yakin(abs(b), x) for x in sayi) for b in vaka["beklenen_kar"])
        if not p["rakam"] and "beklenen_marj" in vaka:  # "marj %-16,2" de dogru bir cevap
            p["rakam"] = any(abs(abs(vaka["beklenen_marj"]) - x) <= 0.15 for x in sayi)
        if len(vaka["beklenen_kar"]) == 1:
            p["yon"] = _zarar_diyor(cevap) == (vaka["beklenen_kar"][0] < 0)
    elif vaka["tur"] == "sormali":
        # Hesap araci cagrildiysa TAKS/emsal uydurulmus demektir (hata donse bile).
        uydurdu = any(ad == "fizibilite_hesapla" for ad, _ in izler)
        p["sormali"] = not uydurdu and any(k in cevap.lower() for k in ("taks", "emsal"))
    elif vaka["tur"] == "mevzuat":
        p["arac"] = any(ad == "yonetmelik_ara" for ad, _ in izler)
        p["madde"] = re.search(rf"\b{vaka['madde']}\b", cevap) is not None
    elif vaka["tur"] == "liste":
        p["arac"] = any(ad == vaka["arac"] for ad, _ in izler)
    if "anahtar" in vaka:
        p["anahtar"] = all(a.lower() in cevap.lower() for a in vaka["anahtar"])
    if "yasak" in vaka:
        p["yasak"] = not any(y in cevap.lower() for y in vaka["yasak"])
    return p


# ---------- Calistirma ----------

def vaka_calistir(vaka, **kw):
    mesajlar = yeni_konusma() + [{"role": "user", "content": vaka["soru"]}]
    baslangic = time.perf_counter()
    try:
        cevap = calistir(mesajlar, gunluk=lambda *a: None, **kw)
    except Exception as e:  # baglanti vb.
        cevap = f"HATA: {e}"
    izler = arac_izleri(mesajlar)
    kontroller = puanla(vaka, cevap, izler)
    return {"vaka": vaka["ad"], "gecti": all(kontroller.values()), "kontroller": kontroller,
            "sure_sn": round(time.perf_counter() - baslangic, 1),
            "araclar": [ad for ad, _ in izler], "cagrilar": cagri_izleri(mesajlar), "cevap": cevap}


def degerlendir(tekrar=3, sadece=None, **kw):
    sonuclar = []
    for vaka in vakalar():
        if sadece and vaka["ad"] not in sadece:
            continue
        for i in range(tekrar):
            s = vaka_calistir(vaka, **kw)
            sonuclar.append(s)
            print(f"{'✓' if s['gecti'] else '✗'} {vaka['ad']:<20} #{i + 1}  {s['sure_sn']:>5} sn  "
                  + " ".join(f"{k}={'ok' if v else 'X'}" for k, v in s["kontroller"].items()))
    return sonuclar


def ozet(sonuclar):
    """Vaka bazinda gecme orani ve kontrol bazinda hata sayilari (markdown)."""
    vakalar_ = {}
    for s in sonuclar:
        vakalar_.setdefault(s["vaka"], []).append(s)
    gecen = sum(s["gecti"] for s in sonuclar)
    satirlar = [f"**Toplam: {gecen}/{len(sonuclar)} (%{100 * gecen / len(sonuclar):.0f})**", "",
                "| Vaka | Gecti | Basarisiz kontroller | Ort. sure |", "|---|---|---|---|"]
    for ad, liste in vakalar_.items():
        hatalar = {}
        for s in liste:
            for k, v in s["kontroller"].items():
                if not v:
                    hatalar[k] = hatalar.get(k, 0) + 1
        hata = ", ".join(f"{k} x{n}" for k, n in hatalar.items()) or "-"
        ort = sum(s["sure_sn"] for s in liste) / len(liste)
        satirlar.append(f"| {ad} | {sum(s['gecti'] for s in liste)}/{len(liste)} | {hata} | {ort:.0f} sn |")
    return "\n".join(satirlar)


def kaydet(sonuclar, model, klasor=RAPOR_KLASORU):
    klasor.mkdir(exist_ok=True)
    zaman = datetime.now().strftime("%Y%m%d-%H%M")
    (klasor / f"sonuc-{zaman}.json").write_text(
        json.dumps({"model": model, "sonuclar": sonuclar}, ensure_ascii=False, indent=2), encoding="utf-8")
    rapor = f"# Degerlendirme ({model}, {zaman})\n\n{ozet(sonuclar)}\n"
    (klasor / "SONUCLAR.md").write_text(rapor, encoding="utf-8")
    return klasor / "SONUCLAR.md"


if __name__ == "__main__":
    from src.llm import VARSAYILAN_MODEL

    ap = argparse.ArgumentParser()
    ap.add_argument("--tekrar", type=int, default=3)
    ap.add_argument("--vaka", nargs="*", help="sadece bu vakalar, or. --vaka balkon mahmutlar")
    ap.add_argument("--model", default=VARSAYILAN_MODEL)
    a = ap.parse_args()

    sonuclar = degerlendir(a.tekrar, a.vaka, model=a.model)
    print("\n" + ozet(sonuclar))
    print(f"\nKaydedildi: {kaydet(sonuclar, a.model)}")
