"""Uydurma korumasi: model kullanicinin vermedigi imar degerleriyle hesap yapamaz.

Degerlendirmede model, TAKS ve emsal verilmeyen bir soruda 3 denemenin 3'unde
bu degerleri kendisi uydurup hesap aracini cagirdi. Prompt'taki "tahmin etme"
kurali yetmedi, bu yuzden kontrol kodda.

Kural: arsa_alani, taks ve emsal degerleri kullanicinin mesajlarinda gecmeli.
"TAKS 0,30", "taks %30", "emsal 1.5" gibi yazimlarin hepsi taninir.
"""
import re

KONTROL_EDILEN = ("arsa_alani", "taks", "emsal")
# Istege bagli: bos/0 olabilir, ama doluysa deger kullanicinin mesajinda gecmeli
ISTEGE_BAGLI = ("arsa_sahibi_payi", "ek_gider_orani", "emsal_disi_orani", "m2_fiyat", "max_kat")
HESAP_ARACLARI = ("fizibilite_hesapla", "duyarlilik_analizi")


def _rol(m):
    return m.get("role") if hasattr(m, "get") else getattr(m, "role", None)


def _icerik(m):
    return (m.get("content") if hasattr(m, "get") else getattr(m, "content", "")) or ""


def kullanici_sayilari(mesajlar):
    """Kullanici mesajlarindaki tum sayilar. '1.000' -> 1000, '0,30' -> 0.3"""
    sayilar = set()
    for m in mesajlar:
        if _rol(m) != "user":
            continue
        metin = _icerik(m)
        metin = re.sub(r"(\d)\.(\d{3})(?!\d)", r"\1\2", metin)   # binlik ayirici: 1.000
        for s in re.findall(r"\d+(?:[.,]\d+)?", metin):
            sayilar.add(round(float(s.replace(",", ".")), 4))
    return sayilar


def _var_mi(deger, sayilar):
    try:
        x = float(str(deger).replace("%", "").replace(",", "."))
    except ValueError:
        return False
    adaylar = {round(x, 4), round(x * 100, 4), round(x / 100, 4)}  # 0.30 <-> %30
    return any(abs(a - s) < 1e-6 for a in adaylar for s in sayilar)


def uydurma_kontrol(ad, argumanlar, mesajlar):
    """Sorun varsa modele donecek hata sozlugunu, yoksa None dondurur."""
    if ad not in HESAP_ARACLARI or not isinstance(argumanlar, dict):
        return None
    a = {str(k).lower(): v for k, v in argumanlar.items()}
    degisen = None
    if ad == "duyarlilik_analizi":
        degisen = str(a.get("parametre", "")).lower()  # denenen deger kullanicidan gelmek zorunda degil
        a = {str(k).lower(): v for k, v in (a.get("arsa") or {}).items()}

    sayilar = kullanici_sayilari(mesajlar)
    eksik = [k for k in KONTROL_EDILEN
             if k != degisen and (a.get(k) in (None, "") or not _var_mi(a[k], sayilar))]
    uydurulan = [k for k in ISTEGE_BAGLI
                 if k != degisen and a.get(k) not in (None, "", 0, "0") and not _var_mi(a[k], sayilar)]
    if uydurulan and not eksik:
        return {"hata": (
            f"Kullanici su degerleri vermedi: {', '.join(uydurulan)}. Bu alanlari bos birakip "
            "araci tekrar cagir; kullanici istemedikce bu degerleri ekleme.")}
    if not eksik:
        return None
    return {"hata": (
        f"Kullanici su degerleri vermedi: {', '.join(eksik)}. Bu degerleri tahmin etme ve "
        "hesap yapma. Kullaniciya bu degerleri sor (imar durumu belgesinde yazar)."
    )}
