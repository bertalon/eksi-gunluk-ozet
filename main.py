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

def get_debe_list():
    """Debe listesini çeker. Tarama sayısını artırdım (20) ki elenenlerden sonra elde malzeme kalsın."""
    url = "https://eksisozluk.com/debe"
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
        
        return titles[:20] 
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

def analyze_and_summarize(text, title):
    """
    İçeriğin 'değer' seviyesini ölçer.
    """
    if not GEMINI_API_KEY: return "API Key Yok."

    try:
        # --- DENGELİ EDİTÖR PROMPTU ---
        prompt = (
            f"Sen Ekşi Sözlük'ün küratörüsün. Görevin Lordum Eren için içerik seçmek.\n"
            f"Başlık: '{title}'\n"
            f"İçerik: '{text}'\n\n"
            f"KARAR MEKANİZMASI:\n"
            f"Bu içerik şu kategorilerden birine giriyor mu?\n"
            f"1. FAYDALI: İlginç bir bilgi, web sitesi önerisi, hayat dersi, psikolojik tespit.\n"
            f"2. EĞLENCELİ: Komik bir anı, absürt bir olay, güldüren bir tespit.\n"
            f"3. TUHAF: Şaşırtıcı, 'yok artık' dedirten bir detay.\n"
            f"\n"
            f"EĞER CEVABIN EVET İSE:\n"
            f"- İçeriği SEÇ ve 2-3 cümleyle özetle. Özetin tonu zeki ve akıcı olsun.\n"
            f"\n"
            f"EĞER İÇERİK ŞUYSA (VE SADECE ŞUYSA) 'SKIP' YAZ:\n"
            f"- Sadece skor tahmini, fanatik takım kavgası, çok bilindik/sıkıcı günlük siyaset (özelliksiz haber), 'selam', 'bkz' gibi boş içerik.\n"
        )
        
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip()
        
        # Model bazen açıklamalı reddeder, içinde SKIP geçiyorsa ele.
        if "SKIP" in cleaned_response:
            return None
        
        # Bazen model "Bu içerik faydalı..." diye analize başlar, onu temizleyip özeti alalım
        return cleaned_response
            
    except Exception:
        return None

def create_html_email(entries):
    """Modern ve şık bir HTML e-posta tasarımı oluşturur."""
    
    html_content = """
    <html>
    <head>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f6f9fc; margin: 0; padding: 0; }
            .container { max-width: 600px; margin: 20px auto; background: #ffffff; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); overflow: hidden; }
            .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; padding: 25px; text-align: center; }
            .header h1 { margin: 0; font-size: 24px; font-weight: 600; letter-spacing: 1px; }
            .header p { margin: 5px 0 0; opacity: 0.8; font-size: 14px; }
            .content { padding: 20px; }
            .entry-card { background: #fdfdfd; border-left: 4px solid #764ba2; margin-bottom: 20px; padding: 15px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.03); }
            .entry-title { color: #2d3748; font-size: 18px; font-weight: 700; margin-bottom: 8px; text-transform: uppercase; display: block; text-decoration: none; }
            .entry-summary { color: #4a5568; font-size: 15px; line-height: 1.6; margin-bottom: 10px; }
            .read-more { display: inline-block; font-size: 12px; color: #667eea; text-decoration: none; font-weight: 600; }
            .footer { background: #edf2f7; padding: 15px; text-align: center; color: #718096; font-size: 12px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>GÜNLÜK TUHAFLIK RAPORU</h1>
                <p>Üstadım, bugün ağa takılanlar bunlar.</p>
            </div>
            <div class="content">
    """
    
    for entry in entries:
        html_content += f"""
        <div class="entry-card">
            <a href="{entry['link']}" class="entry-title">{entry['title']}</a>
            <div class="entry-summary">{entry['summary']}</div>
            <a href="{entry['link']}" class="read-more">Ekşi'de Oku →</a>
        </div>
        """

    html_content += """
            </div>
            <div class="footer">
                <p>Otomasyon Kahyanız <b>Cemil</b> tarafından sevgiyle derlendi.</p>
                <p>Bu mail GitHub Actions sunucularından ateşlenmiştir.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def send_email(entries):
    """Mail gönderir."""
    if not entries: return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Günlük Tuhaflık Raporu 🧠 - {datetime.date.today().strftime('%d.%m.%Y')}"
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL

    # HTML İçeriği Oluştur
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
    print("Seçici tarama başlıyor...")
    debe_items = get_debe_list()
    
    selected_entries = []

    if debe_items:
        for index, item in enumerate(debe_items, 1):
            print(f"İnceleniyor ({index}): {item['title']}")
            
            raw_content = get_entry_content(item['link'])
            
            if raw_content and len(raw_content) > 100:
                # Yapay Zeka Analizi
                summary = analyze_and_summarize(raw_content, item['title'])
                
                if summary: 
                    print(f"--> SEÇİLDİ: {item['title']}")
                    selected_entries.append({
                        "title": item['title'],
                        "summary": summary,
                        "link": item['link']
                    })
                else:
                    print(f"--> ELENDİ (Sıradan): {item['title']}")
            
            time.sleep(random.uniform(2, 4))

        if selected_entries:
            send_email(selected_entries)
        else:
            print("Bugün 'ilginç' kriterine uyan bir şey çıkmadı.")

