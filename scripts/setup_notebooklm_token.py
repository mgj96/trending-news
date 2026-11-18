"""NotebookLM 마스터 토큰을 발급받아 GitHub Secret(NOTEBOOKLM_MASTER_TOKEN)에 등록하고,
PC에 남은 토큰 파일은 지운다. 처음 한 번, 또는 토큰이 무효가 됐을 때만 실행하면 된다.

준비: pip install "notebooklm-py[browser,headless]"
      GitHub CLI(gh) 설치 후 `gh auth login`
사용: 이 레포를 clone한 폴더에서
      python scripts/setup_notebooklm_token.py 본인메일@gmail.com
"""
import subprocess
import sys

from notebooklm.paths import get_master_token_path

SECRET_NAME = "NOTEBOOKLM_MASTER_TOKEN"


def main():
    if len(sys.argv) != 2:
        sys.exit("사용법: python scripts/setup_notebooklm_token.py 본인메일@gmail.com")
    email = sys.argv[1]

    # 1. 브라우저 창에서 구글 로그인 → 마스터 토큰 발급 (master_token.json 저장)
    subprocess.run([sys.executable, "-m", "notebooklm", "login", "--master-token", "--account", email], check=True)

    # 2. GitHub Secret 등록 (gh가 암호화해서 현재 폴더의 레포에 올린다)
    token_path = get_master_token_path()
    subprocess.run(["gh", "secret", "set", SECRET_NAME], input=token_path.read_bytes(), check=True)

    # 3. 구글 계정 전체 권한 토큰이므로 PC에는 남기지 않는다
    token_path.unlink()
    print(f"✅ {SECRET_NAME} 등록 완료, PC의 토큰 파일 삭제: {token_path}")


if __name__ == "__main__":
    main()
