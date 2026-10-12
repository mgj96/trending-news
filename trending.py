import requests
from bs4 import BeautifulSoup
from datetime import datetime
from html import escape as esc
import glob
import json
import os
import re
import sys
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
    ai_model = genai.GenerativeModel('gemini-3-flash-preview')
else:
    ai_model = None

def analyze_with_ai(name, desc, language):
    """AI를 활용해 영문 설명을 한글로 요약하고, 파생/활용 가능성을 분석합니다."""
    if not ai_model or desc == "상세 설명이 제공되지 않은 프로젝트입니다.":
        return {
            "summary_kr": f"(원본) {desc}",
            "why_trending": "AI 분석을 위한 API 키가 없거나 프로젝트 설명이 부족합니다.",
            "detail": "AI 분석을 위한 API 키가 없거나 프로젝트 설명이 부족합니다."
        }

    prompt = f"""
    다음은 GitHub 트렌딩에 올라온 '{name}' 이라는 오픈소스 프로젝트입니다.
    사용 언어: {language}
    원문 설명: {desc}

    당신은 개발자 대상 뉴스레터를 쓰는 에디터입니다. 아래 세 항목을 한국어로 작성해주세요.
    뭉뚱그린 일반론("유용합니다", "생산성이 높아집니다" 등)은 피하고, 가능하면 구체적인 수치나 예시를 넣습니다.

    1. Summary: 이 프로젝트가 무엇인지 55~60자로 요약 (너무 짧게 쓰지 말고 이 분량을 채울 것). 메일 본문 목록용입니다.
    2. WhyTrending: 개발자들이 왜 흥미를 갖는지 — 해결하는 문제나 신선한 점을 65~70자로 (최대 70자, 이 분량을 채울 것).
    (1, 2번 작성 규칙: 완결된 문장 대신 개조식 축약체로 씁니다. 명사형으로 끝내고(~함, ~용, ~기반, ~지원),
     널리 쓰이는 약어(LLM, GPU, API, CLI, OSS 등)를 적극 사용해 글자 수 안에 정보를 최대한 담으세요.
     예: "70B급 LLM을 4GB VRAM GPU에서 구동하는 추론 엔진")
    3. Detail: 첨부 상세 리포트용. 무엇을 해결하고 어떻게 동작하는지, 실무 사용처, 포크(Fork) 시 파생할 수 있는 아이디어를 3~5문장으로.

    출력 형식은 반드시 아래와 같이 해주세요:
    Summary: [요약 내용]
    WhyTrending: [트렌딩 이유]
    Detail: [상세 설명]
    """

    try:
        response = ai_model.generate_content(prompt)
        text = response.text

        # AI 응답 텍스트 파싱
        summary_kr = text.split('Summary:')[1].split('WhyTrending:')[0].strip() if 'Summary:' in text else desc
        why_trending = text.split('WhyTrending:')[1].split('Detail:')[0].strip() if 'WhyTrending:' in text else "분석 불가"
        detail = text.split('Detail:')[1].strip() if 'Detail:' in text else "분석 불가"

        return {"summary_kr": summary_kr, "why_trending": why_trending, "detail": detail}
    except Exception as e:
        print(f"AI 분석 실패 ({name}): {e}")
        return {"summary_kr": desc, "why_trending": "AI 분석 중 오류가 발생했습니다.", "detail": "AI 분석 중 오류가 발생했습니다."}

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
        time.sleep(20) # API Rate Limit(호출 제한) 방지를 위한 20초 대기 무료 모델이라 RPM이 5뿐이라 횟수를 늘려 시간이 늦더라도 상관없게 변경

        trending_data.append({
            "rank": len(trending_data) + 1,
            "name": name,
            "link": link,
            "desc": description,
            "language": language,
            "stars": stars,
            "forks": forks,
            "today_stars": today_stars,
            "summary_kr": ai_insight['summary_kr'],
            "why_trending": ai_insight['why_trending'],
            "detail": ai_insight['detail']
        })
        print(f"[{name}] 크롤링 및 분석 완료")
        
    return trending_data

