FROM python:3.10-slim

WORKDIR /app

# 1. OS 패키지 업데이트 및 pip 강제 업데이트
# --no-cache-dir를 사용하여 항상 최신 상태를 유지하게 합니다.
RUN apt-get update && apt-get upgrade -y && \
    python -m pip install --no-cache-dir --upgrade pip setuptools wheel && \
    rm -rf /var/lib/apt/lists/*

# 2. 의존성 파일 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 3. 앱 소스 복사
COPY . .

EXPOSE 5000

CMD ["python", "app.py"]