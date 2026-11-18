# 📈 trending-news

매일 아침 9시(KST), 최신 GitHub 트렌딩 레포지토리를 자동으로 수집하여 **상세 요약 리포트(HTML)**를 생성하고 **이메일로 발송**하는 자동화 파이프라인입니다.

## ✨ 주요 기능 (Features)

* **자동화된 크롤링:** 매일 지정된 시간(오전 9시)에 `https://github.com/trending` 페이지의 상위 10개 레포지토리 정보를 가져옵니다.
* **상세 리포트 생성:** 단순한 링크 모음이 아닌, 각 레포지토리의 요약과 시사점을 포함한 가독성 높은 HTML 포맷의 리포트를 만듭니다.
* **자동 아카이빙:** 생성된 리포트는 날짜별(`github-trending-YYYY-MM-DD.html`)로 `outputs/` 디렉토리에 자동 커밋 및 저장됩니다.
* **이메일 알림:** 리포트 생성과 동시에 등록된 이메일 주소로 결과물을 즉시 발송합니다.
* **서버리스 동작:** 100% GitHub Actions 기반으로 동작하여 별도의 서버 유지보수가 필요 없습니다.

---

## 🛠 기술 스택 (Tech Stack)

* **Language:** Python 3.9
* **Libraries:** `requests`, `beautifulsoup4` (웹 스크래핑), `smtplib`, `email` (메일 발송)
* **CI/CD & Automation:** GitHub Actions

---

## ⚙️ 설정 가이드 (Setup & Configuration)

이 레포지토리를 포크(Fork)하여 직접 사용하시려면 아래 2가지 설정이 반드시 필요합니다.

### 1. 쓰기 권한 설정 (Workflow Permissions)
GitHub Actions가 `outputs` 폴더에 HTML 파일을 생성하고 커밋할 수 있도록 권한을 부여해야 합니다.
1. 레포지토리 상단의 **Settings** 탭 클릭
2. 왼쪽 메뉴에서 **Actions > General** 선택
3. 화면 하단의 **Workflow permissions** 섹션에서 **`Read and write permissions`** 체크 후 **Save**

### 2. 이메일 발송 설정 (GitHub Secrets)
이메일 발송을 위해 Gmail 계정과 앱 비밀번호를 Secrets에 안전하게 등록합니다.
*(참고: Gmail 2단계 인증 설정 후 '앱 비밀번호'를 발급받아야 합니다.)*
1. 레포지토리 상단의 **Settings** 탭 클릭
2. 왼쪽 메뉴에서 **Secrets and variables > Actions** 선택
3. **New repository secret** 버튼을 눌러 아래 두 가지를 등록합니다.
   * `EMAIL_USER` : 본인의 Gmail 주소 (예: example@gmail.com)
   * `EMAIL_PASSWORD` : 발급받은 16자리 앱 비밀번호 (띄어쓰기 없이 입력)

### 3. (선택) NotebookLM 오디오 설정
매일 리포트로 NotebookLM 노트북을 만들고 한국어 오디오 개요를 생성해 둡니다 (NotebookLM 앱에서 청취).
비공식 라이브러리([notebooklm-py](https://github.com/teng-lin/notebooklm-py))를 쓰며, 실패해도 리포트/메일에는 영향이 없습니다.
1. PC에 `pip install "notebooklm-py[browser,headless]"` 와 [GitHub CLI](https://cli.github.com/) 설치 후 `gh auth login`
2. 이 레포를 clone한 폴더에서 `python scripts/setup_notebooklm_token.py 본인메일@gmail.com` 실행
   → 브라우저로 구글 로그인 → `NOTEBOOKLM_MASTER_TOKEN` Secret 자동 등록 → PC의 토큰 파일 삭제
* 마스터 토큰은 구글 계정 전체 권한이므로 레포 쓰기 권한을 다른 사람에게 주지 마세요. 비밀번호를 바꾸면 2번을 다시 실행합니다.

---

## 🚀 실행 방법 (Usage)

* **자동 실행 (Scheduled):** 설정된 Cron 표기법(`0 0 * * *`)에 따라 매일 한국 시간 오전 9시에 자동으로 실행됩니다.
* **수동 실행 (Manual):** 1. 레포지토리의 **Actions** 탭으로 이동합니다.
  2. 왼쪽 워크플로우 목록에서 `Daily GitHub Trending Report`를 선택합니다.
  3. 우측의 파란색 **Run workflow** 버튼을 클릭하여 즉시 스크립트를 테스트할 수 있습니다.

---

## 📂 디렉토리 구조 (Repository Structure)

```text
.
├── .github/
│   └── workflows/
│       └── daily_report.yml    # GitHub Actions 자동화 설정 파일
├── outputs/                    # 생성된 HTML 리포트가 날짜별로 저장되는 폴더
├── trending.py                 # 크롤링, HTML 생성, 메일 발송을 담당하는 메인 스크립트
└── README.md
