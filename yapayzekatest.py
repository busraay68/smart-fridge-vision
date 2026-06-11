import google.generativeai as genai
import PIL.Image
import os

# API Anahtarını buraya yaz
genai.configure(api_key=" ")

# Modeli seç (Flash modeli bu iş için en hızlı ve ücretsizdir)
model = genai.GenerativeModel('gemini-flash-latest')

def nesneleri_algila(resim_yolu):
    # Resmi yükle
    img = PIL.Image.open(resim_yolu)
    
    # Gemini'a komut (prompt) gönderiyoruz
    # Sadece string istediğimiz için cevabı sınırlıyoruz
    prompt = "Bu buzdolabı fotoğrafındaki yiyecek ve içecekleri tespit et. " \
             "Sadece isimlerini aralarında virgül olacak şekilde tek bir satırda yaz. " \
             "Ekstra açıklama yapma."

    response = model.generate_content([prompt, img])
    
    return response.text

# Test edelim
image_path = 'static/uploads/WhatsApp Image 2026-03-29 at 13.56.39.jpeg'
if os.path.exists(image_path):
    sonuc_string = nesneleri_algila(image_path)
    print(f"Buzdolabındakiler: {sonuc_string}")
else:
    print(f"Hata: {image_path} bulunamadı. Lütfen geçerli bir resim yolu girin.")
