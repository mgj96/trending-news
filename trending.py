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

CS_QUIZ = [
    {"q": "프로세스와 스레드의 차이는? 멀티스레드가 멀티프로세스보다 가벼운 이유와 대가는?",
     "a": "• 프로세스는 독립된 주소 공간(코드·데이터·힙)을 가진 실행 단위, 스레드는 프로세스 안에서 힙·데이터를 공유하고 스택·레지스터만 따로 가진다.\n• 스레드는 메모리를 공유해 생성·컨텍스트 스위칭 비용이 작고 통신이 쉽다.\n• 대가: 공유 자원에 대한 경쟁 상태(race condition)와 동기화 문제, 한 스레드의 크래시가 프로세스 전체에 영향을 준다.\n• 프로세스는 격리가 강해 안전하지만 IPC(파이프, 소켓, 공유 메모리)가 필요하고 무겁다."},
    {"q": "TCP와 UDP의 차이는? TCP의 3-way handshake는 왜 필요할까?",
     "a": "• TCP: 연결 지향, 순서 보장·재전송·흐름/혼잡 제어를 해주는 신뢰성 프로토콜. UDP: 비연결, 신뢰성 보장 없이 헤더가 작고 빠르다(실시간 영상·게임·DNS 등).\n• 3-way(SYN → SYN+ACK → ACK)는 양쪽이 서로 송수신 가능한지 확인하고 초기 시퀀스 번호를 교환하기 위해 필요하다.\n• 2-way로는 서버가 \"클라이언트가 내 응답을 받았는지\" 알 수 없고, 지연된 옛 SYN 때문에 불필요한 연결이 생길 수 있다."},
    {"q": "브라우저 주소창에 URL을 입력하고 엔터를 치면 화면이 뜨기까지 어떤 일이 일어날까?",
     "a": "• DNS 조회로 도메인을 IP로 바꾼다(브라우저·OS 캐시 → 리졸버 → 루트/TLD/권한 서버).\n• TCP 연결(3-way handshake), HTTPS면 TLS 핸드셰이크로 암호화 채널을 만든다.\n• HTTP 요청을 보내고 응답(HTML)을 받는다.\n• HTML 파싱 → DOM, CSS → CSSOM → 렌더 트리 → 레이아웃 → 페인트. 중간에 만나는 JS·CSS·이미지는 추가 요청으로 받는다."},
    {"q": "데드락이 발생하는 4가지 조건과, 이를 피하는 대표적인 방법은?",
     "a": "• 4조건(모두 성립해야 발생): 상호 배제, 점유와 대기, 비선점, 순환 대기.\n• 하나만 깨도 예방된다. 가장 흔한 방법은 자원에 순서를 정해 항상 같은 순서로 잠그는 것(순환 대기 제거).\n• 그 밖에 한 번에 모든 자원 요청, 타임아웃 후 락 해제·재시도, 락 범위 최소화, 은행원 알고리즘 같은 회피 기법이 있다.\n• DB는 데드락을 감지해 한 트랜잭션을 롤백(희생자 선택)하기도 한다."},
    {"q": "DB 인덱스는 왜 조회를 빠르게 할까? 만능이 아닌 이유는?",
     "a": "• 대부분의 RDBMS 인덱스는 B-Tree(B+Tree) 계열: 정렬된 트리를 타고 내려가 O(log N)에 찾고, 풀 스캔(O(N))을 피한다. 범위 검색과 정렬에도 유리하다.\n• 대가: INSERT/UPDATE/DELETE 때 인덱스도 갱신해야 해 쓰기가 느려지고, 저장 공간을 추가로 쓴다.\n• 카디널리티가 낮은 컬럼(성별 등)은 효과가 작다. 복합 인덱스는 선두 컬럼 순서가 중요하고, 컬럼에 함수를 씌우거나 앞부분 와일드카드(LIKE '%x')면 인덱스를 못 탄다."},
    {"q": "트랜잭션의 ACID란? 격리 수준(Isolation Level)이 낮으면 어떤 문제가 생길까?",
     "a": "• Atomicity(전부 또는 전무), Consistency(제약 조건을 지키는 상태 유지), Isolation(동시 실행이 서로 간섭하지 않음), Durability(커밋된 결과는 장애에도 유지).\n• 격리 수준이 낮으면: Dirty Read(커밋 안 된 값 읽기), Non-repeatable Read(같은 행을 다시 읽었더니 값이 다름), Phantom Read(같은 조건으로 다시 조회했더니 행 수가 다름).\n• 수준: READ UNCOMMITTED < READ COMMITTED < REPEATABLE READ < SERIALIZABLE. 높을수록 안전하지만 동시성이 떨어진다."},
    {"q": "해시 테이블에서 충돌이 나면 어떻게 해결할까? 평균/최악 시간 복잡도는?",
     "a": "• 체이닝: 같은 버킷에 연결 리스트(또는 트리)로 달아둔다. 오픈 어드레싱: 다른 빈 칸을 찾는다(선형·이차 탐사, 더블 해싱).\n• 평균 조회·삽입은 O(1), 모든 키가 한 버킷에 몰리는 최악은 O(N).\n• 적재율(load factor)이 높아지면 테이블을 키우고 재해싱해 평균 성능을 유지한다.\n• 좋은 해시 함수는 키를 고르게 퍼뜨리는 것이 핵심이다."},
    {"q": "가상 메모리란? 페이징과 페이지 폴트는 어떻게 동작할까?",
     "a": "• 프로세스마다 독립된 연속 주소 공간처럼 보이게 하고, 실제 물리 메모리·디스크에 매핑해 주는 추상화다. 격리와 메모리 초과 사용을 가능하게 한다.\n• 페이징: 메모리를 같은 크기의 페이지/프레임으로 나눠 페이지 테이블로 변환한다(TLB가 변환 결과를 캐시).\n• 페이지 폴트: 접근한 페이지가 물리 메모리에 없을 때 OS가 디스크에서 불러온다. 너무 잦으면 스레싱(thrashing)으로 성능이 급락한다.\n• 교체 알고리즘 예: LRU, FIFO, Clock."},
    {"q": "HTTPS는 HTTP와 무엇이 다르고, TLS 핸드셰이크에서는 어떤 일이 일어날까?",
     "a": "• HTTPS = HTTP + TLS. 암호화(도청 방지), 무결성(변조 방지), 인증(서버 신원 확인)을 제공한다.\n• 핸드셰이크 요지: 서버가 인증서를 보내고 클라이언트가 CA 서명 체인으로 검증 → 키 교환(ECDHE 등)으로 세션 키를 합의 → 이후 통신은 빠른 대칭키 암호화.\n• 비대칭키는 키 교환·인증에, 대칭키는 실제 데이터 암호화에 쓰는 역할 분담이 핵심이다."},
    {"q": "캐시가 효과를 내는 원리인 지역성(locality)이란? 캐시 교체 정책으로 LRU를 쓰는 이유는?",
     "a": "• 시간 지역성: 최근 접근한 데이터를 곧 다시 접근한다. 공간 지역성: 접근한 데이터 근처를 곧 접근한다(배열 순회 등).\n• 이 성질 덕분에 작고 빠른 캐시가 느리고 큰 저장소의 접근 대부분을 대신한다.\n• LRU는 \"가장 오래 안 쓴 것을 버린다\"로 시간 지역성에 잘 맞는다. 구현은 해시맵 + 이중 연결 리스트로 O(1).\n• 캐시를 쓸 땐 무효화(invalidation)와 데이터 불일치가 가장 어려운 문제다."},
    {"q": "동기/비동기와 블로킹/논블로킹은 어떻게 다를까?",
     "a": "• 블로킹/논블로킹은 \"호출한 쪽이 결과가 올 때까지 멈춰 있나\"(제어권), 동기/비동기는 \"결과를 호출자가 직접 확인하나, 완료 통지(콜백 등)를 받나\"(결과 처리 방식)의 관점이다.\n• 조합 예: 블로킹 + 동기(일반 read), 논블로킹 + 동기(폴링), 논블로킹 + 비동기(epoll/이벤트 루프 + 콜백, async/await).\n• 스레드 하나로 많은 I/O를 다루는 서버(Node.js, Netty)는 논블로킹 + 이벤트 루프 구조다."},
    {"q": "뮤텍스와 세마포어의 차이는? 언제 각각 쓸까?",
     "a": "• 뮤텍스: 한 번에 한 스레드만 임계 구역에 들어가게 하는 상호 배제 락. 락을 건 스레드만 풀 수 있다(소유권).\n• 세마포어: 카운터로 동시에 접근 가능한 수를 N개로 제한한다(예: 커넥션 풀 10개). 소유권이 없어 다른 스레드가 signal할 수 있다(스레드 간 신호 전달에도 사용).\n• 단일 자원 보호는 뮤텍스, 자원 개수 제한·실행 순서 조율은 세마포어가 맞다."},
    {"q": "DB 정규화는 왜 하고, 반정규화는 언제 선택할까?",
     "a": "• 정규화: 중복을 없애 갱신 이상(삽입·수정·삭제 시 불일치)을 막는 설계. 같은 사실은 한 곳에만 저장한다.\n• 대가: 조회 시 JOIN이 늘어 느려질 수 있다.\n• 반정규화: 읽기 성능이 중요하고 JOIN 비용이 병목일 때 일부러 중복을 허용한다(집계 컬럼, 복사 컬럼 등). 일관성을 앱·배치·트리거로 직접 지켜야 하는 부담이 생긴다.\n• 원칙: 먼저 정규화하고, 측정으로 병목을 확인한 뒤 필요한 곳만 반정규화."},
    {"q": "CAP 정리란? 분산 DB에서 \"CP\"와 \"AP\"를 고른다는 말은 무슨 뜻일까?",
     "a": "• 네트워크 분할(Partition)이 생기면 일관성(Consistency)과 가용성(Availability)을 동시에 완전히 만족할 수 없다는 정리.\n• CP: 분할 시 일관성을 지키려고 일부 요청을 거부/대기시킨다(가용성 희생). AP: 응답은 계속하되 노드 간 값이 잠시 다를 수 있다(최종적 일관성).\n• 분할은 현실에서 피할 수 없으므로 실제 선택은 \"분할이 났을 때 C와 A 중 무엇을 포기할까\"이다.\n• 정상 상태의 지연 vs 일관성 trade-off까지 다룬 것이 PACELC."},
    {"q": "컨텍스트 스위칭이란? 왜 비용이 들고, 어떻게 줄일까?",
     "a": "• CPU가 실행하던 프로세스/스레드의 상태(레지스터, 프로그램 카운터 등)를 저장하고 다른 것의 상태를 복원해 실행을 넘기는 일.\n• 비용: 저장·복원 자체 + CPU 캐시/TLB가 무효화돼 다시 데워야 하는 간접 비용(프로세스 간 전환은 주소 공간이 바뀌어 더 크다).\n• 줄이는 방법: 스레드 수를 코어 수에 맞춰 제한(스레드 풀), 논블로킹 I/O·이벤트 루프, 락 경합 줄이기."},
    {"q": "퀵 정렬의 평균·최악 시간 복잡도는? 최악을 피하려면 어떻게 할까?",
     "a": "• 평균 O(N log N), 최악 O(N²). 이미 정렬된 배열에서 첫/끝 원소를 피벗으로 고르면 한쪽으로만 쪼개져 최악이 된다.\n• 피벗을 무작위로 고르거나 3개 값의 중앙값(median-of-three)으로 고르면 최악을 사실상 피한다.\n• 제자리(in-place) 정렬이라 추가 메모리가 적고 캐시 효율이 좋아 실전에서 빠르다. 다만 안정 정렬이 아니다.\n• 병합 정렬은 항상 O(N log N)이고 안정적이지만 O(N) 추가 메모리가 든다."},
]

