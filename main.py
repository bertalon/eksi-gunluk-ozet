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

# --- AYARLAR ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALICI_MAIL = os.environ.get("ALICI_MAIL")

# Gemini Ayarları
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Cloudscraper (Bot Koruması)
scraper = cloudscraper.create_scraper(
    browser={'browser': 'chrome', 'platform': 'windows', 'desktop': True}
)

def get_hebe_list():
    """HEBE (Haftanın En Beğenilenleri) listesini çeker."""
    # DEĞİŞİKLİK: Debe yerine Hebe
    url = "https://eksisozluk.com/hebe"
    try:
        response = scraper.get(url)
        if response.status_code != 200: return []
        
        soup = BeautifulSoup(response.content, 'html.parser')
        titles = []
        topic_list = soup.find("ul", class_="topic-list") or soup.find("ul", class_="topic-list partial")
        
        if not topic_list: return []

        for item in topic_list.find_all("li"):
            a_tag = item.find("a")
            if a_tag:
                link = "https://eksisozluk.com" + a_tag['href']
                caption = a_tag.find("span", class_="caption")
                text = caption.get_text(strip=True) if caption else a_tag.get_text(strip=True)
                titles.append({"title": text, "link": link})
        
        # Haftanın en iyi 10 başlığı yeterli ve temiz olur
        return titles[:10] 
    except Exception:
        return []

def get_entry_content(url):
    try:
        if "?" not in url: url += "?a=search"
        response = scraper.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')
        content_div = soup.find("div", class_="content")
        return content_div.get_text(separator=" ", strip=True) if content_div else None
    except Exception:
        return None

def summarize_content(text, title):
    """
    Filtreleme YAPMAZ. Sadece verilen içeriği Cemil dilinde özetler.
    """
    if not GEMINI_API_KEY: return "API Key Yok."

    try:
        # --- ÖZETLEYİCİ PROMPT ---
        prompt = (
            f"Sen kişisel asistan Cemil'sin. Bu metin Ekşi Sözlük'te haftanın en beğenilenlerinden biri.\n"
            f"Başlık: '{title}'\n"
            f"İçerik: '{text}'\n\n"
            f"GÖREVİN:\n"
            f"Bu içeriği Üstadım Eren için 2-3 cümleyle, akıcı ve hafif esprili/zeki bir dille özetle.\n"
            f"Eğer içerik çok kısaysa veya sadece bir linkse 'İçerik yetersiz' yazma, linkin ne hakkında olduğunu tahmin etmeye çalış veya esprili bir yorum yap.\n"
            f"Asla 'Selam', 'Merhaba' deme, direkt konuya gir."
        )
        
        response = model.generate_content(prompt)
        return response.text.strip()
            
    except Exception:
        return "Yapay zeka bu içeriği yorumlarken takıldı."

def create_html_email(entries):
    """Şık HTML Tasarım."""
    
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 30px auto; background: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 10px rgba(0,0,0,0.1); }
            .header { background: #2c3e50; color: #ffffff; padding: 20px; text-align: center; }
            .header h1 { margin: 0; font-size: 22px; letter-spacing: 1px; }
            .content { padding: 20px; }
            .card { border-bottom: 1px solid #eee; padding: 15px 0; }
            .card:last-child { border-bottom: none; }
            .title { color: #d35400; font-size: 18px; font-weight: bold; text-decoration: none; display: block; margin-bottom: 5px; }
            .summary { color: #555; font-size: 14px; line-height: 1.5; }
            .footer { background: #ecf0f1; padding: 10px; text-align: center; color: #7f8c8d; font-size: 11px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>HAFTALIK ÖZET (HEBE)</h1>
                <p>Geçen hafta Ekşi'de kaçırdığın en sağlam olaylar.</p>
            </div>
            <div class="content">
    """
    
    for entry in entries:
        html_content += f"""
        <div class="card">
            <a href="{entry['link']}" class="title">★ {entry['title']}</a>
            <div class="summary">{entry['summary']}</div>
        </div>
        """

    html_content += """
            </div>
            <div class="footer">
                <p>Cemil - Dijital Kahyanız</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_email(entries):
    if not entries: return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Haftanın En İyileri 🏆 - {datetime.date.today().strftime('%d.%m.%Y')}"
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL

    html_body = create_html_email(entries)
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("Mail başarıyla yollandı.")
    except Exception as e:
        print(f"Mail hatası: {e}")

# --- ANA AKIŞ ---
if __name__ == "__main__":
    print("Haftalık tarama (HEBE) başlıyor...")
    hebe_items = get_hebe_list()
    
    final_entries = []

    if hebe_items:
        for index, item in enumerate(hebe_items, 1):
            print(f"[{index}] Çekiliyor: {item['title']}")
            
            raw_content = get_entry_content(item['link'])
            
            if raw_content:
                # SKIP mekanizması yok, direkt özetletiyoruz
                summary = summarize_content(raw_content, item['title'])
                final_entries.append({
                    "title": item['title'],
                    "summary": summary,
                    "link": item['link']
                })
            else:
                print("   -> İçerik boş geldi.")
            
            time.sleep(random.uniform(2, 4))

        if final_entries:
            send_email(final_entries)
        else:
            print("Liste oluşturulamadı.")