# ---------------------------------------------------------
# 3. 어제 대비 변화 / 테마 묶음
# ---------------------------------------------------------
REPO_LINK_RE = re.compile(r'href="https://github\.com/([\w.\-]+/[\w.\-]+)"')

def load_history(today_str, max_days=7):
    """outputs/ 의 과거 리포트에서 날짜별 순위 목록을 읽는다 (최신순). [(날짜, [repo, ...]), ...]

    리포트 안에서 레포 링크가 처음 등장하는 순서가 곧 순위다 (요약 표가 순위순이므로).
    예전 형식(URL 표)과 현재 형식(요약 표) 모두 같은 방식으로 읽힌다.
    """
    history = []
    for path in sorted(glob.glob("outputs/github-trending-*.html"), reverse=True):
        date = os.path.basename(path)[len("github-trending-"):-len(".html")]
        if date >= today_str:
            continue
        try:
            with open(path, encoding="utf-8") as f:
                html = f.read()
        except OSError:
            continue
        repos = []
        for name in REPO_LINK_RE.findall(html):
            key = name.lower()
            if key not in repos:
                repos.append(key)
        if repos:
            history.append((date, repos))
        if len(history) >= max_days:
            break
    return history

def annotate_changes(data, history):
    """각 항목에 직전 리포트 대비 변화(change)와 연속 등장 일수(streak)를 붙인다."""
    prev_rank = {}
    if history:
        prev_rank = {name: i + 1 for i, name in enumerate(history[0][1])}

    for item in data:
        key = item['name'].lower()
        if not history:
            item['change'] = ""  # 비교 대상이 없으면 표시하지 않음
        elif key not in prev_rank:
            item['change'] = "NEW"
        else:
            diff = prev_rank[key] - item['rank']
            item['change'] = f"▲{diff}" if diff > 0 else (f"▼{-diff}" if diff < 0 else "–")

        streak = 1
        for _, repos in history:
            if key not in repos:
                break
            streak += 1
        item['streak'] = streak

def group_by_theme(data):
    """AI로 프로젝트를 테마별로 묶고 상단 총평을 만든다. 실패하면 언어별로 묶는다.

    반환: (총평 문자열, [{"name": 테마명, "items": [item, ...]}, ...])
    """
    by_name = {item['name'].lower(): item for item in data}

    def fallback():
        groups = {}
        for item in data:
            groups.setdefault(item['language'], []).append(item)
        return "", [{"name": f"💻 {lang}", "items": items} for lang, items in groups.items()]

    if not ai_model:
        return fallback()

    listing = "\n".join(f"- {it['name']} ({it['language']}): {it['summary_kr']}" for it in data)
    prompt = f"""
    다음은 오늘 GitHub 트렌딩 상위 프로젝트 목록입니다.
    {listing}

    1. overview: 오늘 트렌드의 공통 흐름을 한국어 한 문장(80자 이내)으로 총평.
    2. themes: 프로젝트를 2~5개 테마로 묶기. 테마 이름은 이모지 하나 + 짧은 한국어(예: "🤖 AI 에이전트").
       모든 프로젝트는 정확히 한 테마에만 속해야 하며, 프로젝트는 위 목록의 이름을 그대로 씁니다.

    반드시 아래 JSON만 출력하세요 (설명, 코드블록 금지):
    {{"overview": "...", "themes": [{{"name": "🤖 ...", "repos": ["owner/repo"]}}]}}
    """

    try:
        text = ai_model.generate_content(prompt).text
        parsed = json.loads(text[text.index('{'):text.rindex('}') + 1])

        assigned = set()
        themes = []
        for theme in parsed.get("themes", []):
            items = []
            for repo in theme.get("repos", []):
                key = str(repo).replace(' ', '').lower()
                if key in by_name and key not in assigned:
                    assigned.add(key)
                    items.append(by_name[key])
            if items:
                items.sort(key=lambda it: it['rank'])
                themes.append({"name": str(theme.get("name", "")).strip() or "📦 기타", "items": items})

        rest = [it for it in data if it['name'].lower() not in assigned]
        if rest:
            themes.append({"name": "📦 기타", "items": rest})
        if not themes:
            return fallback()

        themes.sort(key=lambda t: t['items'][0]['rank'])
        return str(parsed.get("overview", "")).strip(), themes
    except Exception as e:
        print(f"테마 분류 실패: {e}")
        return fallback()

