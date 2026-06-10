import google.generativeai as genai
import PIL.Image
import os

# API Anahtarı Yapılandırması
API_KEY = " "

genai.configure(api_key=API_KEY)

def gemini_ile_tespit_et(image_path):
    """
    Verilen resim yolundaki nesneleri Gemini 2.0 Flash kullanarak tespit eder.
    """
    if not os.path.exists(image_path):
        return "Hata: Resim dosyası bulunamadı."

    try:
        # Modeli listenizdeki en kararlı isim olan 'gemini-flash-latest' ile güncelliyoruz
        model = genai.GenerativeModel('gemini-flash-latest')


        
        # Resmi yükle
        img = PIL.Image.open(image_path)
        
        # Prompt hazırlığı: Adetli ve yapılandırılmış veri formatı
        prompt = (
            "Sen gelişmiş bir akıllı buzdolabı asistanısın. Resmi dikkatlice incele: "
            "1. Eğer resimde bir el bir nesne tutuyorsa, SADECE o nesneyi ve adedini tespit et. "
            "2. Eğer el yoksa, resimdeki tüm yiyecek/içecekleri ve adetlerini tespit et. "
            "Cevabı SADECE şu formatta döndür (ekstra kelime veya cümle kurma): "
            "Ürün Adı: Adet, Ürün Adı: Adet"
            "Örnek Görünüm: Süt: 1, Yumurta: 12, Elma: 5"
        )



        # Gemini'dan yanıt al
        response = model.generate_content([prompt, img])
        
        return response.text.strip()
    except Exception as e:
        return f"Yapay zeka tespiti sırasında hata oluştu: {str(e)}"
