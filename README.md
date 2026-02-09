# VoiceGrape (음성 포도)

VoiceGrape는 Parselmouth(Praat) 알고리즘을 활용하여 사용자의 음성을 정밀 분석하고 시각화하는 Streamlit 기반 웹 애플리케이션입니다.

## 주요 기능
- **음성 분석**: 피치(Pitch), 포먼트(Formant), 지터(Jitter), 시머(Shimmer) 등 전문 지표 분석.
- **종합 평가**: 목소리 컨디션 점수 산출 및 맞춤형 발성 팁 제공.
- **히스토리 관리**: Google Sheets와 연동하여 과거 분석 기록 저장 및 변화 추이 그래프 제공.
- **리포트 생성**: 분석 결과를 PDF 리포트로 저장하거나 이메일로 즉시 전송.

## 실행 방법

### 1. 환경 준비
Python 3.9 이상의 환경이 권장됩니다.

```bash
# 저장소 클론
git clone https://github.com/project-saerom/voicegrape.git
cd voicegrape

# 가상환경 생성 및 활성화
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

### 2. 필수 패키지 설치
```bash
pip install -r requirements.txt
```

### 3. 보안 설정 (Secrets)
이 앱은 Google Sheets DB와 이메일 전송 기능을 사용하므로, `.streamlit/secrets.toml` 파일을 생성하고 아래 정보를 설정해야 합니다. (이 파일은 보안을 위해 Git 추적에서 제외됩니다.)

```toml
[gcp_service_account]
# Google Cloud Console에서 생성한 서비스 계정 키(JSON) 내용을 입력하세요.
type = "service_account"
project_id = "..."
private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
client_email = "..."

[admin]
user = "admin_id"
password = "admin_password"

[smtp]
server = "smtp.gmail.com"
port = 587
user = "your_email@gmail.com"
password = "your_app_password"
```

### 4. 앱 실행
```bash
streamlit run voicegrape.py
```

## 개발 환경 (VS Code)
`.vscode/launch.json` 설정이 포함되어 있어, VS Code에서 `F5` 키를 눌러 바로 디버깅 모드로 실행할 수 있습니다.

---
© 2026 Saerom. Powered by Parselmouth & Streamlit.