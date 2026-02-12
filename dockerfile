FROM python:3.10-slim

# 작업 디렉터리
WORKDIR /app

# [추가] OS 패키지 업데이트: 해결 가능한 보안 취약점을 최신 패치로 치료합니다.
# slim 이미지이므로 캐시 삭제를 통해 용량도 최적화합니다.
RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# pip 및 기본 도구 업데이트
RUN python -m pip install --upgrade pip setuptools==78.1.1 wheel

# 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 앱 소스 복사
COPY . .

# Flask가 바인딩할 포트
EXPOSE 5000

# 컨테이너 시작 시 실행 명령
CMD ["python", "app.py"]