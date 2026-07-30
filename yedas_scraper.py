"""
yedas_scraper.py
------------------
YEDAŞ Planlı Kesinti Verisi Çekme ve Eşleştirme Modülü (Canlı API Entegreli)
"""

import random
from datetime import datetime, timedelta
import pandas as pd
import requests

# Gerçek YEDAŞ Canlı API Endpoint'i
YEDAS_API_URL = "https://www.yedas.com/api/planli-kesinti-harita"

# Eşleştirme ve gösterim için standart kesinti tablosu sütunları
KESINTI_COLUMNS = ["İl", "İlçe", "Mahalle", "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]


def _normalize_text(x: str) -> str:
    """Türkçe karakter/boşluk/büyük-küçük harf farklarını yok sayarak karşılaştırma anahtarı üretir."""
    if x is None:
        return ""
    x = str(x).strip().lower()
    replacements = {"ı": "i", "İ": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
    for src, tgt in replacements.items():
        x = x.replace(src, tgt)
    return x


def _fetch_live_data() -> pd.DataFrame:
    """YEDAŞ API'sinden canlı JSON verisini çeker ve DataFrame'e dönüştürür."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*"
        }
        resp = requests.get(YEDAS_API_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        
        data = resp.json()
        
        # Eğer gelen veri bir liste veya iç içe obje ise duruma göre parse et
        # YEDAŞ verisinde anahtar listesini kontrol et
        items = data if isinstance(data, list) else data.get("data", data.get("items", []))
        
        rows = []
        for item in items:
            # API'den gelen alan adlarına göre esnek okuma yap
            il = item.get("il") or item.get("ilName") or item.get("province") or ""
            ilce = item.get("ilce") or item.get("ilceName") or item.get("district") or ""
            mahalle = item.get("mahalle") or item.get("mahalleName") or item.get("neighborhood") or ""
            baslangic = item.get("baslangicTarihi") or item.get("startDate") or item.get("baslangic") or ""
            bitis = item.get("bitisTarihi") or item.get("endDate") or item.get("bitis") or ""
            aciklama = item.get("neden") or item.get("aciklama") or item.get("reason") or ""

            rows.append({
                "İl": str(il).strip(),
                "İlçe": str(ilce).strip(),
                "Mahalle": str(mahalle).strip(),
                "Kesinti Başlangıç Saati": str(baslangic).strip(),
                "Kesinti Bitiş Saati": str(bitis).strip(),
                "Açıklama/Nedeni": str(aciklama).strip(),
            })

        df = pd.DataFrame(rows, columns=KESINTI_COLUMNS)
        return df

    except Exception as e:
        # Ağ hatası veya API uyumsuzluğunda sessizce boş dön (Demo veriye düşer)
        return pd.DataFrame(columns=KESINTI_COLUMNS)


def _generate_demo_data(sahalar_df: pd.DataFrame) -> pd.DataFrame:
    """Canlı veri çekilemediğinde test amaçlı sahte veri üretir."""
    if sahalar_df.empty:
        return pd.DataFrame(columns=KESINTI_COLUMNS)

    nedenler = [
        "Trafo bakımı", "Hat yenileme çalışması", "Şalt sahası bakımı",
        "Direk değişimi", "Enerji nakil hattı bakımı", "Altyapı iyileştirme çalışması",
    ]

    sample_size = min(len(sahalar_df), max(1, len(sahalar_df) // 3))
    sample = sahalar_df.sample(n=sample_size, random_state=None)

    rows = []
    now = datetime.now()
    for _, saha in sample.iterrows():
        gun_offset = random.choice([0, 0, 1, 2, 3, 5, 6])
        baslangic_dt = now.replace(hour=random.choice([8, 9, 10, 13]), minute=0, second=0) + timedelta(days=gun_offset)
        bitis_dt = baslangic_dt + timedelta(hours=random.choice([2, 3, 4, 6]))
        rows.append({
            "İl": saha["İl"],
            "İlçe": saha["İlçe"],
            "Mahalle": saha["Mahalle"],
            "Kesinti Başlangıç Saati": baslangic_dt.strftime("%d.%m.%Y %H:%M"),
            "Kesinti Bitiş Saati": bitis_dt.strftime("%d.%m.%Y %H:%M"),
            "Açıklama/Nedeni": random.choice(nedenler),
        })

    return pd.DataFrame(rows, columns=KESINTI_COLUMNS)


def get_kesintiler(sahalar_df: pd.DataFrame):
    """Canlı veriyi çekmeyi dener, boşsa demo veriye düşer."""
    live_df = _fetch_live_data()
    if not live_df.empty:
        return live_df, False
    demo_df = _generate_demo_data(sahalar_df)
    return demo_df, True


def match_sahalar_with_kesintiler(sahalar_df: pd.DataFrame, kesintiler_df: pd.DataFrame) -> pd.DataFrame:
    """Kayıtlı sahaları YEDAŞ kesinti verisiyle eşleştirir."""
    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame(columns=[
            "Saha ID", "İl", "İlçe", "Mahalle",
            "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"
        ])

    s = sahalar_df.copy()
    k = kesintiler_df.copy()

    s["_key"] = (s["İl"].map(_normalize_text) + "|" + s["İlçe"].map(_normalize_text) + "|" + s["Mahalle"].map(_normalize_text))
    k["_key"] = (k["İl"].map(_normalize_text) + "|" + k["İlçe"].map(_normalize_text) + "|" + k["Mahalle"].map(_normalize_text))

    merged = pd.merge(s, k.drop(columns=["İl", "İlçe", "Mahalle"]), on="_key", how="inner")
    merged = merged.drop(columns=["_key"])

    return merged[["Saha ID", "İl", "İlçe", "Mahalle",
                    "Kesinti Başlangıç Saati", "Kesinti Bitiş Saati", "Açıklama/Nedeni"]]


def filter_by_period(df: pd.DataFrame, period: str) -> pd.DataFrame:
    """Kesinti tablosunu tarih filtresine göre süzmektedir."""
    if df.empty:
        return df

    days_map = {"Bugün": 0, "3 Günlük": 3, "7 Günlük": 7}
    days = days_map.get(period, 0)

    now = datetime.now()
    start_limit = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_limit = start_limit + timedelta(days=days + 1)

    def _parse_dt(val):
        try:
            return datetime.strptime(str(val), "%d.%m.%Y %H:%M")
        except Exception:
            try:
                # ISO Formatında gelirse (ör: 2026-07-30T09:00:00)
                return datetime.fromisoformat(str(val))
            except Exception:
                return None

    df = df.copy()
    df["_baslangic_dt"] = df["Kesinti Başlangıç Saati"].map(_parse_dt)
    
    # Tarih okunamazsa satırı gizlememek için varsayılan tut
    valid_dates = df["_baslangic_dt"].notna()
    if valid_dates.any():
        filtered = df[valid_dates & (df["_baslangic_dt"] >= start_limit) & (df["_baslangic_dt"] < end_limit)]
        return filtered.drop(columns=["_baslangic_dt"]).reset_index(drop=True)
    
    return df.drop(columns=["_baslangic_dt"])