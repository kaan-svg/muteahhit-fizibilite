"""Daire dagilimi: toplam insaat alanindan kac daire ciktigini hesaplar."""

import math

# Varsayilan brut daire buyuklukleri (m2). Bunlar baslangic tahminleri;
# Alanya verisi gelince gercek degerlerle guncellenecek.
VARSAYILAN_BUYUKLUKLER = {"1+1": 60, "2+1": 95, "3+1": 130}

# Merdiven, koridor, asansor gibi ortak alanlarin toplam alandan aldigi pay.
VARSAYILAN_ORTAK_ALAN_ORANI = 0.15

_EPS = 1e-9


def kullanilabilir_alan(toplam_alan, ortak_alan_orani=VARSAYILAN_ORTAK_ALAN_ORANI):
    """Ortak alanlar dusuldukten sonra dairelere kalan alan (m2)."""
    if toplam_alan <= 0:
        raise ValueError(f"Toplam alan 0'dan buyuk olmali, verilen: {toplam_alan}")
    if not 0 <= ortak_alan_orani < 1:
        raise ValueError(f"Ortak alan orani 0 ile 1 arasinda olmali, verilen: {ortak_alan_orani}")
    return toplam_alan * (1 - ortak_alan_orani)


def daire_dagilimi(alan, oranlar, buyuklukler=None):
    """Alani verilen oranlara gore daire tiplerine boler.

    alan: dairelere ayrilacak alan (m2)
    oranlar: her tipe ayrilacak alan payi, orn. {"1+1": 0.4, "2+1": 0.6}; toplami 1 olmali
    buyuklukler: her tipin brut m2'si; verilmezse VARSAYILAN_BUYUKLUKLER

    Donus: {"adetler": {...}, "kullanilan_alan": m2, "artan_alan": m2}
    """
    if alan <= 0:
        raise ValueError(f"Alan 0'dan buyuk olmali, verilen: {alan}")
    if not oranlar:
        raise ValueError("En az bir daire tipi verilmeli")
    if any(o < 0 for o in oranlar.values()):
        raise ValueError("Oranlar negatif olamaz")
    if abs(sum(oranlar.values()) - 1) > 1e-6:
        raise ValueError(f"Oranlarin toplami 1 olmali, verilen: {sum(oranlar.values())}")

    buyuklukler = buyuklukler or VARSAYILAN_BUYUKLUKLER
    adetler = {}
    kullanilan = 0.0
    for tip, oran in oranlar.items():
        if tip not in buyuklukler:
            raise ValueError(f"'{tip}' icin daire buyuklugu tanimli degil")
        boyut = buyuklukler[tip]
        if boyut <= 0:
            raise ValueError(f"'{tip}' buyuklugu 0'dan buyuk olmali")
        adet = math.floor(alan * oran / boyut + _EPS)
        adetler[tip] = adet
        kullanilan += adet * boyut

    return {
        "adetler": adetler,
        "kullanilan_alan": kullanilan,
        "artan_alan": alan - kullanilan,
    }
