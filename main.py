import gradio as gr
from PIL import Image
import pandas as pd

# --- Dummy veri ---
inventory_df = pd.DataFrame({
    "Ürün": ["Süt", "Puding", "Makarna"],
    "Adet": [10, 5, 2]
})

logs_df = pd.DataFrame({
    "Tarih": ["2026-03-29", "2026-03-28"],
    "Ürün": ["Süt", "Puding"],
    "Önce": [5, 2],
    "Sonra": [10, 5],
    "İşlem": ["Eklendi", "Eklendi"]
})

# --- Fonksiyonlar ---
def get_dashboard_text():
    return f"📊 **Dashboard**\n\nToplam Ürün: {inventory_df['Adet'].sum()}\nStokta Azalanlar: {inventory_df[inventory_df['Adet']<5].shape[0]}"

def get_inventory_df():
    return inventory_df

def get_logs_df():
    return logs_df

def detect_objects(image: Image.Image):
    # placeholder detection
    return image  # sadece resmi geri döndür

# --- Gradio Layout ---
with gr.Blocks() as demo:

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 🧊 Smart Fridge Menüsü")
            menu = gr.Radio(
                choices=["Dashboard", "Envanter", "Tespit", "Loglar"],
                value="Dashboard",
                label="Menü Seç"
            )
        with gr.Column(scale=3):
            content_text = gr.Textbox(label="", interactive=False, visible=True)
            content_df = gr.Dataframe(headers=None, interactive=False, visible=False)
            img_input = gr.Image(type="pil", visible=False)
            img_output = gr.Image(visible=False)

    # --- Menü callback ---
    def update_content(page):
        # Önce tüm widgetları gizle
        content_text.visible = False
        content_df.visible = False
        img_input.visible = False
        img_output.visible = False

        if page == "Dashboard":
            content_text.visible = True
            return get_dashboard_text(), content_df, img_input, img_output
        elif page == "Envanter":
            content_df.visible = True
            return "", get_inventory_df(), img_input, img_output
        elif page == "Loglar":
            content_df.visible = True
            return "", get_logs_df(), img_input, img_output
        elif page == "Tespit":
            img_input.visible = True
            img_output.visible = True
            return "", content_df, img_input, img_output

    menu.change(
        update_content,
        inputs=[menu],
        outputs=[content_text, content_df, img_input, img_output]
    )

    # --- Tespit için callback ---
    img_input.change(detect_objects, inputs=img_input, outputs=img_output)

demo.launch()