def pick_quiz(now):
    """날짜별로 CS 질문 풀을 순환한다 (하루에 하나)."""
    return CS_QUIZ[now.toordinal() % len(CS_QUIZ)]

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
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', 'Noto Sans KR', Roboto, sans-serif; line-height: 1.6; padding: 10px; margin: 0; color: #333; background-color: #f9f9f9; word-break: keep-all; }}
            .container {{ max-width: 850px; margin: auto; background: #fff; border: 1px solid #e1e4e8; padding: 18px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            h1 {{ color: #24292e; font-size: 1.4em; border-bottom: 2px solid #eaecef; padding-bottom: 8px; margin: 0; }}
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
            .row {{ padding: 10px 0; border-bottom: 1px solid #eaecef; font-size: 0.95em; }}
            .name {{ font-size: 1.02em; overflow-wrap: anywhere; }}
            .sum {{ color: #24292e; margin-top: 2px; }}
            .why {{ color: #57606a; font-size: 0.88em; margin-top: 2px; }}
            .quiz-q {{ font-weight: bold; font-size: 1.05em; color: #24292e; margin: 4px 0; }}
            .quiz {{ background: #fff8c5; border-left: 4px solid #d4a72c; padding: 12px 16px; margin: 16px 0; font-size: 0.95em; }}
            .quiz-a {{ background: #f6f8fa; border-left: 4px solid #1a7f37; padding: 12px 16px; margin-top: 8px; font-size: 0.93em; color: #333; }}
            details summary {{ cursor: pointer; font-weight: bold; color: #1a7f37; }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🚀 트렌딩 {today[5:]}</h1>
            <p style="margin: 6px 0;">마광님, 오늘의 GitHub 트렌딩입니다. <span class="meta">📎 전체 내용은 첨부파일에서 볼 수 있어요.</span></p>

            <div class="quiz">
                <strong>🧠 오늘의 CS 질문</strong>
                <div class="quiz-q">{esc(quiz['q'])}</div>
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
                badges += f'<span class="chg {cls}">{esc(label)}</span> · '
            if streak_label(item):
                badges += f'{esc(streak_label(item))} · '
            html_content += f"""
            <div class="row">
                <div class="name"><span class="meta">#{item['rank']}</span> <a href="{esc(item['link'])}" target="_blank"><strong>{esc(item['name'])}</strong></a></div>
                <div class="meta">{badges}⭐ 오늘 {esc(today_num(item['today_stars']))}</div>
                <div class="sum">{esc(short(item['summary_kr'], 75))}</div>
                <div class="why">🔥 {esc(short(item['why_trending'], 90))}</div>
            </div>
            """

    # 정답: 맨 아래에 둔다. <details>를 지원하는 클라이언트에서는 접혀 있고, Gmail 등에서는 펼쳐 보인다.
    answer_html = esc(quiz['a']).replace("\n", "<br>")
    html_content += f"""
            <p style="text-align: center; color: #6e7781; font-size: 0.8em; margin-top: 30px;">본 리포트는 GitHub Actions와 AI API를 통해 자동 생성되었습니다.</p>

            <div style="margin-top: 60px;">
                <details>
                    <summary>🔑 오늘의 CS 질문 — 정답 보기</summary>
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
    lines = [f"트렌딩 {today[5:]}", "(📎 전체 내용은 첨부파일에서 볼 수 있어요)", ""]
    lines += ["[오늘의 CS 질문]", quiz['q'], "(정답은 맨 아래에 있어요)", ""]

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
    lines += ["", "", "", "", "", "[정답] 오늘의 CS 질문", quiz['a']]
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
    msg['Subject'] = f"🚀 트렌딩 {datetime.now().strftime('%m-%d')}"

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
