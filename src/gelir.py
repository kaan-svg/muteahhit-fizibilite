"""Satis geliri ve kar hesaplari.

Notlar:
- pazar.csv'deki fiyatlar ilan (istenen) fiyat ortalamasidir; eski binalar da
  dahildir. Gercek satis fiyati ve yeni proje fiyati farkli olabilir.
  Alanya'daki saha verisi gelince guncellenecek.
- Bakanlik birim maliyetinde KDV, ruhsat/harc, pazarlama ve finansman yoktur.
  Bunlar ek_gider_orani ile kaba olarak eklenir.
"""
import csv
from pathlib import Path

VARSAYILAN_PAZAR_DOSYASI = Path(__file__).resolve().parent.parent / "data" / "pazar.csv"


def _negatif_olmamali(deger, ad):
    if deger < 0:
        raise ValueError(f"{ad} negatif olamaz, verilen: {deger}")


def _oran_kontrol(oran, ad):
    if not 0 <= oran < 1:
        raise ValueError(f"{ad} 0 ile 1 arasinda olmali, verilen: {oran}")


def pazar_yukle(yol=VARSAYILAN_PAZAR_DOSYASI):
    """CSV'den {mahalle (kucuk harf): m2_fiyat} sozlugu dondurur."""
    fiyatlar = {}
    with open(yol, newline="", encoding="utf-8") as f:
        for satir in csv.DictReader(f):
            fiyatlar[satir["mahalle"].strip().lower()] = float(satir["m2_fiyat"])
    return fiyatlar


def m2_fiyati(mahalle, fiyatlar=None):
    if fiyatlar is None:
        fiyatlar = pazar_yukle()
    anahtar = mahalle.strip().lower()
    if anahtar not in fiyatlar:
        raise KeyError(f"'{mahalle}' icin fiyat yok. Mevcut: {sorted(fiyatlar)}")
    return fiyatlar[anahtar]


def satis_geliri(adetler, buyuklukler, m2_fiyat, tip_carpani=None):
    """Daire adetleri x buyukluk x m2 fiyati.

    tip_carpani: ornegin {"1+1": 1.05} -> kucuk daireler m2 basina daha pahali
    satiliyorsa. Verilmeyen tipler 1.0 kabul edilir.
    """
    _negatif_olmamali(m2_fiyat, "m2 fiyati")
    tip_carpani = tip_carpani or {}
    tip_bazinda = {}
    for tip, adet in adetler.items():
        _negatif_olmamali(adet, f"{tip} adedi")
        if tip not in buyuklukler:
            raise ValueError(f"'{tip}' icin buyukluk tanimli degil")
        carpan = tip_carpani.get(tip, 1.0)
        tip_bazinda[tip] = adet * buyuklukler[tip] * m2_fiyat * carpan
    return {"toplam": sum(tip_bazinda.values()), "tip_bazinda": tip_bazinda}


def kar_hesapla(gelir, insaat_maliyeti, arsa_bedeli=0, arsa_sahibi_payi=0,
                ek_gider_orani=0):
    """Muteahhit karini hesaplar.

    arsa_bedeli: arsa satin alindiysa odenen tutar.
    arsa_sahibi_payi: kat karsiliginda arsa sahibine birakilan gelir orani
        (or. 0.45 = dairelerin %45'i). Genelde ikisinden biri kullanilir.
    ek_gider_orani: insaat maliyetine eklenen oran (KDV, ruhsat, pazarlama...).
    """
    for deger, ad in [(gelir, "Gelir"), (insaat_maliyeti, "Insaat maliyeti"),
                      (arsa_bedeli, "Arsa bedeli"), (ek_gider_orani, "Ek gider orani")]:
        _negatif_olmamali(deger, ad)
    _oran_kontrol(arsa_sahibi_payi, "Arsa sahibi payi")

    musteahhit_geliri = gelir * (1 - arsa_sahibi_payi)
    ek_gider = insaat_maliyeti * ek_gider_orani
    toplam_gider = insaat_maliyeti + ek_gider + arsa_bedeli
    kar = musteahhit_geliri - toplam_gider
    return {
        "brut_gelir": gelir,
        "arsa_sahibine_kalan": gelir - musteahhit_geliri,
        "musteahhit_geliri": musteahhit_geliri,
        "ek_gider": ek_gider,
        "toplam_gider": toplam_gider,
        "kar": kar,
        "kar_marji": kar / toplam_gider if toplam_gider else None,
    }