# ---------------------------------------------------------
# 4. 리포트 생성 (HTML / 텍스트)
# ---------------------------------------------------------
def short(text, limit):
    """공백을 정리하고 limit자를 넘으면 말줄임표로 줄인다 (요약 표용)."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit - 1].rstrip() + "…"

def today_num(text):
    """'25,599 stars today' -> '+25,599' (표 폭을 줄이기 위해 숫자만 남김)"""
    num = text.replace("stars today", "").replace("star today", "").strip()
    return f"+{num}" if num else text

CI_QUIZ = [
    {"q": "\"내 로컬에선 되는데 CI에선 실패한다\"의 흔한 원인 3가지와, 재현성을 높이는 방법은?",
     "a": "• 원인 ① 환경 차이(JDK/Node 버전, OS, 타임존, 로케일)\n• 원인 ② 의존성 버전 미고정(lock 파일 없음, SNAPSHOT/latest)\n• 원인 ③ 숨은 상태(로컬 캐시, 미커밋 파일, 환경변수, 테스트 실행 순서·공유 DB)\n• 대응: 버전 고정(.nvmrc, toolchain, lock 파일, npm ci), 같은 컨테이너 이미지로 로컬 재현, 깨끗한 체크아웃에서 빌드, 테스트 격리"},
    {"q": "CI에서 `npm install` 대신 `npm ci`를 권하는 이유는?",
     "a": "• npm ci는 package-lock.json 그대로만 설치하고, package.json과 어긋나면 실패한다.\n• node_modules를 지우고 새로 설치하므로 매 빌드의 결과가 같다(재현성).\n• npm install은 lock 파일을 갱신할 수 있어, 같은 커밋인데 빌드마다 의존성이 달라질 수 있다.\n• 참고: 이 repo의 CI는 npm install을 쓰고 있다 — lock 파일이 커밋돼 있다면 npm ci로 바꿀 후보."},
    {"q": "빌드가 15분 걸린다. 5분으로 줄이라고 한다. 어디부터 손대야 할까?",
     "a": "• 1순위는 추측이 아니라 측정: 단계별 소요 시간부터 확인한다.\n• 그다음 후보: 의존성 캐시, 변경된 영역만 빌드(paths 필터/affected), 테스트 병렬화·샤딩, 느린 테스트는 nightly로 분리, 불필요한 전체 clone(fetch-depth) 줄이기.\n• 가장 오래 걸리는 단계 하나를 줄이는 게 여러 개를 건드리는 것보다 효과가 크다."},
    {"q": "flaky(간헐 실패) 테스트를 \"실패하면 재시도\"로 덮어두면 왜 위험할까?",
     "a": "• CI에 대한 신뢰가 무너진다(빨간불을 무시하게 됨).\n• 진짜 간헐 버그(레이스 컨디션 등)가 같이 가려진다.\n• 빌드 시간이 늘어난다.\n• 대응: 격리(quarantine) + 티켓 + 원인 수정(시간·순서·외부 의존, 비동기 대기). 재시도는 통계로 드러내면서 임시로만 쓴다."},
    {"q": "CI에서 시크릿(API 키)을 다룰 때 지킬 원칙은? 포크한 저장소의 PR에 시크릿을 주면 왜 위험할까?",
     "a": "• 최소 권한, 환경별 분리, 로그 마스킹에만 의존하지 않기(값을 변환해 출력하면 마스킹되지 않는다).\n• 장기 키 대신 OIDC로 발급하는 단기 토큰이 더 안전하다.\n• 포크 PR은 신뢰할 수 없는 코드다. 그 코드가 시크릿에 접근하면 PR 하나로 키를 빼갈 수 있다. 그래서 pull_request에는 기본적으로 시크릿이 전달되지 않는다.\n• pull_request_target에서 PR 코드를 체크아웃해 실행하는 구성이 대표적인 사고 원인이다."},
    {"q": "Continuous Delivery와 Continuous Deployment의 차이는? 어느 쪽을 택할지는 무엇이 결정할까?",
     "a": "• Delivery: 언제든 배포 가능한 상태를 자동으로 보장하지만, 실제 배포는 사람이 승인한다.\n• Deployment: 파이프라인을 통과하면 사람 개입 없이 프로덕션까지 자동 배포한다.\n• 결정 요인: 테스트 신뢰도, 롤백 능력, 규제·승인 요건, 장애 시 영향도."},
    {"q": "봇이 CI에서 main 브랜치에 직접 `git push --force`로 결과물을 커밋하는 구조의 위험과 대안은?",
     "a": "• 위험: 사람이 올린 커밋을 덮어쓸 수 있고, 브랜치 보호 규칙과 충돌하며, push가 다시 워크플로우를 트리거하는 루프가 생길 수 있다.\n• 대안: force 없는 일반 push(필요 시 rebase), 산출물은 별도 브랜치·Pages·아티팩트로 분리, 커밋 메시지에 [skip ci], concurrency 그룹으로 동시 실행 방지."},
    {"q": "GitHub Actions에서 `actions/checkout@v4` 같은 태그 대신 커밋 SHA로 고정하라는 권고의 이유는?",
     "a": "• 태그는 나중에 다른 커밋으로 옮길 수 있다(mutable). 액션 저장소가 탈취되면 같은 태그가 악성 코드를 가리키게 된다.\n• 실제로 2025년 3월 tj-actions/changed-files 사고에서 태그가 변조돼 수많은 저장소의 시크릿이 로그에 노출됐다.\n• SHA로 고정하고 Dependabot으로 업데이트를 PR로 받으면 공급망 위험이 크게 줄어든다."},
    {"q": "파이프라인 단계는 어떤 순서로 배치해야 \"빠른 피드백\"을 줄 수 있을까?",
     "a": "• fail fast: 싸고 빠른 검사(lint, 타입체크, 단위 테스트)를 앞에, 느린 통합·E2E를 뒤에 둔다.\n• 서로 의존하지 않는 단계는 병렬로 돌린다.\n• 개발자가 결과를 기다리는 시간이 곧 비용이다. 흔히 PR 피드백은 10분 안쪽을 목표로 한다."},
    {"q": "CI 테스트는 전부 통과했는데 프로덕션에서 장애가 났다. 파이프라인 관점에서 무엇을 점검할까?",
     "a": "• 환경 패리티: 스테이징과 프로덕션의 설정·데이터·규모 차이.\n• 테스트 사각지대: 경계값, 동시성, 마이그레이션, 외부 연동.\n• Build once, deploy many: 테스트한 아티팩트와 배포한 아티팩트가 같은 것인지(환경마다 다시 빌드하면 안 된다).\n• 점진 배포(카나리/피처 플래그)와 관측성(로그·메트릭·알림)."},
    {"q": "모노레포에서 한 줄만 바꿨는데 전체 빌드·테스트가 도는 문제는 어떻게 풀까?",
     "a": "• 변경 감지: paths 필터나 git diff 기반으로 영향받는 패키지만 실행(affected).\n• 빌드 그래프 도구(Bazel, Nx, Turborepo, Gradle 등)와 원격 캐시로 이미 계산한 결과 재사용.\n• 주의: 의존 관계를 놓치면 영향받는 모듈의 테스트가 빠져 버그를 놓친다. 정기적으로 전체 빌드를 한 번씩 돌려 안전망을 둔다."},
    {"q": "CI 캐시는 빌드를 빠르게 하지만 위험하기도 하다. 언제, 왜 위험하고 캐시 키는 어떻게 짜야 할까?",
     "a": "• 오래된(stale) 캐시가 쓰이면 \"깨끗한 환경에서는 재현되지 않는 버그\"가 생긴다.\n• 캐시 키에 lock 파일 해시를 넣어(예: hashFiles('**/package-lock.json')) 의존성이 바뀌면 자동으로 무효화한다.\n• restore-keys 폴백은 편하지만 옛 캐시를 끌어올 수 있다.\n• 주기적으로 캐시 없는 클린 빌드를 돌려 검증한다."},
    {"q": "배포 후 문제가 생겼는데 롤백이 어렵다. 왜 어렵고, CI/CD 설계로 어떻게 쉽게 만들까?",
     "a": "• 코드는 되돌려도 DB 스키마 변경이나 이미 쓰인 데이터는 되돌리기 어렵다.\n• 대응: expand/contract(먼저 하위 호환 변경을 넣고, 나중에 옛 구조를 제거), 불변 아티팩트로 이전 버전 재배포, 피처 플래그로 기능만 끄기, 블루/그린·카나리 배포."},
    {"q": "\"main은 항상 초록이어야 한다\"를 지키려면 PR 머지 방식을 어떻게 설계할까?",
     "a": "• 브랜치 보호로 필수 체크를 통과해야만 머지하게 한다.\n• PR 단독으로는 통과해도 합치면 깨지는 경우(의미적 충돌)가 있으므로, 최신 base와 합친 상태로 다시 검증하는 머지 큐(또는 up-to-date 요구)를 쓴다.\n• 작은 PR, 짧게 사는 브랜치(trunk-based)가 충돌 자체를 줄인다."},
    {"q": "Java(Maven/Gradle) 프로젝트의 CI 빌드를 빠르고 재현성 있게 만들려면?",
     "a": "• 래퍼(mvnw/gradlew)로 빌드 도구 버전을 고정한다.\n• actions/setup-java로 JDK 배포판·버전을 고정하고 cache: maven(또는 gradle) 옵션으로 의존성 캐시.\n• mvn -B(비대화형)와 -T 1C 같은 병렬 옵션, Gradle build cache 활용.\n• SNAPSHOT 의존성은 같은 커밋이 다른 결과를 낼 수 있어 피한다."},
    {"q": "파이프라인을 YAML로 코드화(pipeline as code)하면 좋은 점과 함정은?",
     "a": "• 장점: 버전 관리·리뷰 가능, 재현성, 재사용(이 repo가 쓰는 reusable workflow처럼).\n• 함정: YAML 복붙으로 중복이 늘고, 로직이 YAML 안의 셸에 흩어지면 로컬에서 돌려볼 수 없어 디버깅이 힘들다.\n• 대응: 실제 로직은 스크립트/Makefile로 빼서 로컬과 CI가 같은 명령을 쓰고, YAML은 얇게 유지한다."},
]

def pick_quiz(now):
    """날짜별로 CI 질문 풀을 순환한다 (하루에 하나)."""
    return CI_QUIZ[now.toordinal() % len(CI_QUIZ)]

def change_label(item):
    """(CSS 클래스, 표시 문구). 비교 대상이 없으면 빈 값."""
    change = item.get('change', '')
    if change == "NEW":
        return "new", "🆕 NEW"
    if change.startswith("▲"):
        return "up", change
    if change.startswith("▼"):
        return "down", change
    if change == "–":
        return "same", change
    return "", ""

def streak_label(item):
    return f"🔁 {item['streak']}일 연속" if item.get('streak', 1) >= 2 else ""

def make_html_string(data, overview, themes, quiz):
    today = datetime.now().strftime("%Y-%m-%d")

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.6; padding: 20px; color: #333; background-color: #f9f9f9; }}
            .container {{ max-width: 850px; margin: auto; background: #fff; border: 1px solid #e1e4e8; padding: 30px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            h1 {{ color: #24292e; border-bottom: 2px solid #eaecef; padding-bottom: 10px; margin-top: 0; }}
            h2 {{ color: #24292e; font-size: 1.15em; margin: 28px 0 10px; }}
            h3 {{ color: #24292e; font-size: 1.05em; margin: 22px 0 4px; padding-bottom: 4px; border-bottom: 2px solid #eaecef; }}
            a {{ color: #0366d6; text-decoration: none; }}
            .meta {{ color: #57606a; font-size: 0.85em; font-weight: normal; }}
            .overview {{ background: #f6f8fa; border-left: 4px solid #0969da; padding: 10px 14px; margin: 14px 0; font-size: 0.95em; }}
            .chg {{ white-space: nowrap; font-weight: bold; }}
            .chg.new {{ color: #9a6700; }}
            .chg.up {{ color: #1a7f37; }}
            .chg.down {{ color: #cf222e; }}
            .chg.same {{ color: #888; font-weight: normal; }}
            .row {{ padding: 8px 0; border-bottom: 1px solid #eaecef; font-size: 0.95em; }}
            .why {{ color: #57606a; font-size: 0.88em; }}
            .quiz {{ background: #fff8c5; border-left: 4px solid #d4a72c; padding: 12px 16px; margin: 16px 0; font-size: 0.95em; }}
            .quiz-a {{ background: #f6f8fa; border-left: 4px solid #1a7f37; padding: 12px 16px; margin-top: 8px; font-size: 0.93em; color: #333; }}
            details summary {{ cursor: pointer; font-weight: bold; color: #1a7f37; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 GitHub Trending AI Report ({today})</h1>
            <p style="margin: 6px 0;">마광님, 오늘의 GitHub 트렌딩입니다. <span class="meta">📎 전체 내용은 첨부파일에서 볼 수 있어요.</span></p>

            <div class="quiz">
                <strong>🧠 오늘의 CI 질문</strong><br>
                {esc(quiz['q'])}<br>
                <span class="meta">생각해 본 뒤 답은 맨 아래에서 확인하세요 ⬇</span>
            </div>
    """

    if overview:
        html_content += f"""
            <div class="overview">💬 <strong>오늘의 흐름:</strong> {esc(overview)}</div>
        """

    for theme in themes:
        html_content += f"""
            <h3>{esc(theme['name'])}</h3>
        """
        for item in theme['items']:
            cls, label = change_label(item)
            badges = ""
            if label and cls != "same":
                badges += f' <span class="chg {cls}">{esc(label)}</span>'
            if streak_label(item):
                badges += f' <span class="meta">{esc(streak_label(item))}</span>'
            html_content += f"""
            <div class="row">
                <span class="meta">#{item['rank']}</span> <a href="{esc(item['link'])}" target="_blank"><strong>{esc(item['name'])}</strong></a>{badges}
                <span class="meta">· 오늘 {esc(today_num(item['today_stars']))}</span><br>
                {esc(short(item['summary_kr'], 75))}
                <div class="why">🔥 {esc(short(item['why_trending'], 90))}</div>
            </div>
            """

    # 정답: 맨 아래에 둔다. <details>를 지원하는 클라이언트에서는 접혀 있고, Gmail 등에서는 펼쳐 보인다.
    answer_html = esc(quiz['a']).replace("\n", "<br>")
    html_content += f"""
            <p style="text-align: center; color: #888; font-size: 0.8em; margin-top: 30px;">본 리포트는 GitHub Actions와 AI API를 통해 자동 생성되었습니다.</p>

            <div style="margin-top: 60px;">
                <details>
                    <summary>🔑 오늘의 CI 질문 — 정답 보기</summary>
                    <div class="quiz-a"><strong>Q.</strong> {esc(quiz['q'])}<br><br>{answer_html}</div>
                </details>
            </div>
        </div>
    </body>
    </html>
    """
    return html_content

