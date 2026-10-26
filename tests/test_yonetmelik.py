"""RAG testleri. Ollama ve gercek PDF gerekmez: ornek metin ve kelime tabanli
sahte bir embedding kullanilir."""
import re

import pytest

from src import yonetmelik
from src.yonetmelik import _parcala, ara, indeks_kur, maddelere_bol

ORNEK = """BİRİNCİ BÖLÜM
Amaç, Kapsam, Dayanak ve Tanımlar
Amaç
MADDE 1 – (1) Bu Yönetmeliğin amacı; planlı alanlarda yapılaşmayı düzenlemektir.
Tanımlar
MADDE 4 – (1) Bu Yönetmelikte geçen; bodrum kat: tabii zemin altındaki kattır.
İKİNCİ BÖLÜM
Yapılaşma
Emsal hesabı
MADDE 22 – (1) Açık çıkmalar ve balkonlar emsal hesabına dahil edilmez.
(2) Otopark alanları emsal hesabına dahil edilmez.
Uyum
GEÇİCİ MADDE 1 – (1) Mevcut ruhsatlar geçerlidir.
"""


def sahte_embed(metinler):
    """Her metni sabit bir kelime listesindeki kelimelerin sayisina gore vektore cevirir."""
    sozluk = ["amac", "bodrum", "balkon", "emsal", "otopark", "ruhsat", "yapilasma"]
    def vektor(m):
        m = m.lower().replace("ç", "c").replace("ı", "i").replace("ş", "s")
        return [len(re.findall(k, m)) + 0.01 for k in sozluk]
    return [vektor(m) for m in metinler]


def test_maddeler_ve_basliklar():
    p = maddelere_bol(ORNEK)
    assert [x["madde"] for x in p] == ["1", "4", "22", "Geçici 1"]
    assert [x["baslik"] for x in p] == ["Amaç", "Tanımlar", "Emsal hesabı", "Uyum"]


def test_sonraki_baslik_ve_bolum_govdeye_karismaz():
    p = {x["madde"]: x["metin"] for x in maddelere_bol(ORNEK)}
    assert "Tanımlar" not in p["1"]
    assert "BÖLÜM" not in p["4"]
    assert "Uyum" not in p["22"]
    assert p["22"].startswith("MADDE 22")


def test_uzun_madde_fikralardan_bolunur():
    uzun = " ".join(f"({i}) " + "kelime " * 60 for i in range(1, 11))
    parcalar = _parcala(uzun, maks=1000)
    assert len(parcalar) > 1
    assert all(len(x) <= 1000 for x in parcalar)
    assert all(x.startswith("(") for x in parcalar)


def test_ara_dogru_maddeyi_bulur():
    indeks = indeks_kur(maddelere_bol(ORNEK), embed=sahte_embed, yol=None)
    sonuc = ara("balkon emsale dahil mi", k=1, indeks=indeks, embed=sahte_embed)
    assert sonuc[0]["madde"] == "22"
    sonuc = ara("bodrum kat nedir", k=1, indeks=indeks, embed=sahte_embed)
    assert sonuc[0]["madde"] == "4"


def test_indeks_yoksa_anlasilir_hata(tmp_path):
    with pytest.raises(FileNotFoundError, match="kur"):
        yonetmelik.indeks_yukle(tmp_path / "yok.json")


def test_arac_indeks_yoksa_hata_doner(monkeypatch, tmp_path):
    from src.araclar import arac_calistir
    monkeypatch.setattr(yonetmelik, "INDEKS_YOLU", tmp_path / "yok.json")
    sonuc = arac_calistir("yonetmelik_ara", {"soru": "balkon"})
    assert "hata" in sonuc
