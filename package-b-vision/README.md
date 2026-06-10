# 🧊 Smart Fridge Vision Engine (Paket B)

Bu klasör, Akıllı Buzdolabı projesinin **Paket B (Görüntü İşleme)** bileşenini içermektedir. Geliştirilen bu motor, buzdolabına giren ve çıkan ürünleri yapay zeka kullanarak gerçek zamanlı olarak tespit eder ve takip eder.

## 🚀 Projenin Amacı

Bu modül, bir kamera (USB veya IP Kamera) üzerinden aldığı canlı görüntü akışını analiz ederek şu işlemleri gerçekleştirir:
1.  **Nesne Tespiti:** Buzdolabı içindeki ürünleri (süt, meyve, içecek vb.) YOLOv8 modeli ile tanır.
2.  **Nesne Takibi:** Tespit edilen her nesneye bir ID atayarak kareler arasında hareketini takip eder.
3.  **Giriş-Çıkış Analizi:** Belirlenen sanal bir çizgiyi geçen ürünlerin yönüne bakarak `GIRIS` veya `CIKIS` olayları üretir.
4.  **Veri Kaydı:** Tüm olayları Paket C'nin okuyabileceği standart formatlarda (JSON/CSV) kaydeder.

---

## 📂 Klasör Yapısı ve Dosyalar

| Dosya / Klasör | Görevi |
| :--- | :--- |
| `vision_engine.py` | **Ana Motor:** Görüntü işleme, takip ve mantıksal kararların verildiği tek modüllü çekirdek dosya. |
| `models/best.pt` | **Yapay Zeka Modeli:** Eğitilmiş YOLOv8 ağırlık dosyası. Nesnelerin tanınmasını sağlar. |
| `output/` | **Çıktı Klasörü:** Çalışma sonucunda üretilen olay logları (`events.json`) ve özet raporlar (`summary.json`) burada tutulur. |
| `requirements.txt` | **Bağımlılıklar:** Projenin çalışması için gerekli kütüphanelerin (OpenCV, Ultralytics, NumPy) listesi. |
| `README.md` | **Kılavuz:** Proje hakkında genel bilgiler ve kullanım talimatları. |

---

## 🛠️ Kurulum

Öncelikle gerekli kütüphaneleri yükleyin:
```bash
pip install -r requirements.txt
```

---

## ⚡ Hızlı Başlangıç (Adım Adım)

Sistemi en baştan çalıştırmak için şu adımları izleyin:

1.  **Bağımlılıkları Kurun:** `pip install -r requirements.txt`
2.  **Kamerayı Hazırlayın:** USB kameranızı bağlayın veya IP Webcam uygulamasını telefonunuzda başlatın.
3.  **Kaynağı Kontrol Edin:** `vision_engine.py` dosyasının en üstündeki `VIDEO_SOURCE` kısmından doğru kameranın seçili olduğundan emin olun.
4.  **Çalıştırın:** `python3 vision_engine.py --show`

---

## 🎥 Kamera Kaynağını Değiştirme

Kamera seçimini yapmak için `vision_engine.py` dosyasını bir metin düzenleyici ile açın. Dosyanın en üstündeki (yaklaşık 18-25. satırlar arası) şu bölümü bulun:

```python
# SEÇENEK 1: IP Webcam / IP Kamera
VIDEO_SOURCE = "http://192.168.1.50:8080/video"

# SEÇENEK 2: USB Kamera / Harici Donanım Kamerası
# VIDEO_SOURCE = 0
```

- **IP Kamera kullanacaksanız:** Seçenek 1'i aktif bırakın (başında # olmasın), Seçenek 2'nin başına `#` koyun.
- **Normal USB Kamera kullanacaksanız:** Seçenek 1'in başına `#` koyun, Seçenek 2'nin başındaki `#` işaretini kaldırın.

---

## 💻 Çalıştırma Komutları

### 1. Varsayılan Başlatma (IP Webcam)
Kod içindeki `VIDEO_SOURCE` değişkeninde tanımlı olan IP kamerayı kullanarak başlatır:
```bash
python3 vision_engine.py
```

### 2. Canlı İzleme (Debug Modu)
Kameranın ne gördüğünü ve tespitleri ekranda canlı izlemek için `--show` parametresini ekleyin:
```bash
python3 vision_engine.py --show
```

### 3. USB / Harici Kamera Kullanımı
Sisteme bağlı bir USB kamerayı veya CSI kamerayı (0, 1 vb.) kullanmak için:
```bash
python3 vision_engine.py --source 0 --show
```

### 4. Raspberry Pi (2GB RAM) Modu
Raspberry Pi 2GB RAM gibi kısıtlı donanımlarda donma yaşamamak için mutlaka `pi` profilini kullanmalısınız. Bu modda görüntü boyutu düşürülür ve kare atlama yapılarak işlemci yükü dengelenir:
```bash
python3 vision_engine.py --profile pi --show
```

---

## 📸 DJI Action 5 Pro Entegrasyonu

DJI Action 5 Pro kamerasını sisteme iki şekilde bağlayabilirsiniz:

1.  **USB (Webcam Modu):** Kamerayı USB-C ile Pi'ye bağlayın ve kamera menüsünden "Webcam" modunu seçin. Kodda `VIDEO_SOURCE = 0` olarak görünecektir.
2.  **IP Stream (Kablosuz):** Kamera üzerinden canlı yayın (RTMP/RTSP) başlatıp, yayın URL'sini `VIDEO_SOURCE` kısmına yazarak kablosuz olarak kullanabilirsiniz.

> [!IMPORTANT]
> DJI Action 5 Pro 4K çözünürlükte yayın yaptığı için, Pi 2GB üzerinde mutlaka `--profile pi` komutu ile çalıştırılmalıdır. Aksi takdirde sistem RAM yetersizliğinden kapanabilir.

---

## 📊 Çıktılar ve Raporlama

Her çalışma bittiğinde veya nesne geçtiğinde `output/` klasöründe şu veriler oluşur:
- **`events.json` / `events.csv`**: Gerçekleşen her giriş ve çıkış işleminin detaylı kaydı (Zaman, Ürün Adı, Aksiyon, Güven Skoru).
- **`summary.json`**: Oturumun toplam süresi, işlenen kare sayısı ve toplam stok değişim özeti.
- **`annotated.mp4`**: (Eğer `--save-video` aktifse) Üzerinde tespit kutuları olan video kaydı.

---

## ⚠️ Önemli Notlar
- IP Webcam kullanıyorsanız, telefonunuzun ve bilgisayarınızın **aynı Wi-Fi ağına** bağlı olduğundan emin olun.
- Işıklandırma, tespit başarısını doğrudan etkiler; buzdolabı içinin yeterince aydınlık olması önerilir.

