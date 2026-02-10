import os
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
import datetime
import time

# --- 1. AYARLAR VE GÜVENLİK (GitHub Secrets'tan Okuma) ---
# Bu değişkenleri GitHub'da 'Settings -> Secrets and variables -> Actions' kısmına eklemiş olmalısın.
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALICI_MAIL = os.environ.get("ALICI_MAIL")

# Eğer anahtar yoksa hata verip durdur (Hata ayıklamak için)
if not GEMINI_API_KEY:
    raise ValueError("Gemini API Key bulunamadı! GitHub Secrets ayarlarını kontrol et.")

# Gemini Ayarları
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Ekşi Sözlük Bot Korumasını Aşmak İçin
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_debe_list():
    """Debe (Dünün En Beğenilen Entry'leri) listesini çeker."""
    url = "https://eksisozluk.com/debe"
    response = requests.get(url, headers=HEADERS)
    
    if response.status_code != 200:
        print(f"Siteye erişilemedi. Hata kodu: {response.status_code}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    titles = []
    
    # Debe listesini bul
    topic_list = soup.find("ul", class_="topic-list")
    if not topic_list:
        return []

    for item in topic_list.find_all("li"):
        a_tag = item.find("a")
        if a_tag:
            link = "https://eksisozluk.com" + a_tag['href']
            # Entry başlığını al
            text = a_tag.contents[0].strip() if a_tag.contents else "Başlık Yok"
            titles.append({"title": text, "link": link})
    
    # Lordum, çok uzun sürmesin diye ilk 10 başlığı alalım
    return titles[:10]

def get_entry_content(url):
    """Verilen linkteki ilk entry'nin içeriğini çeker."""
    try:
        response = requests.get(url, headers=HEADERS)
        soup = BeautifulSoup(response.content, 'html.parser')
        content_div = soup.find("div", class_="content")
        
        if content_div:
            return content_div.get_text(strip=True)
        return "İçerik bulunamadı."
    except Exception as e:
        return f"Hata: {e}"

def summarize_text(text, title):
    """Gemini API kullanarak metni özetler."""
    try:
        # Prompt mühendisliği: Kısa, öz ve senin tarzına uygun
        prompt = (
            f"Aşağıdaki Ekşi Sözlük entry'si '{title}' başlığı altında yazılmış.\n"
            f"Bu yazıyı Lordum Eren için oku ve 2 cümleyle özetle.\n"
            f"Tonun hafif alaycı ve bilgilendirici olsun. İşte metin:\n\n{text}"
        )
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Yapay zeka yoruldu, özetleyemedi. Hata: {e}"

def send_email(report_body):
    """Hazırlanan raporu e-posta ile gönderir."""
    if not report_body:
        print("Gönderilecek içerik yok.")
        return

    msg = MIMEMultipart()
    msg['Subject'] = f"Günlük Ekşi Raporu - {datetime.date.today().strftime('%d.%m.%Y')}"
    msg['From'] = GMAIL_USER
    msg['To'] = ALICI_MAIL

    # Giriş metni
    intro = "Günaydın Lordum,\n\nEkşi Sözlük ahalisi dün yine neler saçmalamış, senin için derledim. İşte bugünün özeti:\n\n"
    full_text = intro + report_body + "\n\nSaygılarımla,\nDijital Kahyan Cemil"

    msg.attach(MIMEText(full_text, 'plain'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        print("Mail başarıyla gönderildi Lordum.")
    except Exception as e:
        print(f"Mail gönderirken hata oluştu: {e}")

# --- ANA AKIŞ ---
if __name__ == "__main__":
    print("Debe listesi çekiliyor...")
    debe_items = get_debe_list()
    
    if not debe_items:
        print("Debe listesi boş geldi veya çekilemedi.")
    else:
        full_report = ""
        
        for index, item in enumerate(debe_items, 1):
            print(f"[{index}/{len(debe_items)}] İşleniyor: {item['title']}")
            
            raw_content = get_entry_content(item['link'])
            
            # İçerik çok kısaysa (ör: "bkz") özetlemeye çalışma
            if len(raw_content) > 150:
                summary = summarize_text(raw_content, item['title'])
            else:
                summary = f"Kısa entry: {raw_content}"
            
            # Rapora ekle
            full_report += f"{index}. {item['title'].upper()}\n"
            full_report += f"Özet: {summary}\n"
            full_report += f"Link: {item['link']}\n"
            full_report += "-" * 40 + "\n\n"
            
            # API'yi boğmamak için kısa bekleme
            time.sleep(2)

        # Hepsini bitirince mail at
        send_email(full_report)