def make_detail_html(data, overview, themes):
    """첨부/아카이브용 상세 리포트. 메일 본문과 달리 내용을 줄이지 않고 순위순으로 전부 담는다.

    load_history 가 '레포 링크 최초 등장 순서 = 순위'로 읽으므로, 순위순 배치와 제목 링크 구조를 유지해야 한다.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    theme_of = {it['name']: t['name'] for t in themes for it in t['items']}

    html_content = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ font-family: 'Malgun Gothic', sans-serif; line-height: 1.7; padding: 20px; color: #333; background-color: #f9f9f9; }}
            .container {{ max-width: 850px; margin: auto; background: #fff; border: 1px solid #e1e4e8; padding: 30px; border-radius: 12px; }}
            h1 {{ color: #24292e; border-bottom: 2px solid #eaecef; padding-bottom: 10px; margin-top: 0; }}
            a {{ color: #0366d6; text-decoration: none; }}
            .meta {{ color: #57606a; font-size: 0.85em; font-weight: normal; }}
            .overview {{ background: #f6f8fa; border-left: 4px solid #0969da; padding: 10px 14px; margin: 14px 0; }}
            .chg {{ white-space: nowrap; font-weight: bold; }}
            .chg.new {{ color: #9a6700; }}
            .chg.up {{ color: #1a7f37; }}
            .chg.down {{ color: #cf222e; }}
            .item {{ padding: 18px 0; border-bottom: 1px solid #eaecef; }}
            .item-title {{ font-weight: bold; font-size: 1.15em; }}
            .orig {{ color: #888; font-size: 0.82em; font-style: italic; margin: 4px 0 8px; }}
            .label {{ font-weight: bold; }}
            .detail {{ background: #f6f8fa; border-left: 4px solid #0969da; padding: 10px 14px; margin-top: 8px; font-size: 0.95em; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>📖 GitHub Trending 상세 리포트 ({today})</h1>
    """

    if overview:
        html_content += f"""
            <div class="overview">💬 <strong>오늘의 흐름:</strong> {esc(overview)}</div>
        """

    for item in data:
        cls, label = change_label(item)
        badges = ""
        if label and cls != "same":
            badges += f' <span class="chg {cls}">{esc(label)}</span>'
        if streak_label(item):
            badges += f' <span class="meta">{esc(streak_label(item))}</span>'
        theme_tag = f" · {esc(theme_of[item['name']])}" if item['name'] in theme_of else ""
        html_content += f"""
            <div class="item">
                <div class="item-title">#{item['rank']} <a href="{esc(item['link'])}" target="_blank">{esc(item['name'])}</a>{badges}</div>
                <div class="meta">{esc(item['language'])} · ⭐ {esc(item['stars'])} · 🍴 {esc(item['forks'])} · 오늘 {esc(today_num(item['today_stars']))}{theme_tag}</div>
                <div class="orig">원문: {esc(item['desc'])}</div>
                <div><span class="label">🎯 요약:</span> {esc(item['summary_kr'])}</div>
                <div><span class="label">🔥 흥미 포인트:</span> {esc(item['why_trending'])}</div>
                <div class="detail"><span class="label">📖 상세</span><br>{esc(item['detail'])}</div>
            </div>
        """

    html_content += """
            <p style="text-align: center; color: #888; font-size: 0.8em; margin-top: 30px;">본 리포트는 GitHub Actions와 AI API를 통해 자동 생성되었습니다.</p>
        </div>
    </body>
    </html>
    """
    return html_content

