"""
data_manager.py
----------------
YEDAŞ Planlı Kesinti Takip Uygulaması - Veri Yönetimi Modülü

Bu modül, sistemde takip edilen sahaların (Saha ID, İl, İlçe, Mahalle) kalıcı
olarak saklanmasından ve güncellenmesinden sorumludur. Veri kaynağı olarak
basit bir CSV dosyası (sahalar.csv) kullanılır. Küçük/orta ölçekli veri
setleri için CSV yeterlidir; veri hacmi çok büyürse (>100binlerce satır)
SQLite'a geçiş için `load_sahalar`/`save_sahalar` fonksiyonlarının
imzalarını değiştirmeden içini SQLite ile değiştirmek yeterlidir.
"""

import os
import pandas as pd

# Sahalar veritabanının (CSV) yolu. Uygulama ile aynı dizinde tutulur.
SAHA_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sahalar.csv")

# Sistemde tutulacak sabit sütun yapısı
COLUMNS = ["Saha ID", "İl", "İlçe", "Mahalle"]


def _normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    """Sütun isimlerini standardize eder, eksik sütunları ekler, tipleri düzeltir."""
    # Olası sütun adı varyasyonlarını (boşluk, büyük/küçük harf) tolere et
    rename_map = {}
    for col in df.columns:
        col_clean = col.strip()
        for target in COLUMNS:
            if col_clean.lower().replace(" ", "") == target.lower().replace(" ", ""):
                rename_map[col] = target
                break
    df = df.rename(columns=rename_map)

    # Eksik sütunları boş olarak ekle
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = ""

    df = df[COLUMNS].copy()

    # Tüm alanları string'e çevir, baştaki/sondaki boşlukları temizle
    for col in COLUMNS:
        df[col] = df[col].astype(str).str.strip()

    # Tamamen boş (Saha ID'siz) satırları at
    df = df[df["Saha ID"] != ""]
    df = df[df["Saha ID"] != "nan"]

    return df.reset_index(drop=True)


def load_sahalar() -> pd.DataFrame:
    """Kalıcı depodan (sahalar.csv) saha verisini yükler. Dosya yoksa boş DataFrame döner."""
    if not os.path.exists(SAHA_CSV_PATH):
        return pd.DataFrame(columns=COLUMNS)
    try:
        df = pd.read_csv(SAHA_CSV_PATH, dtype=str, encoding="utf-8-sig")
    except Exception:
        # Bazı CSV'ler farklı encoding ile gelebilir (ör. Türkçe karakterli Excel exportları)
        df = pd.read_csv(SAHA_CSV_PATH, dtype=str, encoding="latin5")
    return _normalize_df(df)


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
    new_df = _normalize_df(new_df)

    if mode == "replace":
        final_df = new_df.drop_duplicates(subset=["Saha ID"], keep="last")
    else:  # append_update
        current_df = load_sahalar()
        # Yeni veriyi mevcut verinin altına ekle; aynı Saha ID'de son (yeni) kayıt esas alınır
        combined = pd.concat([current_df, new_df], ignore_index=True)
        final_df = combined.drop_duplicates(subset=["Saha ID"], keep="last")

    save_sahalar(final_df)
    return final_df
