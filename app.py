import os
from datetime import datetime
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import FinanceDataReader as fdr

# ==========================================
# 1. 설정 및 초기화
# ==========================================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'devops-secret-key-1234'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock_simulation.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==========================================
# 2. 데이터베이스 모델
# ==========================================
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
    quantity = db.Column(db.Integer, default=0)
    avg_price = db.Column(db.Float, default=0.0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# 3. 주식 데이터 유틸리티
# ==========================================
def get_current_price(code):
    try:
        df = fdr.DataReader(code)
        if df.empty:
            return None
        return int(df.iloc[-1]['Close'])
    except:
        return None

# ==========================================
# 4. HTML 템플릿 (수정됨: PLACEHOLDER 사용)
# ==========================================
base_html = """
<!DOCTYPE html>
<html>
<head>
    <title>DevOps 주식 투자</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>body { padding-top: 50px; } .container { max-width: 800px; }</style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark fixed-top">
        <div class="container">
            <a class="navbar-brand" href="/">📈 모의 투자</a>
            <div class="collapse navbar-collapse">
                <ul class="navbar-nav ms-auto">
                    {% if current_user.is_authenticated %}
                        <li class="nav-item"><a class="nav-link" href="/">내 자산</a></li>
                        <li class="nav-item"><a class="nav-link" href="/ranking">🏆 랭킹</a></li>
                        <li class="nav-item"><a class="nav-link" href="/logout">로그아웃 ({{ current_user.nickname }})</a></li>
                    {% else %}
                        <li class="nav-item"><a class="nav-link" href="/login">로그인</a></li>
                        <li class="nav-item"><a class="nav-link" href="/register">회원가입</a></li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </nav>
    <div class="container mt-4">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for message in messages %}
                    <div class="alert alert-info">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        </div>
</body>
</html>
"""

# HTML 끼워넣기 헬퍼 함수
def render_page(content, **kwargs):
    # base_html의 플레이스홀더를 실제 컨텐츠로 교체
    full_html = base_html.replace('', content)
    return render_template_string(full_html, **kwargs)

# ==========================================
# 5. 라우트 및 비즈니스 로직
# ==========================================

@app.route('/')
@login_required
def home():
    total_asset = current_user.cash
    portfolio = []
    
    for stock in current_user.stocks:
        current_price = get_current_price(stock.code)
        if current_price:
            valuation = current_price * stock.quantity
            profit = valuation - (stock.avg_price * stock.quantity)
            profit_rate = (profit / (stock.avg_price * stock.quantity)) * 100 if stock.quantity > 0 else 0
            
            portfolio.append({
                'code': stock.code,
                'quantity': stock.quantity,
                'avg_price': stock.avg_price,
                'current_price': current_price,
                'valuation': valuation,
                'profit': profit,
                'profit_rate': round(profit_rate, 2)
            })
            total_asset += valuation
        else:
            portfolio.append({'code': stock.code, 'current_price': 0, 'valuation': 0, 'profit': 0, 'profit_rate': 0})

    content = """
        <h2>💰 {{ current_user.nickname }}님의 자산 현황</h2>
        <div class="card mb-4">
            <div class="card-body">
                <h4>총 자산: {{ "{:,}".format(total_asset|int) }} 원</h4>
                <p>보유 현금: {{ "{:,}".format(current_user.cash|int) }} 원</p>
            </div>
        </div>

        <h3>📉 거래하기</h3>
        <form action="/trade" method="post" class="row g-3 mb-4">
            <div class="col-auto"><input type="text" name="code" class="form-control" placeholder="종목코드 (예: 005930)" required></div>
            <div class="col-auto"><input type="number" name="quantity" class="form-control" placeholder="수량" min="1" required></div>
            <div class="col-auto">
                <select name="action" class="form-select">
                    <option value="buy">매수 (사기)</option>
                    <option value="sell">매도 (팔기)</option>
                </select>
            </div>
            <div class="col-auto"><button type="submit" class="btn btn-primary">주문 실행</button></div>
        </form>

        <h3>📜 보유 주식 목록</h3>
        <table class="table">
            <thead><tr><th>종목코드</th><th>수량</th><th>평단가</th><th>현재가</th><th>평가금액</th><th>수익률</th></tr></thead>
            <tbody>
                {% for p in portfolio %}
                <tr>
                    <td>{{ p.code }}</td>
                    <td>{{ p.quantity }}</td>
                    <td>{{ "{:,}".format(p.avg_price|int) }}</td>
                    <td>{{ "{:,}".format(p.current_price) }}</td>
                    <td>{{ "{:,}".format(p.valuation) }}</td>
                    <td class="{{ 'text-danger' if p.profit > 0 else 'text-primary' }}">
                        {{ p.profit_rate }}%
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    """
    return render_page(content, total_asset=total_asset, portfolio=portfolio)

@app.route('/trade', methods=['POST'])
@login_required
def trade():
    code = request.form.get('code')
    quantity = int(request.form.get('quantity'))
    action = request.form.get('action')
    
    current_price = get_current_price(code)
    
    if not current_price:
        flash("존재하지 않는 종목 코드거나 데이터를 가져올 수 없습니다.")
        return redirect(url_for('home'))

    total_price = current_price * quantity
    stock = Stock.query.filter_by(user_id=current_user.id, code=code).first()

    if action == 'buy':
        if current_user.cash >= total_price:
            current_user.cash -= total_price
            if stock:
                total_cost = (stock.quantity * stock.avg_price) + total_price
                stock.quantity += quantity
                stock.avg_price = total_cost / stock.quantity
            else:
                new_stock = Stock(user_id=current_user.id, code=code, quantity=quantity, avg_price=current_price)
                db.session.add(new_stock)
            flash(f"{code} {quantity}주 매수 성공!")
        else:
            flash("잔액이 부족합니다.")

    elif action == 'sell':
        if stock and stock.quantity >= quantity:
            current_user.cash += total_price
            stock.quantity -= quantity
            if stock.quantity == 0:
                db.session.delete(stock)
            flash(f"{code} {quantity}주 매도 성공! (+{total_price}원)")
        else:
            flash("보유 수량이 부족합니다.")

    db.session.commit()
    return redirect(url_for('home'))

@app.route('/ranking')
def ranking():
    users = User.query.all()
    rank_list = []
    
    for user in users:
        total_val = user.cash
        for stock in user.stocks:
            price = get_current_price(stock.code)
            if price:
                total_val += (price * stock.quantity)
        rank_list.append({'nickname': user.nickname, 'asset': total_val})
    
    rank_list.sort(key=lambda x: x['asset'], reverse=True)
    
    content = """
        <h2>🏆 투자 랭킹</h2>
        <table class="table table-striped">
            <thead><tr><th>순위</th><th>닉네임</th><th>총 자산</th></tr></thead>
            <tbody>
                {% for r in rank_list %}
                <tr>
                    <td>{{ loop.index }}위</td>
                    <td>{{ r.nickname }}</td>
                    <td>{{ "{:,}".format(r.asset|int) }} 원</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    """
    return render_page(content, rank_list=rank_list)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        nickname = request.form.get('nickname')
        
        if User.query.filter_by(username=username).first():
            flash('이미 존재하는 아이디입니다.')
        else:
            hashed_pw = generate_password_hash(password, method='scrypt')
            new_user = User(username=username, password_hash=hashed_pw, nickname=nickname)
            db.session.add(new_user)
            db.session.commit()
            return redirect(url_for('login'))
            
    content = """
        <h2>회원가입</h2>
        <form method="post">
            <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="아이디" required></div>
            <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="비밀번호" required></div>
            <div class="mb-3"><input type="text" name="nickname" class="form-control" placeholder="닉네임" required></div>
            <button type="submit" class="btn btn-success">가입하기 (초기자금 100만원 지급)</button>
        </form>
    """
    return render_page(content)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('아이디 또는 비밀번호가 틀렸습니다.')
            
    content = """
        <h2>로그인</h2>
        <form method="post">
            <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="아이디" required></div>
            <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="비밀번호" required></div>
            <button type="submit" class="btn btn-primary">로그인</button>
        </form>
    """
    return render_page(content)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)