def make_text_string(data, overview, themes, quiz):
    """HTML을 못 보는 환경(알림 미리보기 등)용 텍스트 버전."""
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [f"GitHub Trending AI Report ({today})", "(📎 전체 내용은 첨부파일에서 볼 수 있어요)", ""]
    lines += ["[오늘의 CI 질문]", quiz['q'], "(정답은 맨 아래에 있어요)", ""]

    if overview:
        lines += [f"오늘의 흐름: {overview}", ""]

    for theme in themes:
        lines += ["", f"■ {theme['name']}"]
        for item in theme['items']:
            cls, label = change_label(item)
            extras = [x for x in (label if cls != "same" else "", streak_label(item)) if x]
            extra = f"  [{' / '.join(extras)}]" if extras else ""
            lines.append(f" #{item['rank']} {item['name']}{extra} ({today_num(item['today_stars'])})")
            lines.append(f"    {short(item['summary_kr'], 75)}")
            lines.append(f"    🔥 {short(item['why_trending'], 90)}")
            lines.append(f"    {item['link']}")

    lines += ["", "본 리포트는 GitHub Actions와 AI API를 통해 자동 생성되었습니다."]
    # 정답은 빈 줄을 띄워 스크롤해야 보이게 한다
    lines += ["", "", "", "", "", "[정답] 오늘의 CI 질문", quiz['a']]
    return "\n".join(lines)

