"""PR diff를 Gemini로 리뷰하고 결과를 마크다운으로 저장한다.

- 입력: pr.diff (워크플로우에서 git diff로 생성)
- 출력: review.md (워크플로우에서 PR 코멘트로 게시)
- 사용 모델: gemini-3-flash-preview (trending.py와 동일 모델로 통일)
"""
import os
import sys
import google.generativeai as genai

# diff가 너무 크면 토큰 초과 → 앞부분만 잘라서 보냄 (약 6만 자 ≈ 1.5만 토큰)
MAX_DIFF_CHARS = 60_000

MODEL_NAME = "gemini-3-flash-preview"

REVIEW_PROMPT = """당신은 시니어 개발자입니다. 아래 GitHub Pull Request의 diff를 리뷰하세요.

다음 기준으로만 체크하고, 문제가 없으면 "특이사항 없음"이라고 쓰세요:
1. 버그 가능성 (널 체크, 예외 처리, 경계 조건)
2. 보안 (하드코딩된 시크릿, 인젝션, 권한 과다)
3. 가독성/유지보수 (네이밍, 중복, 과한 복잡도)

규칙:
- 한국어로, 간결하게.
- 추측성 잔소리 금지. 근거 있는 것만.
- 각 지적은 `파일:라인 — 내용` 형식.
- 마지막에 한 줄 총평.

--- DIFF ---
{diff}
"""


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY가 없습니다.", file=sys.stderr)
        return 1

    try:
        with open("pr.diff", encoding="utf-8") as f:
            diff = f.read()
    except FileNotFoundError:
        diff = ""

    if not diff.strip():
        _write("변경된 코드가 없어 리뷰를 건너뜁니다.")
        return 0

    truncated = len(diff) > MAX_DIFF_CHARS
    if truncated:
        diff = diff[:MAX_DIFF_CHARS]

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(MODEL_NAME)
    # str.format 대신 replace 사용 (방어적).
    # 참고: 여기선 .format도 안전하다 — 템플릿엔 {diff}뿐이고 diff는 값으로만 삽입돼
    # 재파싱되지 않기 때문. 다만 나중에 프롬프트에 중괄호 예시가 추가돼도
    # 깨지지 않도록 replace로 둔다. (봇의 'KeyError' 지적은 실제론 오탐이었음)
    prompt = REVIEW_PROMPT.replace("{diff}", diff)
    resp = model.generate_content(prompt)

    # 세이프티 필터 등으로 응답이 차단되면 resp.text 접근이 예외를 던진다.
    # (봇이 PR #2에서 지적한 유효한 케이스 → 방어 코드 추가)
    try:
        review_text = resp.text
    except (ValueError, AttributeError):
        _write("⚠️ AI 응답을 가져오지 못했습니다 (안전 필터 차단 또는 빈 응답).")
        return 0

    body = f"## 🤖 AI 코드 리뷰 ({MODEL_NAME})\n\n{review_text}\n"
    if truncated:
        body += (
            f"\n> ⚠️ diff가 {MAX_DIFF_CHARS:,}자를 초과해 앞부분만 리뷰했습니다."
        )
    body += "\n\n<sub>이 리뷰는 자동 생성되었습니다. 최종 판단은 사람이 합니다.</sub>"
    _write(body)
    return 0


def _write(text: str) -> None:
    with open("review.md", "w", encoding="utf-8") as f:
        f.write(text)


if __name__ == "__main__":
    sys.exit(main())
