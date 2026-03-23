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
            .repo {{ margin-bottom: 25px; padding: 20px; border: 1px solid #e1e4e8; border-radius: 8px; transition: all 0.2s ease