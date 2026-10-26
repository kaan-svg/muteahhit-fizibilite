"""Planli Alanlar Imar Yonetmeligi icin RAG (arama ile cevap).

Adimlar:
  1. indir()          mevzuat.gov.tr'den guncel PDF'i indirir
  2. maddelere_bol()  metni maddelere (uzunsa parcalara) boler
  3. indeks_kur()     her parcanin embedding'ini Ollama ile cikarip kaydeder
  4. ara()            soruya en yakin maddeleri bulur

Kurulum (bir kere):
    ollama pull bge-m3
    python -m src.yonetmelik kur
Deneme:
    python -m src.yonetmelik ara "balkonlar emsale dahil mi"

Vektor veritabani yerine duz JSON + Python kullaniyoruz: yonetmelik birkac yuz
parca, bu boyutta Chroma gibi bir arac gereksiz bagimlilik olur.
"""
import json
import math
import os
import re
from pathlib import Path

VERI = Path(__file__).resolve().parent.parent / "data"
PDF_YOLU = VERI / "yonetmelik.pdf"
INDEKS_YOLU = VERI / "yonetmelik_indeks.json"
PDF_URL = "https://www.mevzuat.gov.tr/MevzuatMetin/yonetmelik/7.5.23722.pdf"
EMBED_MODEL = os.environ.get("FIZIBILITE_EMBED_MODEL", "bge-m3")
MAKS_PARCA = 1500  # karakter; daha uzun maddeler paragraflardan bolunur

# "MADDE 22 –", "GEÇİCİ MADDE 3 -", "EK MADDE 1 –" satirlarini yakalar
_MADDE = re.compile(r"^\s*((?:GEÇİCİ|GECICI|EK)\s+)?MADDE\s+(\d+[A-Z]?)\s*[–—-]", re.MULTILINE)
_BOLUM = re.compile(r"^\s*[A-ZÇĞİÖŞÜ]+\s+BÖLÜM\s*$", re.MULTILINE)


# ---------- 1. Indirme ve metin ----------

def indir(hedef=PDF_YOLU, url=PDF_URL):
    import urllib.request
    hedef.parent.mkdir(parents=True, exist_ok=True)
    istek = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(istek, timeout=60) as yanit:
        hedef.write_bytes(yanit.read())
    return hedef


def pdf_metni(yol=PDF_YOLU):
    from pypdf import PdfReader
    return "\n".join(sayfa.extract_text() or "" for sayfa in PdfReader(yol).pages)


# ---------- 2. Maddelere bolme ----------

# Satir basinda fikra "(3)" veya bent "a)", "çç)", "1)" isareti
_ISARET = r"(?:\(\d+\)|[a-zçğıöşü]{1,2}\)|\d+\))\s"


def _temizle(metin):
    """PDF'in satir kirmalarini birlestirir; fikra/bent baslarindaki satir sonlarini korur."""
    metin = re.sub(r"[ \t]+", " ", metin)
    metin = re.sub(r"-\n(?=[a-zçğıöşü])", "", metin)            # heceden bolunmus kelime
    metin = re.sub(rf"\n(?!{_ISARET})", " ", metin)              # duz satir kirmasi -> bosluk
    return re.sub(r" {2,}", " ", metin).strip()


def _paketle(bloklar, maks):
    """Kucuk bloklari maks uzunluga kadar birlestirir."""
    parcalar, simdiki = [], ""
    for b in bloklar:
        if simdiki and len(simdiki) + len(b) + 1 > maks and len(simdiki) > maks // 5:
            parcalar.append(simdiki.strip())
            simdiki = ""
        simdiki = f"{simdiki}\n{b}" if simdiki else b
    if simdiki.strip():
        parcalar.append(simdiki.strip())
    return parcalar


def _parcala(metin, maks=MAKS_PARCA):
    """Uzun metni once fikralardan "(n)", hala uzunsa bentlerden "a)" boler.

    Sadece satir basindaki isaretlerden bolunur; metin icindeki
    "(6) numarali alt bent" gibi atiflar bolme noktasi sayilmaz.
    """
    if len(metin) <= maks:
        return [metin]
    fikralar = re.split(r"\n(?=\(\d+\)\s)", metin)
    bloklar = []
    for f in fikralar:
        bloklar += [f] if len(f) <= maks else re.split(rf"\n(?={_ISARET})", f)
    # Bentten de bolunemeyen dev bloklar: cumle sonlarindan kes
    son = []
    for b in bloklar:
        while len(b) > maks:
            kes = b.rfind(". ", 0, maks)
            kes = kes + 1 if kes > maks // 3 else maks
            son.append(b[:kes].strip())
            b = b[kes:].strip()
        son.append(b)
    return _paketle(son, maks)


