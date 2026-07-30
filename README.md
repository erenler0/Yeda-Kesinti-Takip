# YEDAŞ Planlı Kesinti Takip ve Saha Yönetim Uygulaması

## Kurulum

```bash
pip install -r requirements.txt
```

## Çalıştırma

```bash
streamlit run app.py
```

Uygulama tarayıcınızda otomatik olarak açılacaktır (varsayılan: `http://localhost:8501`).

## Dosya Yapısı

| Dosya | Görev |
|---|---|
| `app.py` | Ana Streamlit uygulaması (Dashboard + Veri Yönetimi sayfaları) |
| `data_manager.py` | `sahalar.csv` okuma/yazma, tekil/toplu ekleme-güncelleme mantığı |
| `yedas_scraper.py` | YEDAŞ kesinti verisini çekme + saha eşleştirme + tarih filtreleme |
| `report_generator.py` | PDF ve JPG rapor export fonksiyonları |
| `sahalar.csv` | Kalıcı saha veri tabanı (ilk çalıştırmada otomatik oluşturulur) |
| `ornek_sahalar.csv` | Test için örnek 8 satırlık saha verisi (Veri Yönetimi > Toplu Yükleme sekmesinden yükleyebilirsiniz) |

## Hızlı Test Adımları

1. Uygulamayı başlatın.
2. **Veri Yönetimi > Toplu Yükleme** sekmesinden `ornek_sahalar.csv` dosyasını yükleyip "Yüklemeyi Onayla ve Uygula" butonuna basın.
3. **Dashboard** sayfasına geçin; "Bugün / 3 Günlük / 7 Günlük" filtrelerini deneyin.
4. YEDAŞ'ın canlı sitesine bağlanılamazsa (bu JS-tabanlı bir site olduğu için beklenen bir durumdur), sistem otomatik olarak **DEMO veri** ile çalışır ve bunu ekranda açıkça belirtir.
5. Tablonun altındaki **PDF Olarak İndir** / **JPG Olarak İndir** butonlarını test edin.

## Gerçek YEDAŞ Entegrasyonunu Tamamlamak İçin

`yedas_scraper.py` içindeki `_fetch_live_data()` ve `_parse_html()` fonksiyonları, gerçek sitenin
HTML/JSON yapısına göre güncellenmelidir:

1. Tarayıcıda `https://www.yedas.com/planli-kesinti` sayfasını açın.
2. Geliştirici Araçları (F12) > **Network** sekmesinde sayfa yenilenirken tetiklenen bir
   `XHR`/`Fetch` isteği olup olmadığına bakın (genelde `.../api/...` gibi bir adres olur).
   - Böyle bir JSON API bulunursa, `_fetch_live_data()` içinde `requests.get(YEDAS_URL)` yerine
     doğrudan bu API'ye istek atıp `response.json()` ile veriyi ayrıştırmak en sağlıklı yoldur.
3. JSON API bulunamaz ve veri tamamen JavaScript ile render ediliyorsa, `requests` yerine
   `selenium` veya `playwright` ile tarayıcı otomasyonu gerekir (kod içinde örnek yorum
   satırı olarak bırakılmıştır).
4. Sonuç verisini `KESINTI_COLUMNS` ile aynı sütun isimlerine (`İl`, `İlçe`, `Mahalle`,
   `Kesinti Başlangıç Saati`, `Kesinti Bitiş Saati`, `Açıklama/Nedeni`) eşleyin; tarih formatı
   `%d.%m.%Y %H:%M` (örn. `30.07.2026 09:00`) olmalıdır ki filtreleme fonksiyonu doğru çalışsın.

Bu güncellemeyi yaptıktan sonra uygulamanın geri kalanında (eşleştirme, filtreleme, dashboard,
PDF/JPG export) hiçbir değişiklik yapmanıza gerek yoktur.
