"""Fizibilite zinciri ve senaryo karsilastirmasi.

imar -> daire -> maliyet -> gelir adimlarini tek fonksiyonda birlestirir,
ayni arsa icin farkli varsayimlari yan yana koyar.
"""
from src.daire import VARSAYILAN_BUYUKLUKLER, VARSAYILAN_ORTAK_ALAN_ORANI, daire_dagilimi, kullanilabilir_alan
from src.gelir import kar_hesapla, m2_fiyati, satis_geliri
from src.imar import kat_sayisi, taban_alani, toplam_insaat_alani
from src.maliyet import insaat_maliyeti, konut_sinifi


def fizibilite(arsa_alani, taks, emsal, mahalle, oranlar, max_kat=None,
               buyuklukler=None, ortak_alan_orani=VARSAYILAN_ORTAK_ALAN_ORANI,
               m2_fiyat=None, tip_carpani=None, piyasa_carpani=1.0,
               birim_maliyet=None, arsa_bedeli=0, arsa_sahibi_payi=0,
               ek_gider_orani=0, fiyatlar=None, ad=None):
    """Tek bir senaryonun tum hesabini yapar ve ozet sozluk dondurur."""
    buyuklukler = buyuklukler or VARSAYILAN_BUYUKLUKLER

    kat = kat_sayisi(taks, emsal, max_kat)
    # Kat siniri emsali kullandirmayabilir: alan, taban x kat ile de sinirli.
    alan = min(toplam_insaat_alani(arsa_alani, emsal), taban_alani(arsa_alani, taks) * kat)

    dagilim = daire_dagilimi(kullanilabilir_alan(alan, ortak_alan_orani), oranlar, buyuklukler)
    fiyat = m2_fiyat if m2_fiyat is not None else m2_fiyati(mahalle, fiyatlar)
    gelir = satis_geliri(dagilim["adetler"], buyuklukler, fiyat, tip_carpani)
    sinif = konut_sinifi(kat)
    maliyet = insaat_maliyeti(alan, sinif, piyasa_carpani, birim_maliyet)
    kar = kar_hesapla(gelir["toplam"], maliyet, arsa_bedeli, arsa_sahibi_payi, ek_gider_orani)

    return {
        "ad": ad or mahalle,
        "kat_sayisi": kat,
        "insaat_alani": alan,
        "daireler": dagilim["adetler"],
        "artan_alan": dagilim["artan_alan"],
        "m2_fiyat": fiyat,
        "sinif": sinif,
        "insaat_maliyeti": maliyet,
        **kar,
    }


def karsilastir(temel, varyasyonlar, siralama="kar"):
    """temel: ortak parametreler. varyasyonlar: {ad: degisen parametreler}.

    Her varyasyon temelin ustune yazilir; sonuclar `siralama` alanina gore
    buyukten kucuge siralanir.
    """
    if not varyasyonlar:
        raise ValueError("En az bir varyasyon gerekli")
    sonuclar = [fizibilite(**{**temel, **degisen, "ad": ad})
                for ad, degisen in varyasyonlar.items()]
    return sorted(sonuclar, key=lambda s: s[siralama], reverse=True)


def tablo(sonuclar):
    """Sonuclari terminalde okunabilir bir tabloya cevirir."""
    baslik = f"{'Senaryo':<22}{'Kat':>4}{'Alan m2':>9}{'Daireler':>22}{'Gelir M':>9}{'Gider M':>9}{'Kar M':>8}{'Marj':>7}"
    satirlar = [baslik, "-" * len(baslik)]
    for s in sonuclar:
        daireler = " ".join(f"{a}x{t}" for t, a in s["daireler"].items() if a)
        marj = f"{s['kar_marji']:.0%}" if s["kar_marji"] is not None else "-"
        satirlar.append(
            f"{s['ad'][:21]:<22}{s['kat_sayisi']:>4}{s['insaat_alani']:>9.0f}{daireler:>22}"
            f"{s['brut_gelir'] / 1e6:>9.1f}{s['toplam_gider'] / 1e6:>9.1f}{s['kar'] / 1e6:>8.1f}{marj:>7}"
        )
    return "\n".join(satirlar)


if __name__ == "__main__":
    # Ornek: 1000 m2 arsa, kat karsiligi %45, ek gider %25 (VARSAYIM)
    temel = dict(arsa_alani=1000, taks=0.30, emsal=1.50, mahalle="Mahmutlar",
                 oranlar={"1+1": 0.5, "2+1": 0.5}, arsa_sahibi_payi=0.45,
                 ek_gider_orani=0.25)
    varyasyonlar = {
        "Mahmutlar 50/50": {},
        "Mahmutlar hep 1+1": {"oranlar": {"1+1": 1.0}},
        "Mahmutlar pay %40": {"arsa_sahibi_payi": 0.40},
        "Oba 50/50": {"mahalle": "Oba"},
        "Kestel 50/50": {"mahalle": "Kestel"},
        "Kestel max 4 kat": {"mahalle": "Kestel", "max_kat": 4},
    }
    print(tablo(karsilastir(temel, varyasyonlar)))
