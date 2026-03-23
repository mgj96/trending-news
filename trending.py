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
        # 1. 저장소 이름 및 링크
        title_tag = repo.select_one('h2 a')
        name = title_tag.text.strip().replace('\n', '').replace(' ', '')
        link = "https://github.com" + title_tag['href']
        
        # 2. 요약 설명
        desc_tag = repo.select_one('p')
        description = desc_tag.text.strip() if desc_tag else "상세 설명이 제공되지 않은 프로젝트입니다."
        
        # 3. 추가 정보 (언어, 스타, 포크, 오늘 받은 스타)
        # 언어
        lang_tag = repo.select_one('span[itemprop="programmingLanguage"]')
        language = lang_tag.text.strip() if lang_tag else "Unknown"
        
        # 스타, 포크, 오늘의 스타 크롤링을 위해 하단 통계 영역 파싱
        mutted_div = repo.select_one('div.f6.color-fg-muted.mt-2')
        stars = "0"
        forks = "0"
        today_stars = "0 stars today"
        
        if mutted_div:
            links = mutted_div.select('a')
            for a in links:
                if 'stargazers' in a.get('href', ''):
                    stars = a.text.strip().replace('\n', '').replace(' ', '')
                elif 'forks' in a.get('href', ''):
                    forks = a.text.strip().replace('\n', '').replace(' ', '')
            
            # 오늘의 스타
            today_tag = mutted_div.select_one('span.float-sm-right')
            if today_tag:
                today_stars = today_tag.text.strip()
        
        trending_data.append({
            "name": name, 
            "link": link, 
            "desc": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "today_stars": today_stars
        })
        
    return trending_data

def make_html_string(data):
    """HTML 리포트 문자열을 생성하는 함수"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; padding: 20px; color: #333; background-color: #f9f9f9; }}
            .container {{ max-width: 850px; margin: auto; background: #fff; border: 1px solid #e1e4e8; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            h1 {{ color: #24292e; border-bottom: 2px solid #eaecef; padding-bottom: 10px; margin-top: 0; }}
            .repo {{ margin-bottom: 25px; padding: 20px; border: 1px solid #e1e4e8; border-radius: 8px; transition: all 0.2s ease; }}
            .repo:hover {{ box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-color: #0366d6; }}
            .repo-title {{ font-size: 1.3em; font-weight: bold; margin-bottom: 12px; }}
            a {{ color: #0366d6; text-decoration: none; }}
            a:hover {{ text-decoration: underline; }}
            .stats {{ margin-bottom: 15px; display: flex; gap: 10px; flex-wrap: wrap; }}
            .badge {{ padding: 5px 10px; border-radius: 20px; font-size: 0.85em; font-weight: bold; display: flex; align-items: center; gap: 5px; }}
            .badge.lang {{ background-color: #e1efff; color: #0969da; border: 1px solid #b6d4fe; }}
            .badge.star {{ background-color: #fff8c5; color: #9a6700; border: 1px solid #f9e28f; }}
            .badge.fork {{ background-color: #f3f2f2; color: #57606a; border: 1px solid #d0d7de; }}
            .badge.today {{ background-color: #dafbe1; color: #1a7f37; border: 1px solid #a3e635; }}
            .desc {{ color: #24292f; margin-bottom: 15px; font-size: 0.95em; }}
            .detail {{ font-size: 0.9em; color: #57606a; background: #f6f8fa; padding: 12px; border-radius: 6px; border-left: 4px solid #0969da; line-height: 1.5; }}
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
            <div class="repo-title">🔗 <a href="{item['link']}" target="_blank">{item['name']}</a></div>
            
            <div class="stats">
                <span class="badge lang">💻 {item['language']}</span>
                <span class="badge star">⭐ {item['stars']}</span>
                <span class="badge fork">🍴 {item['forks']}</span>
                <span class="badge today">📈 {item['today_stars']}</span>
            </div>

            <div class="desc"><strong>요약:</strong> {item['desc']}</div>
            
            <div class="detail">
                <strong>💡 포인트:</strong> 이 레포지토리는 오늘 하루 동안 <strong>{item['today_stars']}</strong>를 획득하며 급상승 중입니다. 
                현재 <strong>{item['language']}</strong> 생태계에서 주목받고 있으며, 전체 {item['stars']}개의 스타와 {item['forks']}개의 포크를 기록하고 있습니다. 
                어떤 기술적 차별점이 있는지 코드를 직접 확인해 보세요!
            </div>
        </div>
        """
    
    html_content += """
            <p style="text-align: center; color: #888; font-size: 0.8em; margin-top: 30px;">본 리포트는 GitHub Actions를 통해 자동 생성되었습니다.</p>
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