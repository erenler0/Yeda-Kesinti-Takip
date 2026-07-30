"""
data_manager.py
----------------
YEDAŞ Planlı Kesinti Takip Uygulaması - Esnek Veri Yönetimi Modülü

Bu modül, sistemde takip edilen sahaların (Saha ID, İl, İlçe, Mahalle) kalıcı
olarak saklanmasından, güncellenmesinden ve esnek CSV yüklemelerinden sorumludur.
"""

import os
import io
import pandas as pd

# Sahalar veritabanının (CSV) yolu.
SAHA_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahalar.csv")

# Sistemde tutulacak sabit sütun yapısı
COLUMNS = ["Saha ID", "İl", "İlçe", "Mahalle"]


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
    """Sütun isimlerini esnek biçimde eşleştirir, eksik sütunları ekler ve temizler."""
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)

    rename_map = {}
    for col in df.columns:
        clean_col = _clean_text_simple(col)
        
        # Sütun adı varyasyonlarını akıllıca eşleştir
        if "saha" in clean_col or clean_col in ["id", "sahaid", "sahano", "kodu"]:
            rename_map[col] = "Saha ID"
        elif clean_col in ["il", "sehir", "province", "city"]:
            rename_map[col] = "İl"
        elif clean_col in ["ilce", "district", "town"]:
            rename_map[col] = "İlçe"
        elif clean_col in ["mahalle", "mah", "neighborhood", "semt"]:
            rename_map[col] = "Mahalle"

    df = df.rename(columns=rename_map)

    # Eksik sütunları boş olarak ekle
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS].copy()

    # Tüm alanları string'e çevir ve boşlukları temizle
    for col in COLUMNS:
        df[col] = df[col].astype(str).str.strip()
        # "nan", "None", "null" gibi stringleşmiş ifadeleri temizle
        df[col] = df[col].replace(["nan", "None", "null", "NaN"], "")

    # Tamamen boş satırları ve Saha ID'si olmayanları filtrele
    df = df[df["Saha ID"] != ""]
    # Boş kalan ayraçlı satırları (örn: ;;; veya ,,) engelle
    df = df[~df["Saha ID"].str.startswith(";")]

    return df.reset_index(drop=True)


def read_flexible_csv(file_or_path) -> pd.DataFrame:
    """
    Şirketten gelebilecek her türlü CSV'yi (noktalı virgül, virgül, latin5, utf-8)
    otomatik algılayıp hatasız okuyan yardımcı fonksiyon.
    """
    content = ""
    # 1. İçeriği Metin Olarak Oku (Encoding Uyumluluğu)
    encodings_to_try = ["utf-8-sig", "latin5", "iso-8859-9", "cp1255", "utf-8"]
    
    if isinstance(file_or_path, str):
        for enc in encodings_to_try:
            try:
                with open(file_or_path, "r", encoding=enc) as f:
                    content = f.read()
                break
            except Exception:
                continue
    else:
        # Streamlit FileUploader nesnesi gelirse
        bytes_data = file_or_path.getvalue()
        for enc in encodings_to_try:
            try:
                content = bytes_data.decode(enc)
                break
            except Exception:
                continue

    if not content.strip():
        return pd.DataFrame(columns=COLUMNS)

    # 2. Ayracı Otomatik Tespit Et (Virgül mü Noktalı Virgül mü?)
    first_line = content.strip().split("\n")[0]
    sep = ";" if ";" in first_line else ","

    # 3. Pandas ile Oku
    try:
        df = pd.read_csv(io.StringIO(content), sep=sep, dtype=str)
    except Exception:
        df = pd.read_csv(io.StringIO(content), dtype=str)

    return _normalize_df(df)


def load_sahalar() -> pd.DataFrame:
    """Kalıcı depodan (sahalar.csv) saha verisini yükler. Dosya yoksa boş DataFrame döner."""
    if not os.path.exists(SAHA_CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)
    
    return read_flexible_csv(SAHA_CSV_PATH)


def save_sahalar(df: pd.DataFrame) -> None:
    """Verilen DataFrame'i kalıcı olarak sahalar.csv dosyasına yazar (üzerine yazar)."""
    df = _normalize_df(df)
    # Aynı Saha ID tekrar etmesin diye son kaydı esas al
    df = df.drop_duplicates(subset=["Saha ID"], keep="last")
    df.to_csv(SAHA_CSV_PATH, index=False, encoding="utf-8-sig")


def add_or_update_saha(saha_id: str, il: str, ilce: str, mahalle: str) -> pd.DataFrame:
    """Tekil bir sahayı ekler; Saha ID zaten varsa bilgilerini günceller."""
    df = load_sahalar()
    saha_id = str(saha_id).strip()

    if saha_id in df["Saha ID"].values:
        # Var olan kaydı güncelle
        idx = df.index[df["Saha ID"] == saha_id][0]
        df.loc[idx, ["İl", "İlçe", "Mahalle"]] = [il.strip(), ilce.strip(), mahalle.strip()]
    else:
        # Yeni kayıt ekle
        new_row = pd.DataFrame([{
            "Saha ID": saha_id, "İl": il.strip(), "İlçe": ilce.strip(), "Mahalle": mahalle.strip()
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    save_sahalar(df)
    return df


def delete_saha(saha_id: str) -> pd.DataFrame:
    """Verilen Saha ID'ye sahip kaydı siler."""
    df = load_sahalar()
    df = df[df["Saha ID"] != str(saha_id).strip()]
    save_sahalar(df)
    return df


def bulk_upload(new_df: pd.DataFrame, mode: str = "append_update") -> pd.DataFrame:
    """
    Toplu CSV yükleme mantığını uygular.

    mode="replace"        -> Mevcut tüm veri tabanını SIFIRLAR, yalnızca yeni dosyadaki veriyi tutar.
    mode="append_update"  -> Mevcut veriye EKLER; Saha ID çakışırsa yeni gelen veri ile GÜNCELLER.
    """
    # Eğer yüklenen nesne ham dosya ise önce akıllı oku
    if not isinstance(new_df, pd.DataFrame):
        new_df = read_flexible_csv(new_df)
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
