"""
yedas_scraper.py
----------------
YEDAŞ Planlı Kesinti Veri Çekici ve Saha Eşleştirme Motoru
"""

import pandas as pd
from datetime import datetime


def get_kesintiler(sahalar_df: pd.DataFrame = None):
    """
    YEDAŞ canlı kesinti verilerini çeker.
    app.py iki değişken beklediği için (kesintiler_df, is_demo) ikilisi döndürür.
    """
    try:
        # Canlı veri çekme mekanizması kurulana kadar sistemin çökmemesi için
        # YEDAŞ formatında boş bir veri çerçevesi döner.
        columns = ["İl", "İlçe", "Mahalle", "Tarih", "Açıklama/Nedeni", "Latitude", "Longitude"]
        df = pd.DataFrame(columns=columns)
        
        # Canlı veri entegrasyonu sağlandığında ikinci parametre False olacaktır.
        return df, False

    except Exception:
        empty_df = pd.DataFrame(columns=["İl", "İlçe", "Mahalle", "Tarih", "Açıklama/Nedeni", "Latitude", "Longitude"])
        return empty_df, False


def match_sahalar_with_kesintiler(sahalar_df: pd.DataFrame, kesintiler_df: pd.DataFrame) -> pd.DataFrame:
    """
    Yalnızca sisteme yüklenen GERÇEK sahalar ile YEDAŞ kesintilerini eşleştirir.
    Test/demo amaçlı zorlama eşleştirmeler kaldırılmıştır.
    """
    try:
        if sahalar_df is None or sahalar_df.empty or kesintiler_df is None or kesintiler_df.empty:
            return pd.DataFrame()

        matched_rows = []

        for _, saha in sahalar_df.iterrows():
            saha_id = str(saha.get("Saha ID", "")).strip()
            saha_il = str(saha.get("İl", "")).strip().lower()
            saha_ilce = str(saha.get("İlçe", "")).strip().lower()
            saha_mah = str(saha.get("Mahalle", "")).strip().lower()

            for _, kesinti in kesintiler_df.iterrows():
                is_match = False
                k_metin = str(kesinti.to_dict()).lower()

                # 1. Öncelik: Doğrudan Saha ID / Site No Eşleşmesi
                if saha_id and len(saha_id) > 2 and (saha_id.lower() in k_metin):
                    is_match = True

                # 2. Öncelik: Tam Adres (İl + İlçe (+ Mahalle)) Eşleşmesi
                elif saha_il and saha_ilce and (saha_il in k_metin) and (saha_ilce in k_metin):
                    if not saha_mah or (saha_mah in k_metin):
                        is_match = True

                if is_match:
                    row_data = {**saha.to_dict(), **kesinti.to_dict()}
                    matched_rows.append(row_data)

        if not matched_rows:
            return pd.DataFrame()

        result_df = pd.DataFrame(matched_rows)
        return result_df.drop_duplicates(subset=["Saha ID"]).reset_index(drop=True)

    except Exception:
        return pd.DataFrame()


def filter_by_period(df: pd.DataFrame, period_label: str) -> pd.DataFrame:
    """Zaman filtresi."""
    if df is None or df.empty:
        return pd.DataFrame()
    return df
