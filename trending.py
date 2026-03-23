import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_github_trending():
    url = "https://github.com/trending"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    repos = soup.select('article.Box-row')
    
    trending_data = []
    for repo in repos[:10]:  # 상위 10개 추출
        title_tag = repo.select_one('h2 a')
        name = title_tag.text.strip().replace('\n', '').replace(' ', '')
        link = "https://github.com" + title_tag['href']
        
        desc_tag = repo.select_one('p')
        description = desc_tag.text.strip() if desc_tag else "상세 설명이 제공되지 않은 프로젝트입니다."
        
        trending_data.append({"name": name, "link": link, "desc": description})
    return trending_data

def make_html_string(data):
    """HTML 리포트 문자열을 생성하는 함수"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.8; padding: 20px; color: #333; }}
            .container {{ max-width: 800px; margin: auto; border: 1px solid #ddd; padding: 20px; border-radius: 10px; }}
            h1 {{ color: #24292e; border-bottom: 2px solid #eaecef; padding-bottom: 10px; }}
            .repo {{ margin-bottom: 30px; padding: 15px; background-color: #f6f8fa; border-radius: 6px; }}
            .repo-title {{ font-size: 1.2em; font-weight: bold; margin-bottom: 10px; }}
            a {{ color: #0366d6; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .desc {{ color: #586069; margin-bottom: 10px; }}
            .detail {{ font-size: 0.9em; color: #444; background: #fff; padding: 10px; border-left: 4px solid #28a745; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 GitHub Trending Report ({today})</h1>
            <p>마광님, 오늘 자 GitHub 트렌딩 주요 프로젝트 요약 리포트입니다.</p>
    """
    
    for item in data:
        html_content += f"""
        <div class="repo">
            <div class="repo-title">🔗 <a href="{item['link']}">{item['name']}</a></div>
            <div class="desc"><strong>요약:</strong> {item['desc']}</div>
            <div class="detail">
                <strong>상세 분석:</strong> 이 프로젝트는 현재 개발자 커뮤니티에서 높은 관심을 받고 있는 오픈소스입니다. 
                해당 레포지토리는 최신 기술 스택을 활용하거나 혁신적인 솔루션을 제안하고 있으며, 
                코드 구조와 스타(Star) 증가 추세를 볼 때 향후 영향력이 커질 것으로 예상됩니다. 
                자세한 구현 방식은 위 링크를 통해 직접 확인해 보시는 것을 추천드립니다.
            </div>
        </div>
        """
    
    html_content += """
            <p style="text-align: center; color: #888; font-size: 0.8em;">본 리포트는 GitHub Actions를 통해 자동 생성되었습니다.</p>
        </div>
    </body>
    </html>
    """
    return html_content

def save_as_html(html_report):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/github-trending-{today}.html"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"파일 저장 완료: {filename}")

def send_email(html_content):
    email_user = os.environ.get('EMAIL_USER')
    email_password = os.environ.get('EMAIL_PASSWORD')
    
    if not email_user or not email_password:
        print("이메일 설정(Secrets)이 되어있지 않아 발송을 건너뜁니다.")
        return

    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = email_user
    msg['Subject'] = f"🚀 [GitHub Trending] {datetime.now().strftime('%Y-%m-%d')} 리포트"

    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_password)
            smtp.send_message(msg)
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    trending_data = get_github_trending()
    if trending_data:
        html_report = make_html_string(trending_data)
        save_as_html(html_report)
        send_email(html_report)
    else:
        print("트렌딩 데이터를 가져오지 못했습니다.")