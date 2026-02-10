import os
import cloudscraper
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
import datetime
import time
import random

# --- 1. AYARLAR VE GÜVENLİK ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALICI_MAIL = os.environ.get("ALICI_MAIL")

# Gemini Ayarları
if not GEMINI_API_KEY:
    print("UYARI: Gemini API Key bulunamadı.")
else:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')

# --- ÖNEMLİ DEĞİŞİKLİK: Cloudscraper Başlatılıyor ---
# Bu kütüphane Cloudflare korumasını aşmak için tarayıcı taklidi yapar.
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

def get_debe_list():
    """Debe listesini çeker."""
    url = "https://eksisozluk.com/debe"
    try:
        # requests.get yerine scraper.get kullanıyoruz
        response = scraper.get(url)
        
        if response.status_code != 200:
            print(f"Debe listesine erişilemedi. Hata kodu: {response.status_code}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        titles = []
        
        # Debe listesi yapısı
        # Bazen 'topic-list partial', bazen 'topic-list' olabilir
        topic_list = soup.find("ul", class_="topic-list")
        if not topic_list:
            print("Debe listesi HTML içinde bulunamadı. Yapı değişmiş olabilir.")
            return []

        for item in topic_list.find_all("li"):
            a_tag = item.find("a")
            if a_tag:
                link = "https://eksisozluk.com" + a_tag['href']
                # Entry başlığını al (span veya text)
                if a_tag.find("span", class_="caption"):
                    text = a_tag.find("span", class_="caption").get_text(strip=True)
                else:
                    text = a_tag.get_text(strip=True)
                    
                titles.append({"title": text, "link": link})
        
        # İlk 10 başlık
        return titles[:10]
    except Exception as e:
        print(f"Debe çekilirken hata: {e}")
        return []

def get_entry_content(url):
    """Entry içeriğini çeker."""
    try:
        # Ekşi Sözlük bazen linklere parametre eklenmezse farklı davranır
        if "?" not in url:
            url += "?a=search" # Rastgele bir parametre bot algısını kırabilir
            
        response = scraper.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # İçeriği bulmaya çalış
        content_div = soup.find("div", class_="content")
        
        if content_div:
            text = content_div.get_text(separator=" ", strip=True)
            return text
        else:
            # Eğer content yoksa, belki bot korumasına takıldık, log basalım
            print(f"İçerik çekilemedi (HTML Title): {soup.title.string if soup.title else 'Başlık Yok'}")
            return None
    except Exception as e:
        print(f"Entry detay hatası: {e}")
        return None

def summarize_text(text, title):
    """Gemini ile özetler."""
    if not GEMINI_API_KEY:
        return text[:300] + "... (API Key olmadığı için özetlenmedi)"
        
    try:
        prompt = (
            f"Sen benim kişisel asistanım Cemil'sin. Hitabın saygılı ama zeki olsun.\n"
            f"Aşağıdaki Ekşi Sözlük entry'sini ('{title}') Lordum Eren için oku.\n"
            f"Gereksiz detayları at, ana fikri 2 cümleyle özetle.\n"
            f"Entry Metni:\n\n{text}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Özetlenemedi: {e}"

def send_email(report_body):
    """Mail gönderir."""
    if not report_body:
        print("Rapor boş, mail atılmıyor.")
        return

    msg = MIMEMultipart()
    msg['Subject'] = f"Gunluk Eksi Ozeti - {datetime.date.today().strftime('%d.%m.%Y')}"
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL

    full_text = (
        "Günaydın Lordum,\n\n"
        "Bugün güvenlik duvarlarını aşıp içeri sızmayı başardım. "
        "İşte Ekşi Sözlük'te dün en çok konuşulanlar:\n\n"
        f"{report_body}\n\n"
        "Emirlerinize amadeyim,\nCemil"
    )

    msg.attach(MIMEText(full_text, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("Mail başarıyla yollandı.")
    except Exception as e:
        print(f"Mail hatası: {e}")

# --- ANA AKIŞ ---
if __name__ == "__main__":
    print("Görev başladı...")
    debe_items = get_debe_list()
    
    report_content = ""
    basarili_sayisi = 0

    if not debe_items:
        print("Liste boş döndü, operasyon iptal.")
        # Kendine hata maili atabilirsin istersen buraya
    else:
        for index, item in enumerate(debe_items, 1):
            print(f"İşleniyor ({index}/10): {item['title']}")
            
            raw_content = get_entry_content(item['link'])
            
            if raw_content:
                # Çok kısa içerikleri özetleme
                if len(raw_content) > 200:
                    summary = summarize_text(raw_content, item['title'])
                else:
                    summary = f"Kısa Not: {raw_content}"
                
                report_content += f"► {item['title'].upper()}\n"
                report_content += f"{summary}\n"
                report_content += f"Link: {item['link']}\n"
                report_content += "-" * 35 + "\n\n"
                basarili_sayisi += 1
            else:
                report_content += f"► {item['title']} - (Erişim Engeli/Silinmiş)\n\n"

            # Çok hızlı istek atarsak yine banlanırız, biraz bekle
            time.sleep(random.uniform(3, 6))

        if basarili_sayisi > 0:
            send_email(report_content)
        else:
            print("Hiçbir içerik alınamadı, mail atılmadı.")