def maddelere_bol(metin):
    """[{'madde': '22', 'baslik': 'Emsal hesabi', 'parca': 1, 'metin': ...}, ...]"""
    metin = _BOLUM.sub("", metin)
    eslesmeler = list(_MADDE.finditer(metin))
    sonuc = []
    for i, e in enumerate(eslesmeler):
        # Baslik: MADDE satirindan onceki son dolu satir
        onceki = metin[eslesmeler[i - 1].end() if i else 0:e.start()].rstrip().split("\n")
        baslik = onceki[-1].strip() if onceki and len(onceki[-1].strip()) < 120 else ""
        bitis = eslesmeler[i + 1].start() if i + 1 < len(eslesmeler) else len(metin)
        govde = metin[e.start():bitis]
        # Govdenin sonundaki satir bir sonraki maddenin basligi, onu at
        if i + 1 < len(eslesmeler):
            govde = govde.rstrip().rsplit("\n", 1)[0]
        madde = ("Geçici " if e.group(1) and "GE" in e.group(1) else "Ek " if e.group(1) else "") + e.group(2)
        for n, parca in enumerate(_parcala(_temizle(govde)), 1):
            sonuc.append({"madde": madde, "baslik": baslik, "parca": n, "metin": parca})
    return sonuc


# ---------- 3. Embedding ve indeks ----------

def _normalize(v):
    uzunluk = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / uzunluk for x in v]


def ollama_embed(metinler, model=EMBED_MODEL):
    import ollama
    vektorler = []
    for i in range(0, len(metinler), 32):
        vektorler += ollama.embed(model=model, input=metinler[i:i + 32])["embeddings"]
    return vektorler


def indeks_kur(parcalar, embed=ollama_embed, yol=INDEKS_YOLU):
    girdiler = [f"Madde {p['madde']} {p['baslik']}\n{p['metin']}" for p in parcalar]
    vektorler = [_normalize(v) for v in embed(girdiler)]
    indeks = [{**p, "vektor": [round(x, 5) for x in v]} for p, v in zip(parcalar, vektorler)]
    if yol:
        yol.write_text(json.dumps(indeks, ensure_ascii=False), encoding="utf-8")
    return indeks


def indeks_yukle(yol=None):
    yol = Path(yol or INDEKS_YOLU)
    if not yol.exists():
        raise FileNotFoundError(
            "Yonetmelik indeksi yok. Once kurulum: ollama pull bge-m3 && python -m src.yonetmelik kur")
    return json.loads(yol.read_text(encoding="utf-8"))


# ---------- 4. Arama ----------

def _kelimeler(metin):
    return {k for k in re.findall(r"\w+", metin.lower()) if len(k) > 3}


def ara(soru, k=3, indeks=None, embed=None):
    """Anlam benzerligi (%80) + ortak kelime orani (%20) ile en iyi k parcayi dondurur.
    Kelime puani 'bodrum', 'otopark' gibi tam terimlerin kacmamasi icin."""
    indeks = indeks if indeks is not None else indeks_yukle()
    embed = embed or ollama_embed
    soru_v = _normalize(embed([soru])[0])
    soru_k = _kelimeler(soru)
    puanli = []
    for p in indeks:
        anlam = sum(a * b for a, b in zip(soru_v, p["vektor"]))
        kelime = len(soru_k & _kelimeler(p["metin"])) / len(soru_k) if soru_k else 0
        puanli.append((0.8 * anlam + 0.2 * kelime, p))
    puanli.sort(key=lambda x: x[0], reverse=True)
    return [{"madde": p["madde"], "baslik": p["baslik"], "metin": p["metin"],
             "puan": round(puan, 3)} for puan, p in puanli[:k]]


if __name__ == "__main__":
    import sys

    komut = sys.argv[1] if len(sys.argv) > 1 else ""
    if komut == "kur":
        if not PDF_YOLU.exists():
            print(f"Indiriliyor: {PDF_URL}")
            indir()
        parcalar = maddelere_bol(pdf_metni())
        maddeler = {p["madde"] for p in parcalar}
        print(f"{len(maddeler)} madde, {len(parcalar)} parca bulundu. Embedding cikariliyor ({EMBED_MODEL})...")
        indeks_kur(parcalar)
        print(f"Kaydedildi: {INDEKS_YOLU}")
    elif komut == "ara" and len(sys.argv) > 2:
        for s in ara(" ".join(sys.argv[2:])):
            print(f"\n=== Madde {s['madde']} - {s['baslik']} (puan {s['puan']}) ===\n{s['metin'][:600]}")
    elif komut == "goster":
        for p in maddelere_bol(pdf_metni())[:int(sys.argv[2]) if len(sys.argv) > 2 else 10]:
            print(f"Madde {p['madde']} [{p['parca']}] {p['baslik']}: {p['metin'][:80]!r}")
    else:
        print("Kullanim: python -m src.yonetmelik kur | ara <soru> | goster [n]")
