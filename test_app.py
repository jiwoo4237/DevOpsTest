import pytest
from app import app, db

@pytest.fixture
def client():
    # 테스트용 설정 (실제 DB 대신 메모리 DB 사용)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()  # 테스트용 가짜 테이블 생성
        
    with app.test_client() as client:
        yield client

def test_login_page_loads(client):
    """로그인 페이지가 정상적으로(200 OK) 열리는지 테스트"""
    response = client.get('/login')
    
    # 1. 상태 코드가 200(성공)이어야 함
    assert response.status_code == 200
    
    # 2. HTML 내용 중에 '로그인'이라는 단어가 포함되어 있어야 함
    # (HTML은 bytes로 오기 때문에 encode로 변환해서 비교)
    assert '로그인'.encode('utf-8') in response.data

def test_root_redirects_to_login(client):
    """로그인 안 한 상태로 홈(/) 접속 시 로그인 페이지로 튕기는지(302) 테스트"""
    response = client.get('/')
    
    # 302: 리다이렉트 (다른 페이지로 이동) 상태 코드
    assert response.status_code == 302