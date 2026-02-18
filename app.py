import os
from flask import Flask, render_template_string, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import FinanceDataReader as fdr

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
    quantity = db.Column(db.Integer, default=0)
    avg_price = db.Column(db.Float, default=0.0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_current_price(code):
    try:
        df = fdr.DataReader(code)
        if df.empty: return None
        return int(df.iloc[-1]['Close'])
    except: return None

# --- HTML 템플릿 함수 (구조 단순화) ---
def render_layout(content):
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>DevOps 주식 투자</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>body {{ padding-top: 60px; background-color: #f8f9fa; }} .container {{ max-width: 800px; }}</style>
    </head>
    <body>
        <nav class="navbar navbar-dark bg-dark fixed-top px-4">
            <a class="navbar-brand" href="/">📈 DevOps 모의투자</a>
            <div>
                {{% if current_user.is_authenticated %}}
                    <span class="text-white me-3">{{{{ current_user.nickname }}}}님</span>
                    <a href="/logout" class="btn btn-sm btn-danger">로그아웃</a>
                {{% else %}}
                    <a href="/login" class="btn btn-sm btn-primary">로그인</a>
                {{% endif %}}
            </div>
        </nav>
        <div class="container mt-4">
            {{% with messages = get_flashed_messages() %}}
                {{% if messages %}}
                    {{% for msg in messages %}}
                        <div class="alert alert-warning">{{{{ msg }}}}</div>
                    {{% endfor %}}
                {{% endif %}}
            {{% endwith %}}
            
            {content}
            
        </div>
    </body>
    </html>
    """
    return render_template_string(html)

# --- 라우트 (페이지) ---
@app.route('/')
@login_required
def home():
    total_asset = current_user.cash
    stock_rows = ""
    
    for s in current_user.stocks:
        now = get_current_price(s.code) or 0
        val = now * s.quantity
        profit = val - (s.avg_price * s.quantity)
        rate = (profit / (s.avg_price * s.quantity) * 100) if s.quantity > 0 else 0
        color = "text-danger" if profit > 0 else "text-primary"
        
        total_asset += val
        stock_rows += f"""
        <tr>
            <td>{s.code}</td>
            <td>{s.quantity}주</td>
            <td>{int(s.avg_price):,}원</td>
            <td>{now:,}원</td>
            <td>{val:,}원</td>
            <td class="{color}">{rate:.2f}%</td>
        </tr>
        """

    content = f"""
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="card shadow-sm">
                <div class="card-body">
                    <h5 class="card-title">💰 내 자산 총액</h5>
                    <h2 class="card-text text-success">{int(total_asset):,} 원</h2>
                    <p class="text-muted">보유 현금: {int(current_user.cash):,} 원</p>
                </div>
            </div>
        </div>
        <div class="col-md-6">
             <div class="card shadow-sm">
                <div class="card-body">
                    <h5 class="card-title">📉 주식 매매</h5>
                    <form action="/trade" method="post" class="row g-2">
                        <div class="col-4"><input type="text" name="code" class="form-control" placeholder="종목(005930)" required></div>
                        <div class="col-3"><input type="number" name="quantity" class="form-control" placeholder="수량" required></div>
                        <div class="col-3">
                            <select name="action" class="form-select">
                                <option value="buy">매수</option>
                                <option value="sell">매도</option>
                            </select>
                        </div>
                        <div class="col-2"><button class="btn btn-primary w-100">Go</button></div>
                    </form>
                </div>
            </div>
        </div>
    </div>

    <h4>📜 보유 주식</h4>
    <table class="table table-hover bg-white shadow-sm rounded">
        <thead class="table-light"><tr><th>종목</th><th>수량</th><th>평단가</th><th>현재가</th><th>평가금액</th><th>수익률</th></tr></thead>
        <tbody>{stock_rows}</tbody>
    </table>
    """
    return render_layout(content)

@app.route('/trade', methods=['POST'])
@login_required
def trade():
    code = request.form.get('code')
    qty = int(request.form.get('quantity'))
    act = request.form.get('action')
    price = get_current_price(code)
    
    if not price:
        flash("가격을 불러올 수 없습니다. 종목 코드를 확인하세요.")
        return redirect('/')

    cost = price * qty
    stock = Stock.query.filter_by(user_id=current_user.id, code=code).first()

    if act == 'buy':
        if current_user.cash >= cost:
            current_user.cash -= cost
            if stock:
                total_val = (stock.quantity * stock.avg_price) + cost
                stock.quantity += qty
                stock.avg_price = total_val / stock.quantity
            else:
                db.session.add(Stock(user_id=current_user.id, code=code, quantity=qty, avg_price=price))
            flash(f"매수 체결! ({qty}주)")
        else: flash("잔액이 부족합니다.")
    
    elif act == 'sell':
        if stock and stock.quantity >= qty:
            current_user.cash += cost
            stock.quantity -= qty
            if stock.quantity == 0: db.session.delete(stock)
            flash(f"매도 체결! (+{cost:,}원)")
        else: flash("주식이 부족합니다.")
        
    db.session.commit()
    return redirect('/')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect('/')
        flash("아이디 또는 비밀번호가 틀렸습니다.")
    
    content = """
    <div class="row justify-content-center mt-5">
        <div class="col-md-5">
            <div class="card shadow">
                <div class="card-header bg-primary text-white"><h4>로그인</h4></div>
                <div class="card-body">
                    <form method="post">
                        <div class="mb-3">
                            <label>아이디</label>
                            <input type="text" name="username" class="form-control" required>
                        </div>
                        <div class="mb-3">
                            <label>비밀번호</label>
                            <input type="password" name="password" class="form-control" required>
                        </div>
                        <button class="btn btn-primary w-100">로그인</button>
                    </form>
                    <div class="mt-3 text-center">
                        <a href="/register">계정이 없으신가요? 회원가입</a>
                    </div>
                </div>
            </div>
        </div>
    </div>
    """
    return render_layout(content)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            pw_hash = generate_password_hash(request.form.get('password'))
            user = User(username=request.form.get('username'), password_hash=pw_hash, nickname=request.form.get('nickname'))
            db.session.add(user)
            db.session.commit()
            return redirect('/login')
        except: flash("이미 존재하는 아이디입니다.")
            
    content = """
    <div class="row justify-content-center mt-5">
        <div class="col-md-5">
            <div class="card shadow">
                <div class="card-header bg-success text-white"><h4>회원가입 (지원금 100만원)</h4></div>
                <div class="card-body">
                    <form method="post">
                        <div class="mb-3"><input type="text" name="username" class="form-control" placeholder="아이디" required></div>
                        <div class="mb-3"><input type="password" name="password" class="form-control" placeholder="비밀번호" required></div>
                        <div class="mb-3"><input type="text" name="nickname" class="form-control" placeholder="닉네임" required></div>
                        <button class="btn btn-success w-100">가입 완료</button>
                    </form>
                </div>
            </div>
        </div>
    </div>
    """
    return render_layout(content)

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/login')

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)