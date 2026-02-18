import os
import json
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devops-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- DB 모델 ---
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(100), nullable=False)
    cash = db.Column(db.Float, default=1000000.0)
    stocks = db.relationship('Stock', backref='owner', lazy=True)

class Stock(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code = db.Column(db.String(20), nullable=False)
    name = db.Column(db.String(100), default="Unknown") # 종목명 추가
    quantity = db.Column(db.Integer, default=0)
    avg_price = db.Column(db.Float, default=0.0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- 주식 데이터 유틸리티 ---
def get_kospi_top30():
    """코스피 시가총액 상위 30개를 가져옵니다."""
    try:
        # KRX 상장종목 전체 가져오기 (시간이 좀 걸림, 실제 서비스에선 캐싱 필요)
        df = fdr.StockListing('KOSPI')
        top30 = df.head(30)[['Code', 'Name', 'Marcap', 'Close', 'ChagesRatio']]
        return top30.to_dict(orient='records')
    except:
        return []

def get_stock_history(code):
    """최근 3달치 주가 데이터를 가져옵니다 (차트용)."""
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        df = fdr.DataReader(code, start_date, end_date)
        # 날짜(index)를 문자열로 변환
        data = {
            'labels': [date.strftime('%Y-%m-%d') for date in df.index],
            'prices': df['Close'].tolist()
        }
        return data
    except:
        return {'labels': [], 'prices': []}

# --- HTML 템플릿 (차트 라이브러리 추가됨) ---
base_html = """
<!DOCTYPE html>
<html>
<head>
    <title>DevOps Pro Trade</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { padding-top: 60px; background-color: #1e1e2f; color: #e0e0e0; }
        .card { background-color: #27293d; border: none; margin-bottom: 20px; }
        .table { color: #e0e0e0; }
        .form-control, .form-select { background-color: #1e1e2f; border: 1px solid #2b3553; color: white; }
        .list-group-item { background-color: #27293d; color: white; border: 1px solid #2b3553; cursor: pointer; }
        .list-group-item:hover { background-color: #3e3e5e; }
        .nav-link { color: white; }
    </style>
</head>
<body>
    <nav class="navbar navbar-dark bg-dark fixed-top px-4 border-bottom border-secondary">
        <a class="navbar-brand text-warning" href="/">⚡ DevOps Trader</a>
        <div>
            {% if current_user.is_authenticated %}
                <span class="me-3">{{ current_user.nickname }}님 | 잔액: <span class="text-success fw-bold">{{ "{:,}".format(current_user.cash|int) }}원</span></span>
                <a href="/logout" class="btn btn-sm btn-outline-danger">로그아웃</a>
            {% else %}
                <a href="/login" class="btn btn-sm btn-primary">로그인</a>
            {% endif %}
        </div>
    </nav>
    <div class="container-fluid mt-3">
        {% with messages = get_flashed_messages() %}
            {% if messages %}<div class="alert alert-info">{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        
        </div>
    
    <script>
        // 차트 그리기 함수
        let myChart = null;

        async function loadStock(code, name) {
            // 1. 입력창에 종목 코드 자동 입력
            document.getElementById('inputCode').value = code;
            document.getElementById('stockTitle').innerText = name + " (" + code + ")";
            
            // 2. 서버에서 차트 데이터 가져오기 (AJAX)
            const response = await fetch('/api/chart/' + code);
            const data = await response.json();
            
            // 3. 차트 업데이트
            const ctx = document.getElementById('stockChart').getContext('2d');
            
            if (myChart) { myChart.destroy(); } // 기존 차트 삭제

            myChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: data.labels,
                    datasets: [{
                        label: name + ' 주가',
                        data: data.prices,
                        borderColor: '#00d6b4',
                        backgroundColor: 'rgba(0, 214, 180, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4
                    }]
                },
                options: {
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { color: '#2b3553' } },
                        y: { grid: { color: '#2b3553' } }
                    }
                }
            });
        }
    </script>
</body>
</html>
"""

def render_layout(content, **kwargs):
    return render_template_string(base_html.replace('', content), **kwargs)

# --- 라우트 ---
@app.route('/')
@login_required
def home():
    # 1. 왼쪽 사이드바용 상위 종목 리스트 가져오기
    top_stocks = get_kospi_top30()
    
    # 2. 내 보유 주식 계산
    total_asset = current_user.cash
    my_stocks_html = ""
    for s in current_user.stocks:
        # 간단하게 현재가는 마지막 종가로 가정 (실시간 API 제한 때문)
        # 실제로는 여기서도 fdr.DataReader로 현재가 호출해야 함
        try:
            df = fdr.DataReader(s.code)
            now_price = int(df.iloc[-1]['Close'])
        except:
            now_price = 0
            
        val = now_price * s.quantity
        total_asset += val
        profit = val - (s.avg_price * s.quantity)
        color = "text-danger" if profit > 0 else "text-primary"
        my_stocks_html += f"<tr><td>{s.name}</td><td>{s.quantity}</td><td>{int(s.avg_price):,}</td><td>{now_price:,}</td><td class='{color}'>{int(profit):,}</td></tr>"

    # 3. HTML 조립 (좌: 리스트, 우: 차트 및 주문)
    stock_list_items = ""
    for stock in top_stocks:
        change_color = "text-danger" if stock['ChagesRatio'] > 0 else "text-primary"
        stock_list_items += f"""
        <li class="list-group-item d-flex justify-content-between align-items-center" onclick="loadStock('{stock['Code']}', '{stock['Name']}')">
            <span>{stock['Name']}</span>
            <span class="{change_color}">{stock['Close']:,}원</span>
        </li>
        """

    content = f"""
    <div class="row">
        <div class="col-md-3">
            <h5 class="text-muted">🏆 KOSPI Top 30</h5>
            <div style="height: 80vh; overflow-y: scroll;">
                <ul class="list-group">
                    {stock_list_items}
                </ul>
            </div>
        </div>

        <div class="col-md-9">
            <div class="card p-3">
                <h3 id="stockTitle">종목을 선택하세요</h3>
                <canvas id="stockChart" height="100"></canvas>
            </div>

            <div class="row">
                <div class="col-md-6">
                    <div class="card p-3">
                        <h5>⚡ 빠른 주문</h5>
                        <form action="/trade" method="post">
                            <input type="hidden" id="stockName" name="name" value="">
                            <div class="mb-2">
                                <label>종목코드</label>
                                <input type="text" id="inputCode" name="code" class="form-control" readonly required>
                            </div>
                            <div class="mb-2">
                                <label>수량</label>
                                <input type="number" name="quantity" class="form-control" placeholder="몇 주?" required>
                            </div>
                            <div class="row g-2">
                                <div class="col"><button name="action" value="buy" class="btn btn-danger w-100">매수 (Buy)</button></div>
                                <div class="col"><button name="action" value="sell" class="btn btn-primary w-100">매도 (Sell)</button></div>
                            </div>
                        </form>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card p-3">
                        <h5>💰 내 자산: {int(total_asset):,}원</h5>
                        <table class="table table-sm" style="font-size: 0.9em;">
                            <thead><tr><th>종목</th><th>수량</th><th>평단</th><th>현재가</th><th>손익</th></tr></thead>
                            <tbody>{my_stocks_html}</tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return render_layout(content)

# --- 차트 데이터 API (JSON 반환) ---
@app.route('/api/chart/<code>')
def chart_api(code):
    data = get_stock_history(code)
    return jsonify(data)

@app.route('/trade', methods=['POST'])
@login_required
def trade():
    code = request.form.get('code')
    qty = int(request.form.get('quantity'))
    action = request.form.get('action')
    
    # 종목명 찾기 (DB 없으면 API 호출)
    try:
        df = fdr.DataReader(code)
        price = int(df.iloc[-1]['Close'])
        # 간단히 날짜 인덱스로 이름 찾는건 안되니, 그냥 코드로 저장하거나 리스트에서 넘겨받아야 함.
        # 여기선 편의상 기존 리스트 클릭 시 JS가 넘겨주도록 하거나 생략.
        name = code # 임시
    except:
        flash("종목 정보를 불러올 수 없습니다.")
        return redirect('/')

    cost = price * qty
    stock = Stock.query.filter_by(user_id=current_user.id, code=code).first()

    if action == 'buy':
        if current_user.cash >= cost:
            current_user.cash -= cost
            if stock:
                total_val = (stock.quantity * stock.avg_price) + cost
                stock.quantity += qty
                stock.avg_price = total_val / stock.quantity
            else:
                db.session.add(Stock(user_id=current_user.id, code=code, name=name, quantity=qty, avg_price=price))
            flash(f"매수 체결 완료!")
        else: flash("잔액이 부족합니다.")
    
    elif action == 'sell':
        if stock and stock.quantity >= qty:
            current_user.cash += cost
            stock.quantity -= qty
            if stock.quantity == 0: db.session.delete(stock)
            flash(f"매도 체결 완료!")
        else: flash("주식이 부족합니다.")
        
    db.session.commit()
    return redirect('/')

# --- 로그인/회원가입 (기존 유지) ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect('/')
        flash("로그인 실패")
    
    # 로그인 화면 디자인 살짝 수정
    return render_layout("""
    <div class="row justify-content-center" style="margin-top: 100px;">
        <div class="col-md-4">
            <div class="card p-4">
                <h3 class="text-center mb-4">🔐 Trade Login</h3>
                <form method="post">
                    <input type="text" name="username" class="form-control mb-3" placeholder="ID" required>
                    <input type="password" name="password" class="form-control mb-3" placeholder="Password" required>
                    <button class="btn btn-info w-100">로그인</button>
                </form>
                <div class="text-center mt-3"><a href="/register" class="text-white">회원가입</a></div>
            </div>
        </div>
    </div>
    """)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            pw = generate_password_hash(request.form.get('password'))
            user = User(username=request.form.get('username'), password_hash=pw, nickname=request.form.get('nickname'))
            db.session.add(user)
            db.session.commit()
            return redirect('/login')
        except: flash("ID 중복")
    return render_layout("""
    <div class="row justify-content-center" style="margin-top: 100px;">
        <div class="col-md-4 card p-4">
            <h3 class="text-center">회원가입</h3>
            <form method="post">
                <input name="username" class="form-control mb-2" placeholder="ID">
                <input name="password" type="password" class="form-control mb-2" placeholder="PW">
                <input name="nickname" class="form-control mb-2" placeholder="Nickname">
                <button class="btn btn-success w-100">가입</button>
            </form>
        </div>
    </div>
    """)

@app.route('/logout')
def logout(): logout_user(); return redirect('/login')

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)