# theme.py
class Theme:
    def __init__(self, primary, accent, background, text, card_bg):
        self.primary = primary
        self.accent = accent
        self.background = background
        self.text = text
        self.card_bg = card_bg

# örnek temalar

tema_light = {
    "background": "#f4f6f8",  # Açık gri, göz yormaz
    "text": "#1f2937",        # Koyu gri
    "primary": "#293b6d",     # Modern mavi
    "accent": "#9ab4eb",      # Turuncu vurgu
    "card_bg": "#ffffff"       # Saf beyaz kart
}

tema_dark = {
    "background": "#0f172a",  # Koyu gece mavisi
    "text": "#f1f5f9",        # Açık gri
    "primary": "#3b82f6",     # Mavi vurgu
    "accent": "#facc15",      # Altın sarısı vurgu
    "card_bg": "#1e293b"       # Koyu kart arka plan
}

tema_cool = {
    "background": "#e0f2fe",  # Buz mavisi
    "text": "#0c4a6e",        # Koyu mavi
    "primary": "#0284c7",     # Canlı mavi
    "accent": "#7dd3fc",      # Açık mavi vurgu
    "card_bg": "#ffffff"       # Kartlar beyaz
}

DEFAULT_TEMA = "light"

def get_theme(name=None):
    global DEFAULT_TEMA
    if name is None:
        name = DEFAULT_TEMA
    if name == "light":
        return tema_light
    elif name == "dark":
        return tema_dark
    elif name == "cool":
        return tema_cool
    else:
        return tema_light