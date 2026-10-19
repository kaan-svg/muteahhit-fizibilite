"""Insaat maliyeti tahmini.

Kaynak: Cevre, Sehircilik ve Iklim Degisikligi Bakanligi, "2026 Yili Mimarlik ve
Muhendislik Hizmet Bedellerinin Hesabinda Kullanilacak Yapi Yaklasik Birim
Maliyetleri", Resmi Gazete 3 Subat 2026, Sayi 33157.

Bu degerler KDV haric, %15 genel gider ve %10 yuklenici kari dahildir.
Resmi hesaplar (proje bedeli, harc vb.) icin hazirlanir; gercek piyasa maliyeti
genelde farklidir. Bu yuzden `piyasa_carpani` ile yerel veriye gore ayarlanir.
"""

BIRIM_MALIYET_2026 = {  # TL/m2
    "III-A": 19_800,
    "III-B": 21_050,
    "III-C": 23_400,
    "IV-A": 26_450,
    "IV-B": 33_900,
}

# Apartman tipi konut icin tahmini kat yuksekligi (m). Proje belliyse
# gercek yukseklik kullanilmali.
VARSAYILAN_KAT_YUKSEKLIGI = 3.0


def konut_sinifi(kat_sayisi, yapi_yuksekligi=None):
    """Apartman tipi konutun Bakanlik yapi sinifini dondurur.

    III-A: uc kata kadar (dahil)
    III-B: uc kattan fazla ve yukseklik < 21.50 m
    III-C: 21.50 m - 30.50 m
    IV-A : 30.50 m - 51.50 m
    IV-B : 51.50 m uzeri
    """
    if kat_sayisi < 1:
        raise ValueError(f"Kat sayisi en az 1 olmali, verilen: {kat_sayisi}")
    if yapi_yuksekligi is None:
        yapi_yuksekligi = kat_sayisi * VARSAYILAN_KAT_YUKSEKLIGI
    if yapi_yuksekligi <= 0:
        raise ValueError(f"Yapi yuksekligi 0'dan buyuk olmali, verilen: {yapi_yuksekligi}")

    if kat_sayisi <= 3:
        return "III-A"
    if yapi_yuksekligi < 21.50:
        return "III-B"
    if yapi_yuksekligi < 30.50:
        return "III-C"
    if yapi_yuksekligi < 51.50:
        return "IV-A"
    return "IV-B"


def insaat_maliyeti(toplam_alan, sinif, piyasa_carpani=1.0, birim_maliyet=None):
    """Toplam insaat maliyeti (TL, KDV haric).

    toplam_alan: m2
    sinif: "III-B" gibi; birim_maliyet verilirse yok sayilir
    piyasa_carpani: resmi birim maliyeti yerel piyasaya uyarlamak icin (1.0 = resmi deger)
    birim_maliyet: TL/m2'yi dogrudan vermek icin (orn. muteahhitten alinan rakam)
    """
    if toplam_alan <= 0:
        raise ValueError(f"Toplam alan 0'dan buyuk olmali, verilen: {toplam_alan}")
    if piyasa_carpani <= 0:
        raise ValueError(f"Piyasa carpani 0'dan buyuk olmali, verilen: {piyasa_carpani}")

    if birim_maliyet is None:
        if sinif not in BIRIM_MALIYET_2026:
            raise ValueError(f"Bilinmeyen yapi sinifi: {sinif}")
        birim_maliyet = BIRIM_MALIYET_2026[sinif]
    elif birim_maliyet <= 0:
        raise ValueError(f"Birim maliyet 0'dan buyuk olmali, verilen: {birim_maliyet}")

    return toplam_alan * birim_maliyet * piyasa_carpani
