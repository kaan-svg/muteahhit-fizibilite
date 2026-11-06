import csv

import pytest

from src.ilanlar import aykirilari_ayir, oku, ozet, pazar_guncelle

BASLIK = "mahalle,tip,brut_m2,fiyat_tl,site_havuz,ilan_tarihi\n"


def yaz(tmp_path, satirlar, ad="ilanlar.csv"):
    yol = tmp_path / ad
    yol.write_text(BASLIK + "\n".join(satirlar) + "\n", encoding="utf-8")
    return yol


def ornek(tmp_path):
    # Mahmutlar: 3 x 1+1 (60 m2, 60.000 TL/m2) + 3 x 2+1 (100 m2, 55.000 TL/m2)
    satirlar = [f"Mahmutlar,1+1,60,{60 * 60_000},evet,2026-11-06" for _ in range(3)]
    satirlar += [f"Mahmutlar,2+1,100,{100 * 55_000},hayir,2026-11-06" for _ in range(3)]
    satirlar += [f"Oba,1+1,55,{55 * 70_000},evet,2026-11-06" for _ in range(2)]
    satirlar += ["Mahmutlar,3+1,250,90000000,evet,2026-11-06"]   # aykiri (360.000 TL/m2)
    return yaz(tmp_path, satirlar)


@pytest.mark.parametrize("fiyat, beklenen", [
    ('"4.250.000"', 4_250_000), ("4250000", 4_250_000), ('"4.250.000 TL"', 4_250_000), ("4250000.5", 4_250_000.5),
])
def test_fiyat_bicimleri(tmp_path, fiyat, beklenen):
    ilan = oku(yaz(tmp_path, [f"Oba,1+1,62,{fiyat},evet,2026-11-06"]))[0]
    assert ilan["fiyat_tl"] == beklenen


def test_tip_ve_m2_bicimleri(tmp_path):
    ilan = oku(yaz(tmp_path, ['Oba, 2 + 1 ,"62,5 m2",5000000,var,2026-11-06']))[0]
    assert ilan["tip"] == "2+1" and ilan["brut_m2"] == 62.5 and ilan["site_havuz"]


def test_bos_satirlar_atlanir(tmp_path):
    assert len(oku(yaz(tmp_path, ["Oba,1+1,60,4000000,,", ",,,,,"]))) == 1


@pytest.mark.parametrize("satir, mesaj", [
    ("Oba,1+1,altmis,4000000,,", "brut_m2"),
    ("Oba,1+1,60,0,,", "fiyat_tl"),
    ("Oba,bir arti bir,60,4000000,,", "tip"),
])
def test_hatali_satir_satir_numarasiyla(tmp_path, satir, mesaj):
    with pytest.raises(ValueError, match=f"2. satir: {mesaj}"):
        oku(yaz(tmp_path, [satir]))


def test_eksik_sutun(tmp_path):
    yol = tmp_path / "x.csv"
    yol.write_text("mahalle,fiyat\nOba,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="eksik sutun"):
        oku(yol)


def test_aykiri_ilan_atilir(tmp_path):
    temiz, atilan = aykirilari_ayir(oku(ornek(tmp_path)))
    assert len(atilan) == 1 and atilan[0]["tip"] == "3+1"


def test_ozet(tmp_path):
    o = ozet(oku(ornek(tmp_path)))
    assert o["kullanilan"] == 8
    assert o["mahalleler"]["Mahmutlar"] == {"ilan": 6, "m2_fiyat": 57_500}
    assert o["tipler"]["1+1"]["brut_m2"] == 60   # medyan(60, 60, 60, 55, 55)
    assert o["tipler"]["2+1"]["tip_carpani"] == pytest.approx(55_000 / 57_500, abs=0.01)


def test_pazar_guncelle_az_ilanli_mahalleye_dokunmaz(tmp_path):
    pazar = tmp_path / "pazar.csv"
    pazar.write_text("mahalle,m2_fiyat,kaynak,tarih\nMahmutlar,58979,emlakjet,2026-09\n"
                     "Oba,67133,emlakjet,2026-09\n", encoding="utf-8")
    guncellenen = pazar_guncelle(ozet(oku(ornek(tmp_path))), pazar, bugun="2026-11")
    assert guncellenen == ["Mahmutlar"]
    satirlar = {r["mahalle"]: r for r in csv.DictReader(open(pazar, encoding="utf-8"))}
    assert satirlar["Mahmutlar"]["m2_fiyat"] == "57500"
    assert "6 ilan" in satirlar["Mahmutlar"]["kaynak"]
    assert satirlar["Oba"]["m2_fiyat"] == "67133"     # 2 ilan: yetersiz, eski deger kalir


def test_turkce_karakterli_mahalle_eslesir(tmp_path):
    pazar = tmp_path / "pazar.csv"
    pazar.write_text("mahalle,m2_fiyat,kaynak,tarih\nCikcilli,66196,emlakjet,2026-09\n", encoding="utf-8")
    satirlar = [f"Çıkcıllı,2+1,100,{100 * 70_000},evet,2026-11-06" for _ in range(5)]
    pazar_guncelle(ozet(oku(yaz(tmp_path, satirlar))), pazar)
    satirlar = list(csv.DictReader(open(pazar, encoding="utf-8")))
    assert len(satirlar) == 1 and satirlar[0]["mahalle"] == "Cikcilli" and satirlar[0]["m2_fiyat"] == "70000"


def test_turkce_excel_csv(tmp_path):
    """Turkce Excel: ';' ayirici, cp1254 kodlama, ondalikta virgul."""
    yol = tmp_path / "excel.csv"
    yol.write_bytes("mahalle;tip;brut_m2;fiyat_tl;site_havuz;ilan_tarihi\n"
                    "Çıkcıllı;2+1;95,5;6.500.000;evet;06.11.2026\n".encode("cp1254"))
    ilan = oku(yol)[0]
    assert ilan["mahalle"] == "Çıkcıllı" and ilan["brut_m2"] == 95.5 and ilan["fiyat_tl"] == 6_500_000