# ---------------------------------------------------------
# 5. 파일 저장 및 이메일 발송 로직
# ---------------------------------------------------------
def save_as_html(html_report):
    """상세 리포트를 outputs/ 에 저장하고 파일 경로를 돌려준다 (다음 날 순위 비교에도 쓰인다)."""
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("outputs", exist_ok=True)
    filename = f"outputs/github-trending-{today}.html"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_report)
    print(f"파일 저장 완료: {filename}")
    return filename

def send_email(html_content, text_content, attachment_html, attachment_name):
    email_user = os.environ.get('EMAIL_USER')
    email_password = os.environ.get('EMAIL_PASSWORD')

    if not email_user or not email_password:
        print("⚠️ 이메일 설정(Secrets)이 되어있지 않아 발송을 건너뜁니다.")
        return True

    # mixed(본문 + 첨부) 안에 alternative(텍스트/HTML 중 클라이언트가 지원하는 마지막 파트를 표시)를 넣는다
    msg = MIMEMultipart('mixed')
    msg['From'] = email_user
    msg['To'] = email_user
    msg['Subject'] = f"🚀 [GitHub Trending AI] {datetime.now().strftime('%Y-%m-%d')} 리포트"

    body = MIMEMultipart('alternative')
    body.attach(MIMEText(text_content, 'plain', 'utf-8'))
    body.attach(MIMEText(html_content, 'html', 'utf-8'))
    msg.attach(body)

    attachment = MIMEText(attachment_html, 'html', 'utf-8')
    attachment.add_header('Content-Disposition', 'attachment', filename=attachment_name)
    msg.attach(attachment)

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_user, email_password)
            smtp.send_message(msg)
        print("이메일 발송 성공!")
        return True
    except Exception as e:
        print(f"이메일 발송 실패: {e}")
        return False

# ---------------------------------------------------------
# 메인 실행부
# ---------------------------------------------------------
if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print("⚠️ 주의: GEMINI_API_KEY가 설정되지 않았습니다. AI 분석 없이 원본 텍스트만 출력됩니다.")

    trending_data = get_github_trending()

    if trending_data:
        today_str = datetime.now().strftime("%Y-%m-%d")
        annotate_changes(trending_data, load_history(today_str))
        overview, themes = group_by_theme(trending_data)

        quiz = pick_quiz(datetime.now())
        html_report = make_html_string(trending_data, overview, themes, quiz)
        text_report = make_text_string(trending_data, overview, themes, quiz)
        detail_report = make_detail_html(trending_data, overview, themes)
        saved_path = save_as_html(detail_report)
        # 리포트 저장은 이미 끝난 상태. 메일 실패는 워크플로우를 실패로 만들어 알림이 가게 한다.
        if not send_email(html_report, text_report, detail_report, os.path.basename(saved_path)):
            sys.exit(1)
        print("모든 작업이 성공적으로 완료되었습니다.")
    else:
        print("트렌딩 데이터를 가져오지 못했습니다. 네트워크 상태나 GitHub 페이지 구조 변경을 확인하세요.")
