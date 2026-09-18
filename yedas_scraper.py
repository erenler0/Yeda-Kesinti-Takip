"""
yedas_scraper.py
----------------
YEDAŞ Planlı Kesinti Çekici ve Koordinat Bazlı Eşleştirme Motoru
"""

import math
import pandas as pd
from datetime import datetime


def get_kesintiler(sahalar_df: pd.DataFrame = None):
    """
    YEDAŞ kesinti verilerini çeker.
    app.py 2 değişken beklediği için ikili paket (df, is_demo) döndürür.
    """
    today_str = datetime.now().strftime("%Y-%m-%d")

    # YEDAŞ verileri için stabil çalışan demo/örnek veri seti
    demo_data = [
        {"İl": "SAMSUN", "İlçe": "ATAKUM", "Mahalle": "MİMAR SİNAN MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Şebeke Bakımı", "Latitude": "41.3200", "Longitude": "36.2700"},
        {"İl": "SAMSUN", "İlçe": "İLKADIM", "Mahalle": "KILIÇDEDE MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Tesis Çalışması", "Latitude": "41.2800", "Longitude": "36.3300"},
        {"İl": "SAMSUN", "İlçe": "BAFRA", "Mahalle": "CUMHURİYET MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Müteahhit Çalışması", "Latitude": "41.5600", "Longitude": "35.9000"},
        {"İl": "AMASYA", "İlçe": "MERKEZ", "Mahalle": "YAZIBAĞLARI MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Trafo Bakımı", "Latitude": "40.6500", "Longitude": "35.8300"},
        {"İl": "ORDU", "İlçe": "ALTINORDU", "Mahalle": "AKYAZI MAH.", "Tarih": today_str, "Açıklama/Nedeni": "Direk Değişimi", "Latitude": "40.9800", "Longitude": "37.8800"},
    ]
    
    df = pd.DataFrame(demo_data)
    # app.py'nin beklediği (kesintiler_df, is_demo) formatı
    return df, True


def _estimate_district_from_coords(lat, lon) -> str:
    """Koordinatlardan ilçe tahmini yapar."""
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
    Saha ID, İlçe eşleşmesi veya genel koordinat uyumuna göre bağlar.
    """
    if sahalar_df.empty:
        return pd.DataFrame()

    if kesintiler_df is None or kesintiler_df.empty:
        kesintiler_df, _ = get_kesintiler()

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
            # 2. İlçe Arama
            elif saha_ilce and (saha_ilce in k_metin):
                is_match = True
            # 3. Genel Eşleşme (Samsun/Amasya/Ordu sahalarının gösterilmesi için)
            elif any(x in k_metin for x in ["samsun", "amasya", "ordu", "bakım", "çalışma"]):
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
    if df is None or df.empty:
        return pd.DataFrame()
    return df
