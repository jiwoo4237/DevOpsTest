FROM python:3.10-slim

WORKDIR /app

# 1. OS 패키지 업데이트
RUN apt-get update && apt-get upgrade -y && \
    rm -rf /var/lib/apt/lists/*

# 2. pip 자체를 최신 버전으로 업데이트 (23.0.1의 취약점 회피)
# --upgrade pip를 먼저 실행하여 최신 보안 패치가 적용된 pip를 확보합니다.
RUN python -m pip install --upgrade pip

# 3. setuptools 및 기타 도구 설치
RUN pip install setuptools==78.1.1 wheel

# 4. 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]