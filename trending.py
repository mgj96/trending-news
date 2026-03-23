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
        return "데이터를 가져오는데 실패했습니다."

    soup = BeautifulSoup(response.text, 'html.parser')
    repos = soup.select('article.Box-row')
    
    trending_data = []
    for repo in repos[:10]:  # 상위 10개 추출
        title_tag = repo.select_one('h2 a')
        name = title_tag.text.strip().replace('\n', '').replace(' ', '')
        link = "https://github.com" + title_tag['href']
        
        desc_tag = repo.select_one('p')
        description = desc_tag.text.strip() if desc_tag else "설명 없음"
        
        trending_data.append({"name": name, "link": link, "desc": description})
    return trending_data

def save_as_html(data):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/github-trending-{today}.html"
    
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <title>GitHub Trending Report - {today}</title>
        <style>
            body {{ font-family: sans-serif; line-height: 1.6; padding: 20px; }}
            .repo {{ margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }}
            a {{ color: #0366d6; text-decoration: none; font-weight: bold; }}
        </style>
    </head>
    <body>
        <h1>🚀 GitHub Trending 리포트 ({today})</h1>
    """
    
    for item in data:
        html_content += f"""
        <div class="repo">
            <h3><a href="{item['link']}">{item['name']}</a></h3>
            <p><strong>요약:</strong> {item['desc']}</p>
            <p>상세 내용: 이 레포지토리는 현재 GitHub에서 큰 관심을 받고 있는 프로젝트입니다. 
            주로 최신 기술 트렌드나 유용한 라이브러리를 포함하고 있으며, 개발자 커뮤니티에서 활발하게 논의되고 있습니다. 
            상세한 코드는 링크를 통해 확인해 보세요.</p>
        </div>
        """
    
    html_content += "</body></html>"
    
    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"리포트 생성 완료: {filename}")

def send_email(html_content):
    # GitHub Secrets에서 환경변수 가져오기
    email_user = os.environ.get('EMAIL_USER')
    email_password = os.environ.get('EMAIL_PASSWORD')
    
    if not email_user or not email_password:
        print("이메일 설정 정보가 없습니다.")
        return

    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = email_user  # 본인에게 발송
    msg['Subject'] = f"🚀 GitHub Trending Report ({datetime.now().strftime('%Y-%m-%d')})"

    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_password)
            smtp.send_message(msg)
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

if __name__ == "__main__":
    data = get_github_trending()
    # HTML 생성 시 사용한 문자열을 변수에 담아 이메일로 전달
    html_report = make_html_string(data) # HTML 생성 함수를 문자열 반환형으로 수정 권장
    save_as_html(html_report) 
    send_email(html_report)