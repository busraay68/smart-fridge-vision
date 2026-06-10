# seed_db.py
import db

def seed():
    # Önce tabloların varlığından emin olalım
    db.create_tables()
    
    # 10 farklı envanter elemanı ekleyelim veya güncelleyelim.
    # update_inventory fonksiyonu change_amount alır. Eğer envanterde önceden veri varsa üzerine ekler.
    # Bu yüzden önce envanteri sıfırlayıp temiz bir seed yapalım ya da direkt değerleri set edelim.
    # db.clear_all_data() diyebiliriz veya doğrudan SQL ile insert/update yapabiliriz.
    
    # Doğrudan temizlemek için clear_all_data() çağıralım:
    print("Mevcut veriler temizleniyor...")
    db.clear_all_data()
    
    items = [
        {"name": "Süt", "qty": 5, "expiry": "2026-06-15", "img": "items_photos/milk.jpg"},
        {"name": "Domates", "qty": 1, "expiry": "2026-06-05", "img": "items_photos/tomato.jpg"},
        {"name": "Yumurta", "qty": 2, "expiry": "2026-06-10", "img": "items_photos/eggs.jpg"},
        {"name": "Ekmek", "qty": 0, "expiry": "2026-06-02", "img": "items_photos/bread.jpg"},
        {"name": "Peynir", "qty": 1, "expiry": "2026-06-20", "img": "items_photos/cheese.jpg"},
        {"name": "Salatalık", "qty": 8, "expiry": "2026-06-07", "img": "items_photos/cucumber.jpg"},
        {"name": "Muz", "qty": 10, "expiry": "2026-06-06", "img": "items_photos/banana.jpg"},
        {"name": "Elma", "qty": 0, "expiry": "2026-06-12", "img": "items_photos/apple.jpg"},
        {"name": "Yoğurt", "qty": 1, "expiry": "2026-06-18", "img": "items_photos/natural_yoghurt.jpg"},
        {"name": "Tereyağı", "qty": 4, "expiry": "2026-06-25", "img": "items_photos/butter.jpg"}
    ]
    
    print("Yeni veriler envantere ekleniyor...")
    for item in items:
        # update_inventory'yi doğrudan change_amount = qty olarak çağırıyoruz çünkü veritabanını sıfırladık.
        db.update_inventory(
            class_name=item["name"],
            change_amount=item["qty"],
            expiry_date=item["expiry"],
            image_path=item["img"],
            source="Seed Script"
        )
        print(f"Eklendi: {item['name']} (Miktar: {item['qty']})")
        
    print("Seed işlemi tamamlandı!")

if __name__ == "__main__":
    seed()
