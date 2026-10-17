"""Imar (zoning) calculations: footprint, total buildable area and floor count."""

import math

# Ondalik sayilarda 0.6 / 0.2 = 2.9999999999999996 gibi kucuk hatalar olur.
# Asagi yuvarlamadan once bu kucuk payi ekleyerek 3'un 2'ye dusmesini onluyoruz.
_EPS = 1e-9


def _pozitif_olmali(deger, ad):
    if deger <= 0:
        raise ValueError(f"{ad} 0'dan buyuk olmali, verilen: {deger}")


def _taks_kontrol(taks):
    _pozitif_olmali(taks, "TAKS")
    if taks > 1:
        raise ValueError(f"TAKS 1'den buyuk olamaz, verilen: {taks}")


def taban_alani(arsa_alani, taks):
    """Binanin zemine oturdugu en buyuk alan (m2) = arsa alani x TAKS."""
    _pozitif_olmali(arsa_alani, "Arsa alani")
    _taks_kontrol(taks)
    return arsa_alani * taks


def toplam_insaat_alani(arsa_alani, emsal):
    """Tum katlarin toplam alani (m2) = arsa alani x emsal (KAKS)."""
    _pozitif_olmali(arsa_alani, "Arsa alani")
    _pozitif_olmali(emsal, "Emsal")
    return arsa_alani * emsal


def kat_sayisi(taks, emsal, max_kat=None):
    """Sigan tam kat sayisi = emsal / TAKS (asagi yuvarlanir).

    Imar plani bir kat siniri (max_kat) koyuyorsa ikisinden kucugu gecerlidir.
    """
    _taks_kontrol(taks)
    _pozitif_olmali(emsal, "Emsal")
    kat = math.floor(emsal / taks + _EPS)
    if max_kat is not None:
        _pozitif_olmali(max_kat, "Maksimum kat")
        kat = min(kat, max_kat)
    return kat
