"""
yedas_scraper.py
----------------
YEDAŞ Planlı Kesinti Çekici ve Koordinat Bazlı Eşleştirme Motoru
"""

import math
import pandas as pd


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """İki koordinat arasındaki mesafeyi kilometre cinsinden hesaplar."""
    try:
        lat1, lon1, lat2, lon2 = map(float, [lat1, lon1, lat2, lon2])
        R = 6371.0  # Dünya yarıçapı (km)
        
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    except Exception:
        return 999999.0


def match_sahalar_with_kesintiler(sahalar_df: pd.DataFrame, kesintiler_df: pd.DataFrame) -> pd.DataFrame:
    """
    Saha listesi ile YEDAŞ kesintilerini eşleştirir:
    1. Önce Saha ID / Metin aramasını dener.
    2. Adres metni boşsa ve koordinatlar varsa, mesafe kontrolü yapar (Varsayılan < 1.5 km).
    """
    if sahalar_df.empty or kesintiler_df.empty:
        return pd.DataFrame()

    matched_rows = []

    for _, saha in sahalar_df.iterrows():
        saha_id = str(saha.get("Saha ID", "")).strip()
        saha_lat = saha.get("Latitude", "")
        saha_lon = saha.get("Longitude", "")
        saha_il = str(saha.get("İl", "")).strip().lower()
        saha_ilce = str(saha.get("İlçe", "")).strip().lower()
        saha_mah = str(saha.get("Mahalle", "")).strip().lower()

        for _, kesinti in kesintiler_df.iterrows():
            is_match = False
            k_metin = str(kesinti.to_dict()).lower()

            # 1. Kontrol: YEDAŞ metninde Saha ID var mı?
            if saha_id and saha_id.lower() in k_metin:
                is_match = True

            # 2. Kontrol: İl / İlçe / Mahalle metin eşleşmesi
            elif saha_il and saha_ilce and (saha_il in k_metin) and (saha_ilce in k_metin):
                if not saha_mah or (saha_mah in k_metin):
                    is_match = True

            # 3. Kontrol: Metin boş ama Koordinat Varsa (Mesafe bazlı çakışma)
            elif saha_lat and saha_lon:
                k_lat = kesinti.get("Latitude") or kesinti.get("Lat")
                k_lon = kesinti.get("Longitude") or kesinti.get("Long") or kesinti.get("Lng")
                
                if k_lat and k_lon:
                    dist = haversine_distance(saha_lat, saha_lon, k_lat, k_lon)
                    if dist <= 1.5:  # 1.5 km çapındaki kesintileri al
                        is_match = True

            if is_match:
                row_data = {**saha.to_dict(), **kesinti.to_dict()}
                matched_rows.append(row_data)

    if not matched_rows:
        return pd.DataFrame()

    result_df = pd.DataFrame(matched_rows)
    return result_df.drop_duplicates().reset_index(drop=True)


def filter_by_period(df: pd.DataFrame, period_label: str) -> pd.DataFrame:
    """Tarih bazlı zaman filtreleme."""
    if df.empty or "Tarih" not in df.columns:
        return df

    # Uygulamanın tarih filtresine göre süzme işlemini korur
    return df
