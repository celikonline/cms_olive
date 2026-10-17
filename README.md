# Hasret Zeytincilik — React + Python

[altingida45.com](https://altingida45.com/) referans alınarak hazırlanmış, yerelde çalışan mağaza ve yönetim paneli. React 19 + Vite, Python Flask + Waitress, SQLite. Logo ve görseller yerel `public/assets` klasöründedir; harici siteye bağımlı çalışmaz. Yazı tipi bağlantısı için çevrimiçi Google Fonts kullanılır; bağlantı yoksa sistem yazı tipi devreye girer.

## Çalıştırma (Windows)

Node.js 20.19+ veya 22.12+, Python 3.11+ gerektirir. Proje klasöründe:

```powershell
.\start.ps1
```

- Mağaza: http://127.0.0.1:8000
- Yönetim: http://127.0.0.1:8000/admin
- Kullanıcı: `admin`. İlk kurulumda rastgele oluşturulan şifre `.local/admin.txt` dosyasındadır. Bu dosya Git'e dahil edilmez. Alternatif olarak ilk başlatmadan önce `ADMIN_PASSWORD` ortam değişkeni belirlenebilir; bu durumda şifre dosyası oluşturulmaz.

Script React'i derler ve Python sunucusunu ön planda çalıştırır. Durdurmak için Ctrl+C. Aynı portta mevcut sunucu varsa önce onu durdurun. Veritabanı sonraki çalıştırmalarda korunur; başlangıç verileri yalnızca boş veritabanına aktarılır.

## Docker ile çalıştırma

Docker Desktop kuruluysa proje tek komutla derlenip **7030** portunda yayınlanır:

```powershell
docker compose up -d --build
```

- Mağaza: http://127.0.0.1:7030 — Panel: http://127.0.0.1:7030/admin
- Durdurma: `docker compose down` (veriler silinmez). Günlükler: `docker compose logs -f`. Durum ve sağlık: `docker compose ps`.
- İmaj çok aşamalıdır: React derlemesi Node aşamasında yapılır; çalışma imajı yalnızca Flask + Waitress, `backend/` ve `dist/` içeriğini taşır ve kök olmayan `app` kullanıcısıyla çalışır.
- `backend/instance` klasörü konteynerde `/data` dizinine bağlanır; mevcut SQLite veritabanı, görseller ve sesli notlar korunur. Klasör boşsa başlangıç verileri yüklenir ve yönetici şifresi `backend/instance/admin.txt` dosyasına yazılır (mevcut kurulumda şifre `.local/admin.txt` içindedir).
- İsimli birim (named volume) tercih ederseniz `docker-compose.yml` içindeki yorum satırlarını açın; veriler Docker biriminde tutulur ve Linux'ta izin sorunları yaşanmaz.
- Ortam değişkenleri: `PORT` (varsayılan 7030), `HOST` (imajda `0.0.0.0`), `DATA_DIR`, `ADMIN_FILE`, `ADMIN_PASSWORD`, `SECRET_KEY`, `COOKIE_SECURE`.
- HTTPS arkasında yayınlıyorsanız `docker-compose.yml` içinde `COOKIE_SECURE: "1"` yapın; düz HTTP'de `0` kalmalıdır, aksi hâlde tarayıcı oturum çerezini göndermez.
- PWA kurulumu, konum ve mikrofon güvenli bağlam gerektirir: `http://127.0.0.1:7030` ve HTTPS çalışır, `http://<yerel-ip>:7030` çalışmaz.
- Arayüzde değişiklik yaptıktan sonra aynı komutu tekrar çalıştırın; imaj yeniden derlenir.

## Özellikler

- Referans siteden aktarılan 107 ürün, 12 kategori, 20 blog yazısı ve 5 bilgi sayfası.
- Mobil uyumlu ana sayfa, slaytlar, kategori sayfaları, arama, fiyat sıralaması ve stok filtresi.
- Varyant seçimi, kalıcı sepet, teslimat formu ve sipariş talebi kaydı.
- Sipariş formunda kullanıcı isteği ve tarayıcı izniyle konumdan il/ilçe/mahalle doldurma. Koordinatlar ve IP adresi BigDataCloud'a gönderilir; sokak ve bina numarası kullanıcı tarafından tamamlanır.
- Yönetici oturumu; ürün, varyant, fiyat, stok, kategori, blog, sayfa, logo, duyuru ve ana sayfa slaytları düzenleme.
- PNG/JPG/WebP görsel (5 MB) ve sesli not kaydı yükleme, sipariş durumları, iletişim mesajları ve e-posta aboneleri.
- Silme yerine arşivleme: “Pasifleri göster” üzerinden düzenleyip yeniden yayınlayabilirsiniz.
- Sipariş sırasında sunucuda fiyat ve stok doğrulaması; atomik stok düşümü. İptalde stok bir kez geri eklenir.
- Şifre özeti, HttpOnly/SameSite oturum çerezi, CSRF denetimi ve giriş denemesi sınırlaması.
- Saha müşteri kaydı: ad, telefon, adres, yakınlık/hatırlatma notu, GPS teslim konumu ve sipariş geçmişi. Kapıda satışta “Sipariş verildi” işaretlenir; bir sonraki yılın hatırlatması otomatik kurulur.
- Yenileme hatırlatma takvimi: aylık takvim, yaklaşan ve geciken müşteri listeleri, seçilen günün müşterileri.
- Sesli hatırlatma notu: mikrofondan konuşulan Türkçe metin yazıya çevrilir, istenirse ses kaydı da notla birlikte saklanır ve sonradan dinlenebilir.
- PWA: `manifest.webmanifest` ve servis çalışanı ile telefona kurulabilir; uygulama kabuğu önbelleğe alınır, `/api` istekleri her zaman ağdan gider.

## Saha satışı ve yenileme hatırlatmaları

Müşteriler yönetim panelindeki **Müşteriler** bölümünden yönetilir (`/admin/customers`). Kapı kapı satışta her müşteri için ad, telefon, adres, yakınlık notu (“Özgür’ün arkadaşı, her yıl 5 litrelik alır”) ve isteğe bağlı GPS teslim konumu kaydedilir.

- **Hatırlatma kuralı:** son sipariş tarihine yenileme periyodu (varsayılan 12 ay) eklenir. Müşteri, hatırlatma tarihine varsayılan 30 gün kalınca “Yaklaşıyor”, tarih geçtiğinde “Gecikti” olarak listelenir.
- **Sipariş verildi:** kapıda satış tamamlandığında tarih, tutar ve alınan ürünler girilir; sipariş geçmişine eklenir ve sonraki hatırlatma bir sonraki yıla kurulur.
- **Notlar:** her not kaynağıyla (sesli veya elle) saklanır. Sesli notlarda konuşma tarayıcıda yazıya çevrilir, kayıt `backend/instance/voice/` klasörüne yazılır ve yalnızca yönetici oturumu olan istemciye (`/api/admin/voice/...`) sunulur.
- **Web siparişleri:** mağazadan gelen sipariş talebi, telefon numarası eşleşiyorsa mevcut saha müşterisinin geçmişine eklenir; eşleşme yoksa yeni kayıt açılır. İlk kayıtta hatırlatma tarihi kurulur, mevcut hatırlatma korunur.
- **Ayarlar:** `Site Ayarları` sayfasındaki “Saha ve hatırlatma ayarları” bölümünden saha satış temsilcileri, varsayılan periyot ve hatırlatma aralığı düzenlenir.

## PWA ve telefon kullanımı

- `public/manifest.webmanifest` uygulama adını, ikonları, tema rengini ve kısayolları (Müşteriler, Hatırlatma takvimi, Panel) tanımlar; `public/sw.js` uygulama kabuğunu ve görselleri önbelleğe alır. Önbelleği yenilemek için `sw.js` içindeki `CACHE` adını değiştirin.
- Kurulum (ana ekrana ekleme), konum ve mikrofon **güvenli bağlam** gerektirir. `http://127.0.0.1:8000` güvenli sayılır; telefondan yerel ağ IP'si ile `http://` üzerinden açıldığında bu özellikler çalışmaz. Telefonda kullanmak için HTTPS'e (ters vekil veya tünel) geçin.
- Sesi yazıya çevirme tarayıcı desteğine bağlıdır (Chrome/Android’de çevrimiçi çalışır). Desteklenmeyen tarayıcıda ses kaydı saklanır, not elle yazılabilir.

## Ödeme ve kapsam

Siparişler **ödeme alınmadan sipariş talebi** olarak kaydedilir. Kart, banka, kargo, SMS, e-posta gönderimi ve pazaryeri entegrasyonu bulunmaz. Abonelik ve iletişim formları kayıtları yönetim paneline iletir; dışarıya mesaj göndermez. Kaynak sitenin kampanya motoru, müşteri hesabı sistemi ve ikas hizmetleri taşınmamıştır. Ürün açıklamaları detay sayfalarından, blog görselleri kaynak anasayfadan aktarılmıştır. Fiyatlar ve stoklar 17 Ekim 2026 tarihli referans aktarımıdır; kendiliğinden eşitlenmez. Yayına geçmeden önce mağaza içerikleri, fiyatlar ve işletmeye özel sözleşmeler panelden düzenlenmelidir.

## Geliştirme

İki terminalde:

```powershell
.\.venv\Scripts\python.exe backend/app.py
```

```powershell
npm.cmd run dev
```

Vite adresi http://127.0.0.1:5173; `/api` ve `/media` istekleri Python'a yönlendirilir. Normal kullanımda tek Python sunucusu derlenmiş React dosyalarını sunar.

## Doğrulama

```powershell
npm.cmd run build
.\.venv\Scripts\python.exe scripts/test_backend.py
```

Testler geçici bir veritabanı kullanır. Yönetici erişimi, CSRF, içerik yönetimi, arşivden geri alma, fiyat manipülasyonu, stok yetersizliği, sipariş iptali, görsel doğrulaması, saha müşterisi kaydı, yenileme hatırlatmasının hesaplanması, sesli/görsel not doğrulaması ve ses kaydı yüklemesi kontrol edilir.

## Veri ve yedekleme

- `backend/seed.json`: başlangıç içerikleri.
- `backend/instance/store.sqlite3`: gerçek mağaza verileri.
- `backend/instance/uploads/`: panelden yüklenen görseller.
- `backend/instance/voice/`: sesli hatırlatma notlarının kayıtları (yalnızca yönetici erişir).
- `backend/instance/session-secret`: oturum imzalama anahtarı.
- `.local/admin.txt`: ilk kurulum giriş bilgileri.

Yedek alırken sunucuyu durdurup `backend/instance` klasörünün tamamını kopyalayın. Veritabanını silmek içerik ve siparişleri kaybettirir. `DATA_DIR` ile veri klasörü, `PORT` ile port, `HOST` ile dinlenen adres (varsayılan `127.0.0.1`), `ADMIN_FILE` ile yönetici şifre dosyasının yolu belirlenebilir. İnternette yayın için HTTPS, kalıcı veri diski, güvenilir ters vekil ve `COOKIE_SECURE=1` yapılandırılmalıdır. Uygulama yerelde varsayılan olarak yalnızca `127.0.0.1` üzerinde dinler; Docker imajı `HOST=0.0.0.0` ile başlar.

## Referans aktarımı

`scripts/import_reference.py`, kamuya açık referans sayfalarını okuyarak **yalnızca başlangıç verilerini** ve görsel dosyalarını oluşturur; canlı veritabanını değiştirmez. Kaynak anasayfanın `__NEXT_DATA__` verisi `reference-data.json`, HTML görsel/link özeti `reference-summary.json` olarak hazır bulunmalıdır. Bunlar teslim edilen uygulamanın çalışması için gerekli değildir. `inspect_reference.py` bir HTML kopyasından bu dosyaları üretir. Başlangıç verilerini yeniledikten sonra sırayla `scripts/refine_descriptions.py` ve `scripts/refine_blog_images.py` çalıştırılarak uzun açıklamalar ve blog görselleri tamamlanabilir. Bu iki komut da canlı veritabanını değiştirmez.
