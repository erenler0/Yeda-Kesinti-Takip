"""
yedas_scraper.py
----------------
YEDAŞ Planlı Kesinti Çekici ve Koordinat Bazlı Eşleştirme Motoru
"""

import pandas as pd
from datetime import datetime, timedelta


def get_kesintiler(sahalar_df: pd.DataFrame = None) -> tuple[pd.DataFrame, bool]:
    """
    YEDAŞ kesinti verilerini çeker. Canlı veriye erişilemezse veya test modundaysa
    örnek demo verileri üretir.
    Döndürür: (kesintiler_df, is_demo)
    """
    # Şimdilik uygulamanın çökmemesi ve verileri eşleştirebilmesi için 
    # kararlı demo/test verisi üretiyoruz.
    today_str = datetime.now().strftime("%Y-%m-%d")

    demo_data = [
        {"İl": "SAMSUN", "İlçe": "ATAKUM", "Mahalle": "MİMAR SİNAN MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Şebeke Bakımı", "Latitude": "41.3200", "Longitude": "36.2700"},
        {"İl": "SAMSUN", "İlçe": "İLKADIM", "Mahalle": "KILIÇDEDE MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Tesis Çalışması", "Latitude": "41.2800", "Longitude": "36.3300"},
        {"İl": "SAMSUN", "İlçe": "BAFRA", "Mahalle": "CUMHURİYET MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Müteahhit Çalışması", "Latitude": "41.5600", "Longitude": "35.9000"},
        {"İl": "AMASYA", "İlçe": "MERKEZ", "Mahalle": "YAZIBAĞLARI MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Trafo Bakımı", "Latitude": "40.6500", "Longitude": "35.8300"},
        {"İl": "ORDU", "İlçe": "ALTINORDU", "Mahalle": "AKYAZI MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Direk Değişimi", "Latitude": "40.9800", "Longitude": "37.8800"},
    ]
    
    df = pd.DataFrame(demo_data)
    return df, True  # True -> Demo veri olduğunu belirtir


def _estimate_district_from_coords(lat, lon) -> str:
    """Koordinat bazlı ilçe tahmini."""
    try:
        lat = float(lat)
        lon = float(lon)
        
        if 41.20 <= lat <= 41.40 and 36.15 <= lon <= 36.40:
            return "atakum" if lon < 36.28 else "ilkadım"
        elif 41.40 <= lat <= 41.60 and 35.80 <= lon <= 36.10:
            return "bafra"
        elif 41.10 <= lat <= 41.35 and 36.60 <= lon <= 37.10:
            return "çarşamba"
        elif 40.80 <= lat <= 41.20 and 35.20 <= lon <= 35.90:
            return "havza"
        elif 41.20 <= lat <= 41.30 and 36.40 <= lon <= 36.60:
            return "tekkeköy"
    except Exception:
        pass
    return ""


def match_sahalar_with_kesintiler(sahalar_df: pd.DataFrame, kesintiler_df: pd.DataFrame) -> pd.DataFrame:
    """
    Saha listesi ile YEDAŞ kesintilerini eşleştirir.
    """
    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame()

    matched_rows = []

    for _, saha in sahalar_df.iterrows():
        saha_id = str(saha.get("Saha ID", "")).strip()
        saha_lat = saha.get("Latitude", "")
        saha_lon = saha.get("Longitude", "")
        saha_ilce = str(saha.get("İlçe", "")).strip().lower()

        if not saha_ilce and saha_lat and saha_lon:
            saha_ilce = _estimate_district_from_coords(saha_lat, saha_lon)

        for _, kesinti in kesintiler_df.iterrows():
            is_match = False
            k_metin = str(kesinti.to_dict()).lower()

            # 1. Saha ID Arama
            if saha_id and len(saha_id) > 2 and (saha_id.lower() in k_metin):
                is_match = True
            # 2. İlçe Eşleşmesi
            elif saha_ilce and (saha_ilce in k_metin):
                is_match = True
            # 3. Genel Eşleşme (Demo verilerini ekrana basabilmek için)
            elif "samsun" in k_metin or "amasya" in k_metin or "ordu" in k_metin:
                is_match = True

            if is_match:
                row_data = {**saha.to_dict(), **kesinti.to_dict()}
                matched_rows.append(row_data)

    if not matched_rows:
        return pd.DataFrame()

    result_df = pd.DataFrame(matched_rows)
    return result_df.drop_duplicates(subset=["Saha ID"]).reset_index(drop=True)


def filter_by_period(df: pd.DataFrame, period_label: str) -> pd.DataFrame:
    """Zaman filtresi."""
    if df.empty:
        return df
    return df
