# Smart Fridge OS

Smart Fridge OS, Marmara Üniversitesi Teknoloji Fakültesi Bilgisayar Mühendisliği bölümü kapsamında geliştirilmiş bir bitirme projesidir.

Proje; görüntü işleme, yapay zeka ve web tabanlı envanter yönetimini birleştirerek buzdolabındaki ürünlerin otomatik olarak takip edilmesini, stok hareketlerinin kaydedilmesini, son kullanma tarihi/tazelik durumlarının izlenmesini ve mevcut malzemelere göre yemek tarifi önerileri üretilmesini amaçlar.

## Proje Amacı

Geleneksel manuel buzdolabı takibi yerine, kamera ve yapay zeka destekli bir sistem ile ürün giriş/çıkışlarını otomatik algılamak, gıda israfını azaltmak ve kullanıcıya akıllı mutfak asistanı deneyimi sunmak hedeflenmiştir.

## Temel Özellikler

- IP kamera adresini kaydetme ve kalıcı hafızada tutma
- Canlı kamera yayını izleme
- YOLOv8 ile gerçek zamanlı nesne tespiti
- Ürün giriş/çıkış hareketlerini olay akışında listeleme
- Görüntü alma butonu ile anlık kare yakalayıp Gemini AI ile analiz etme
- YOLO sonuçlarını arka planda Gemini AI ile doğrulama
- YOLO ve Gemini uyuşmazlığında kullanıcı onay popup'ı gösterme
- Envantere tek tıkla ürün ekleme/çıkarma
- Ürünleri adet, son kullanma tarihi ve tazelik oranıyla takip etme
- Yeni ürünlere otomatik SKT ve tazelik değeri atama
- Dinamik istatistik paneli
- Envantere göre yemek tarifi önerileri
- Azalan/tükenen ürünleri alışveriş listesine önerme
- WhatsApp rehberi ve alışveriş listesini WhatsApp Web ile gönderme
- Sistem işlem loglarını görüntüleme
- Raspberry Pi için deploy otomasyon betiği

## Kullanılan Teknolojiler

- Python
- Flask
- SQLite
- OpenCV
- YOLOv8 / Ultralytics
- Gemini AI
- HTML, CSS, JavaScript
- SweetAlert2
- Raspberry Pi uyumlu dağıtım yapısı

## Sistem Mimarisi

Sistem temel olarak dört ana katmandan oluşur:

1. Kamera Katmanı  
   IP kamera veya USB kamera üzerinden canlı görüntü alınır.

2. Vision Engine  
   YOLOv8 modeli ile ürünler tespit edilir, takip edilir ve giriş/çıkış olayları üretilir.

3. AI Doğrulama Katmanı  
   Gemini AI ile YOLO tespitleri doğrulanır. Uyuşmazlık durumunda kullanıcıdan onay alınır.

4. Web Uygulama Katmanı  
   Envanter, tarif önerileri, alışveriş listesi, WhatsApp gönderimi ve log ekranları kullanıcıya sunulur.

## Bitirme Projesi Bilgisi

Bu proje, Marmara Üniversitesi Teknoloji Fakültesi Bilgisayar Mühendisliği Bölümü bitirme projesi kapsamında geliştirilmiştir.

Proje konusu:

**Görüntü İşleme Tabanlı Akıllı Buzdolabı İçerik Takibi ve Tarif Öneri Sistemi**
