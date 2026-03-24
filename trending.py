import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import google.generativeai as genai
import time

# ---------------------------------------------------------
# 1. AI API 설정
# ---------------------------------------------------------
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

def analyze_with_ai(name, desc, language):
    """AI를 활용해 영문 설명을 한글로 요약하고, 파생/활용 가능성을 분석합니다."""
    if not ai_model or desc == "상세 설명이 제공되지 않은 프로젝트입니다.":
        return {
            "summary_kr": f"(원본) {desc}", 
            "use_case": "AI 분석을 위한 API 키가 없거나 프로젝트 설명이 부족합니다."
        }
    
    prompt = f"""
    다음은 GitHub 트렌딩에 올라온 '{name}' 이라는 오픈소스 프로젝트입니다.
    사용 언어: {language}
    원문 설명: {desc}

    이 정보를 바탕으로 다음 두 가지 항목을 한국어로 작성해주세요.
    1. Summary: 이 프로젝트가 한눈에 어떤 서비스/툴인지 일반 개발자가 파악할 수 있도록 1~2줄로 명확히 요약.
    2. UseCase: 이 프로젝트의 실무 사용 용도와, 포크(Fork)해서 어떤 새로운 서비스나 비즈니스 로직으로 파생/활용될 수 있는지에 대한 전문가적 인사이트 (2~3줄).
    
    출력 형식은 반드시 아래와 같이 해주세요:
    Summary: [요약 내용]
    UseCase: [활용 방안 내용]
    """
    
    try:
        response = ai_model.generate_content(prompt)
        text = response.text
        
        # AI 응답 텍스트 파싱
        summary_kr = text.split('Summary:')[1].split('UseCase:')[0].strip() if 'Summary:' in text else desc
        use_case = text.split('UseCase:')[1].strip() if 'UseCase:' in text else "분석 불가"
        
        return {"summary_kr": summary_kr, "use_case": use_case}
    except Exception as e:
        print(f"AI 분석 실패 ({name}): {e}")
        return {"summary_kr": desc, "use_case": "AI 분석 중 오류가 발생했습니다."}

# ---------------------------------------------------------
# 2. GitHub 크롤링 로직
# ---------------------------------------------------------
def get_github_trending():
    url = "https://github.com/trending"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    repos = soup.select('article.Box-row')
    
    trending_data = []
    print("데이터 크롤링 및 AI 분석 시작... (시간이 조금 걸릴 수 있습니다)")
    
    for repo in repos[:10]:  # 상위 10개 추출
        # 저장소 이름 및 링크
        title_tag = repo.select_one('h2 a')
        name = title_tag.text.strip().replace('\n', '').replace(' ', '')
        link = "https://github.com" + title_tag['href']
        
        # 요약 설명
        desc_tag = repo.select_one('p')
        description = desc_tag.text.strip() if desc_tag else "상세 설명이 제공되지 않은 프로젝트입니다."
        
        # 언어
        lang_tag = repo.select_one('span[itemprop="programmingLanguage"]')
        language = lang_tag.text.strip() if lang_tag else "Unknown"
        
        # 스타, 포크, 오늘의 스타
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
            
            today_tag = mutted_div.select_one('span.float-sm-right')
            if today_tag:
                today_stars = today_tag.text.strip()
        
        # AI 분석 호출
        ai_insight = analyze_with_ai(name, description, language)
        time.sleep(2) # API Rate Limit(호출 제한) 방지를 위한 2초 대기
        
        trending_data.append({
            "name": name, 
            "link": link, 
            "desc": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "today_stars": today_stars,
            "summary_kr": ai_insight['summary_kr'],
            "use_case": ai_insight['use_case']
        })
        print(f"[{name}] 크롤링 및 분석 완료")
        
    return trending_data

# ---------------------------------------------------------
# 3. HTML 생성 로직
# ---------------------------------------------------------
def make_html_string(data):
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
            .repo-title {{ font-size: 1.3em; font-weight: bold; margin-bottom: 12px; }}
            a {{ color: #0366d6; text-decoration: none; }}
            .stats {{ margin-bottom: 15px; display: flex; gap: 10px; flex-wrap: wrap; }}
            .badge {{ padding: 5px 10px; border-radius: 20px; font-size: 0.85em; font-weight: bold; display: flex; align-items: center; gap: 5px; }}
            .badge.lang {{ background-color: #e1efff; color: #0969da; border: 1px solid #b6d4fe; }}
            .badge.star {{ background-color: #fff8c5; color: #9a6700; border: 1px solid #f9e28f; }}
            .badge.fork {{ background-color: #f3f2f2; color: #57606a; border: 1px solid #d0d7de; }}
            .badge.today {{ background-color: #dafbe1; color: #1a7f37; border: 1px solid #a3e635; }}
            .desc {{ color: #24292f; margin-bottom: 15px; font-size: 1.05em; line-height: 1.5; }}
            .detail {{ font-size: 0.95em; color: #444; background: #f6f8fa; padding: 15px; border-radius: 6px; border-left: 4px solid #0969da; line-height: 1.6; }}
            .eng-desc {{ font-size: 0.8em; color: #888; font-style: italic; margin-bottom: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 GitHub Trending AI Report ({today})</h1>
            <p>마광님, AI가 분석한 오늘 자 GitHub 트렌딩 주요 프로젝트 요약 및 인사이트 리포트입니다.</p>
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

            <div class="desc"><strong>🎯 한줄 요약:</strong> {item['summary_kr']}</div>
            <div class="eng-desc">원문: {item['desc']}</div>
            
            <div class="detail">
                <strong>💡 활용 포인트 (Fork & Use Case):</strong><br>
                {item['use_case']}
                <br><br>
                <span style="font-size: 0.85em; color: #57606a;">
                오늘 하루 <strong>{item['today_stars']}</strong>를 획득하며 <strong>{item['language']}</strong> 생태계에서 주목받고 있습니다.
                </span>
            </div>
        </div>
        """
    
    html_content += """
            <p style="text-align: center; color: #888; font-size: 0.8em; margin-top: 30px;">본 리포트는 GitHub Actions와 AI API를 통해 자동 생성되었습니다.</p>
        </div>
    </body>
    </html>
    """
    return html_content

# ---------------------------------------------------------
# 4. 파일 저장 및 이메일 발송 로직
# ---------------------------------------------------------
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
        print("⚠️ 이메일 설정(Secrets)이 되어있지 않아 발송을 건너뜁니다.")
        return

    msg = MIMEMultipart()
    msg['From'] = email_user
    msg['To'] = email_user
    msg['Subject'] = f"🚀 [GitHub Trending AI] {datetime.now().strftime('%Y-%m-%d')} 리포트"

    msg.attach(MIMEText(html_content, 'html'))

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_password)
            smtp.send_message(msg)
        print("이메일 발송 성공!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

# ---------------------------------------------------------
# 메인 실행부
# ---------------------------------------------------------
if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("⚠️ 주의: GEMINI_API_KEY가 설정되지 않았습니다. AI 분석 없이 원본 텍스트만 출력됩니다.")
        
    trending_data = get_github_trending()
    
    if trending_data:
        html_report = make_html_string(trending_data)
        save_as_html(html_report)
        send_email(html_report)
        print("모든 작업이 성공적으로 완료되었습니다.")
    else:
        print("트렌딩 데이터를 가져오지 못했습니다. 네트워크 상태나 GitHub 페이지 구조 변경을 확인하세요.")