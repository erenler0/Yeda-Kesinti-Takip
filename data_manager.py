"""
data_manager.py
----------------
YEDAŞ Planlı Kesinti Takip Uygulaması - Esnek Veri Yönetimi Modülü

Bu modül, sistemde takip edilen sahaların (Saha ID, İl, İlçe, Mahalle, Koordinat)
kalıcı olarak saklanmasından, güncellenmesinden ve Excel/CSV yüklemelerinden sorumludur.
"""

import os
import io
import re
import pandas as pd

# Sahalar veritabanının (CSV) yolu.
SAHA_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahalar.csv")

# Sistemde tutulacak sabit sütun yapısı
COLUMNS = ["Saha ID", "Saha Adı", "İl", "İlçe", "Mahalle", "Latitude", "Longitude"]


def _clean_text_simple(x: str) -> str:
    """Türkçe karakter ve harf büyüklüğü duyarsız karşılaştırma için yardımcı metin temizleyici."""
    if pd.isna(x) or x is None:
        return ""
    x = str(x).strip().lower()
    replacements = {"ı": "i", "ğ": "g", "ü": "u", "ş": "s", "ö": "o", "ç": "c"}
    for src, tgt in replacements.items():
        x = x.replace(src, tgt)
    return x.replace(" ", "")


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Sütun isimlerini esnek biçimde eşleştirir, SITE_NO ayıklar, eksik sütunları ekler ve temizler."""
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    # 1. KML / Excel formatındaki Açıklama sütunundan SITE_NO çıkar
    if "Açıklama" in df.columns:
        site_ids = df["Açıklama"].astype(str).str.extract(r'SITE_NO=\s*(\d+)')
        if 0 in site_ids.columns and not site_ids[0].isnull().all():
            df["Saha ID"] = site_ids[0]

    rename_map = {}
    for col in df.columns:
        clean_col = _clean_text_simple(col)
        
        # Sütun adı varyasyonlarını eşleştir
        if "saha" in clean_col or clean_col in ["id", "sahaid", "sahano", "kodu", "site_no"]:
            rename_map[col] = "Saha ID"
        elif clean_col in ["placemarkad", "sahaadi", "siteadi", "name"]:
            rename_map[col] = "Saha Adı"
        elif clean_col in ["il", "sehir", "province", "city"]:
            rename_map[col] = "İl"
        elif clean_col in ["ilce", "district", "town"]:
            rename_map[col] = "İlçe"
        elif clean_col in ["mahalle", "mah", "neighborhood", "semt"]:
            rename_map[col] = "Mahalle"
        elif clean_col in ["latitude", "lat", "enlem"]:
            rename_map[col] = "Latitude"
        elif clean_col in ["longitude", "long", "lng", "boylam"]:
            rename_map[col] = "Longitude"

    df = df.rename(columns=rename_map)

    # Saha ID hala atanmadıysa Placemark Adı'nı Saha ID yap
    if "Saha ID" not in df.columns or df["Saha ID"].isnull().all():
        if "Saha Adı" in df.columns:
            df["Saha ID"] = df["Saha Adı"]

    # Eksik sütunları boş olarak ekle
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS].copy()

    # Tüm alanları string'e çevir ve boşlukları temizle
    for col in COLUMNS:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace(["nan", "None", "null", "NaN"], "")

    # Tamamen boş satırları ve Saha ID'si olmayanları filtrele
    df = df[df["Saha ID"] != ""]
    df = df[~df["Saha ID"].str.startswith(";")]

    return df.reset_index(drop=True)


def read_flexible_file(file_or_path) -> pd.DataFrame:
    """
    Excel (.xlsx) ve CSV dosyalarını otomatik algılayıp okuyan esnek fonksiyon.
    """
    try:
        # 1. Dosya yolu string ise
        if isinstance(file_or_path, str):
            if file_or_path.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_or_path, dtype=str)
                return _normalize_df(df)
            else:
                encodings_to_try = ["utf-8-sig", "latin5", "iso-8859-9", "utf-8"]
                for enc in encodings_to_try:
                    try:
                        df = pd.read_csv(file_or_path, dtype=str, encoding=enc, sep=None, engine='python')
                        return _normalize_df(df)
                    except Exception:
                        continue

        # 2. Streamlit UploadedFile nesnesi ise
        else:
            file_name = getattr(file_or_path, "name", "").lower()
            if file_name.endswith(('.xlsx', '.xls')):
                df = pd.read_excel(file_or_path, dtype=str)
                return _normalize_df(df)
            else:
                bytes_data = file_or_path.getvalue()
                encodings_to_try = ["utf-8-sig", "latin5", "iso-8859-9", "utf-8"]
                for enc in encodings_to_try:
                    try:
                        content = bytes_data.decode(enc)
                        sep = ";" if ";" in content.split("\n")[0] else ","
                        df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)
                        return _normalize_df(df)
                    except Exception:
                        continue
    except Exception as e:
        print(f"Okuma hatası: {e}")
        
    return pd.DataFrame(columns=COLUMNS)


def load_sahalar() -> pd.DataFrame:
    """Kalıcı depodan (sahalar.csv) saha verisini yükler."""
    if not os.path.exists(SAHA_CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)
    
    return read_flexible_file(SAHA_CSV_PATH)


def save_sahalar(df: pd.DataFrame) -> None:
    """Verilen DataFrame'i kalıcı olarak sahalar.csv dosyasına yazar."""
    df = _normalize_df(df)
    df = df.drop_duplicates(subset=["Saha ID"], keep="last")
    df.to_csv(SAHA_CSV_PATH, index=False, encoding="utf-8-sig")


def add_or_update_saha(saha_id: str, il: str = "", ilce: str = "", mahalle: str = "", saha_adi: str = "") -> pd.DataFrame:
    """Tekil bir sahayı ekler veya günceller."""
    df = load_sahalar()
    saha_id = str(saha_id).strip()

    if not df.empty and "Saha ID" in df.columns and saha_id in df["Saha ID"].values:
        idx = df.index[df["Saha ID"] == saha_id][0]
        df.loc[idx, ["İl", "İlçe", "Mahalle", "Saha Adı"]] = [il.strip(), ilce.strip(), mahalle.strip(), saha_adi.strip()]
    else:
        new_row = pd.DataFrame([{
            "Saha ID": saha_id, "Saha Adı": saha_adi.strip(), "İl": il.strip(), "İlçe": ilce.strip(), "Mahalle": mahalle.strip(),
            "Latitude": "", "Longitude": ""
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    save_sahalar(df)
    return df


def delete_saha(saha_id: str) -> pd.DataFrame:
    """Saha ID'ye göre kayıt siler."""
    df = load_sahalar()
    if not df.empty and "Saha ID" in df.columns:
        df = df[df["Saha ID"] != str(saha_id).strip()]
        save_sahalar(df)
    return df


def bulk_upload(new_df, mode: str = "append_update") -> pd.DataFrame:
    """Toplu dosya yükleme mantığı."""
    if not isinstance(new_df, pd.DataFrame):
        new_df = read_flexible_file(new_df)
    else:
        new_df = _normalize_df(new_df)

    if mode == "replace":
        final_df = new_df.drop_duplicates(subset=["Saha ID"], keep="last")
    else:  # append_update
        current_df = load_sahalar()
        combined = pd.concat([current_df, new_df], ignore_index=True)
        final_df = combined.drop_duplicates(subset=["Saha ID"], keep="last")

    save_sahalar(final_df)
    return final_df
