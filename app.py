import os
import json
from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import FinanceDataReader as fdr
from datetime import datetime, timedelta

app = Flask(__name__)
app.config['SECRET_KEY'] = 'devops-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///stock.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# ==========================================
# 1. 초기 데이터 로드 (종목코드 -> 종목명)
# ==========================================
print("📈 한국거래소(KRX) 종목 데이터를 불러오는 중... (약 2~3초 소요)")
try:
    krx_df = fdr.StockListing('KRX')
    STOCK_DICT = dict(zip(krx_df['Code'], krx_df['Name']))
    print(f"✅ 총 {len(STOCK_DICT)}개의 종목 로드 완료!")
except Exception as e:
    print("⚠️ 종목 데이터를 불러오지 못했습니다.", e)
    STOCK_DICT = {}

def get_stock_name(code):
    return STOCK_DICT.get(code, "알수없는종목")

# ==========================================
# 2. DB 모델
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
    name = db.Column(db.String(100), default="Unknown")
    quantity = db.Column(db.Integer, default=0)
    avg_price = db.Column(db.Float, default=0.0)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# 3. 주식 데이터 유틸리티 (랭킹을 위한 캐싱 포함)
# ==========================================
def get_kospi_top30():
    try:
        df = fdr.StockListing('KOSPI')
        return df.head(30)[['Code', 'Name', 'Marcap', 'Close', 'ChagesRatio']].to_dict(orient='records')
    except:
        return []

def get_stock_history(code):
    try:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        df = fdr.DataReader(code, start_date, end_date)
        return {
            'labels': [date.strftime('%Y-%m-%d') for date in df.index],
            'prices': df['Close'].tolist()
        }
    except:
        return {'labels': [], 'prices': []}

def get_current_price_cached(code, cache_dict):
    """서버 부하 방지를 위해 한 번 조회한 가격은 저장해두고 씀"""
    if code in cache_dict:
        return cache_dict[code]
    try:
        df = fdr.DataReader(code)
        price = int(df.iloc[-1]['Close'])
        cache_dict[code] = price
        return price
    except:
        cache_dict[code] = 0
        return 0

# ==========================================
# 4. 통합 HTML 템플릿
# ==========================================
base_html = """
<!DOCTYPE html>
<html>
<head>
    <title>DevOps Pro Trade</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body { padding-top: 70px; background-color: #1e1e2f; color: #e0e0e0; font-family: 'Noto Sans KR', sans-serif;}
        .card { background-color: #27293d; border: none; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
        .table { color: #e0e0e0; vertical-align: middle; }
        .form-control, .form-select { background-color: #1e1e2f; border: 1px solid #2b3553; color: white; }
        .form-control:focus, .form-select:focus { background-color: #1e1e2f; color: white; border-color: #00d6b4; box-shadow: none; }
        .nav-link { color: #aaa !important; font-weight: bold; }
        .nav-link.active, .nav-link:hover { color: #fff !important; }
        
        /* 원형 타이머 CSS */
        .circular-chart { display: block; width: 36px; height: 36px; }
        .circle-bg { fill: none; stroke: #3e3e5e; stroke-width: 3; }
        .circle { fill: none; stroke-width: 3; stroke-linecap: round; transition: stroke-dasharray 1s linear; }
        .timer-text { fill: white; font-size: 11px; font-weight: bold; text-anchor: middle; }
        
        /* 랭킹 리스트 CSS */
        .rank-item { background-color: transparent; border-bottom: 1px solid #3e3e5e; color: #e0e0e0; }
        .rank-item:last-child { border-bottom: none; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand navbar-dark bg-dark fixed-top px-4 border-bottom border-secondary">
        <a class="navbar-brand text-warning fw-bold" href="/">⚡ DevOps Trader</a>
        <ul class="navbar-nav me-auto">
            <li class="nav-item"><a class="nav-link" href="/">내 자산</a></li>
            <li class="nav-item"><a class="nav-link" href="/board">📊 차트 게시판</a></li>
        </ul>
        <div class="d-flex align-items-center">
            <div class="d-flex align-items-center me-4">
                <span class="me-2 text-muted" style="font-size: 0.8rem;">데이터 갱신</span>
                <svg viewBox="0 0 36 36" class="circular-chart">
                  <path class="circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                  <path class="circle" id="timerCircle" stroke="#00d6b4" stroke-dasharray="100, 100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" />
                  <text x="18" y="22" class="timer-text" id="timerText">30</text>
                </svg>
            </div>
            {% if current_user.is_authenticated %}
                <span class="me-3 text-light">{{ current_user.nickname }}님 | <span class="text-success fw-bold">{{ "{:,}".format(current_user.cash|int) }}원</span></span>
                <a href="/logout" class="btn btn-sm btn-outline-danger">로그아웃</a>
            {% else %}
                <a href="/login" class="btn btn-sm btn-primary">로그인</a>
            {% endif %}
        </div>
    </nav>

    <div class="container-fluid mt-2">
        {% with messages = get_flashed_messages() %}
            {% if messages %}<div class="alert alert-info alert-dismissible"><button type="button" class="btn-close" data-bs-dismiss="alert"></button>{{ messages[0] }}</div>{% endif %}
        {% endwith %}
        </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 원형 타이머 스크립트
        let maxTime = 30;
        let time = maxTime;
        
        setInterval(() => {
            const isInputFocused = document.activeElement.tagName === 'INPUT';
            const isModalOpen = document.querySelector('.modal.show') !== null;
            
            if (isInputFocused || isModalOpen) {
                time = 10; 
            } else {
                time--;
                if (time <= 0) window.location.reload();
                else {
                    document.getElementById('timerText').textContent = time;
                    let strokeDash = (time / maxTime) * 100;
                    document.getElementById('timerCircle').setAttribute('stroke-dasharray', `${strokeDash}, 100`);
                }
            }
        }, 1000);
    </script>
</body>
</html>
"""

def render_layout(content, **kwargs):
    return render_template_string(base_html.replace('', content), **kwargs)

# ==========================================
# 5. 라우트 및 로직
# ==========================================

@app.route('/')
@login_required
def home():
    """메인 대시보드 (3단 구성: 내 자산, 포트폴리오, 랭킹)"""
    price_cache = {} # 서버 속도 저하 방지용 캐시 딕셔너리
    
    # ---------------------------
    # 1. 내 자산 및 포트폴리오 계산
    # ---------------------------
    total_asset = current_user.cash
    my_stocks_html = ""
    
    for s in current_user.stocks:
        now_price = get_current_price_cached(s.code, price_cache)
        val = now_price * s.quantity
        total_asset += val
        profit = val - (s.avg_price * s.quantity)
        rate = (profit / (s.avg_price * s.quantity) * 100) if s.quantity > 0 else 0
        color = "text-danger" if profit > 0 else "text-primary"
        
        my_stocks_html += f"""
        <tr>
            <td class="text-start">
                <span class="fs-6 fw-bold text-white">{s.name}</span><br>
                <span class="text-muted" style="font-size: 0.8em;">{s.code}</span>
            </td>
            <td>{s.quantity}주</td>
            <td>{int(s.avg_price):,}원<br><span class="text-muted" style="font-size:0.85em;">현재: {now_price:,}원</span></td>
            <td>{val:,}원</td>
            <td class="{color} fw-bold">{int(profit):,}원<br><small>({rate:.2f}%)</small></td>
        </tr>
        """

    # ---------------------------
    # 2. 전체 유저 실시간 랭킹 계산
    # ---------------------------
    users = User.query.all()
    ranking_data = []
    
    for u in users:
        u_total = u.cash
        for s in u.stocks:
            p = get_current_price_cached(s.code, price_cache)
            u_total += (p * s.quantity)
        ranking_data.append({'nickname': u.nickname, 'asset': u_total})
        
    # 총 자산 기준으로 내림차순 정렬
    ranking_data.sort(key=lambda x: x['asset'], reverse=True)
    
    ranking_html = ""
    for idx, rank in enumerate(ranking_data[:10]): # 상위 10명만 표시
        medal = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"<span class='badge bg-secondary'>{idx+1}</span>"
        highlight = "bg-primary bg-opacity-25" if rank['nickname'] == current_user.nickname else ""
        
        ranking_html += f"""
        <li class="list-group-item d-flex justify-content-between align-items-center rank-item {highlight} p-3">
            <span class="fs-6">{medal} <span class="ms-2 fw-bold">{rank['nickname']}</span></span>
            <span class="text-success fw-bold">{int(rank['asset']):,}원</span>
        </li>
        """

    # ---------------------------
    # 3. HTML 조립 (3단 레이아웃)
    # ---------------------------
    content = f"""
    <div class="row px-2">
        <div class="col-lg-3 col-md-12 mb-4">
            <div class="card p-4">
                <h6 class="text-muted mb-3">💰 총 보유 자산</h6>
                <h2 class="text-success fw-bold">{int(total_asset):,} 원</h2>
                <hr class="border-secondary">
                <div class="d-flex justify-content-between text-light">
                    <span>주문 가능 현금</span>
                    <span>{int(current_user.cash):,} 원</span>
                </div>
            </div>
            
            <div class="card p-4 mt-3 border border-warning">
                <h5 class="text-warning mb-3">⚡ 빠른 주문</h5>
                <form action="/trade" method="post">
                    <div class="mb-2"><input type="text" name="code" class="form-control" placeholder="종목코드 (예: 005930)" required></div>
                    <div class="mb-3"><input type="number" name="quantity" class="form-control" placeholder="주문 수량" required></div>
                    <div class="row g-2">
                        <div class="col"><button name="action" value="buy" class="btn btn-danger w-100 fw-bold">매수</button></div>
                        <div class="col"><button name="action" value="sell" class="btn btn-primary w-100 fw-bold">매도</button></div>
                    </div>
                </form>
            </div>
        </div>

        <div class="col-lg-6 col-md-12 mb-4">
            <h4 class="mb-3">📜 내 포트폴리오</h4>
            <div class="card p-0 overflow-hidden">
                <table class="table table-hover mb-0 text-center" style="font-size: 0.95rem;">
                    <thead class="table-dark text-muted">
                        <tr><th class="text-start">종목</th><th>수량</th><th>평단가</th><th>평가금액</th><th>손익/수익률</th></tr>
                    </thead>
                    <tbody>{my_stocks_html or "<tr><td colspan='5' class='py-5 text-muted'>보유한 주식이 없습니다.<br>게시판에서 차트를 보고 매수해보세요!</td></tr>"}</tbody>
                </table>
            </div>
        </div>
        
        <div class="col-lg-3 col-md-12 mb-4">
            <h4 class="mb-3 text-info">🏆 실시간 자산 랭킹</h4>
            <div class="card p-0 overflow-hidden border border-info">
                <div class="card-header bg-info text-dark fw-bold text-center p-3 fs-5">
                    Top 10 트레이더
                </div>
                <ul class="list-group list-group-flush">
                    {ranking_html}
                </ul>
            </div>
        </div>
    </div>
    """
    return render_layout(content)

@app.route('/board')
@login_required
def board():
    top_stocks = get_kospi_top30()
    cards_html = ""
    for s in top_stocks:
        color = "text-danger" if s['ChagesRatio'] > 0 else "text-primary"
        cards_html += f"""
        <div class="col-xl-3 col-lg-4 col-md-6 mb-4">
            <div class="card h-100 p-3" style="cursor: pointer; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'" onclick="openChartModal('{s['Code']}', '{s['Name']}')">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 class="text-white mb-0 text-truncate" style="max-width: 70%;">{s['Name']}</h5>
                    <span class="badge bg-secondary">{s['Code']}</span>
                </div>
                <h3 class="fw-bold {color}">{int(s['Close']):,}원</h3>
                <p class="mb-0 {color} fw-bold">{(s['ChagesRatio']):.2f}%</p>
            </div>
        </div>
        """

    content = f"""
    <div class="px-3">
        <h3 class="mb-4">📊 KOSPI 차트 게시판 <small class="text-muted fs-6">카드를 클릭하여 차트를 확인하세요.</small></h3>
        <div class="row">{cards_html}</div>
    </div>

    <div class="modal fade" id="chartModal" tabindex="-1">
      <div class="modal-dialog modal-lg modal-dialog-centered">
        <div class="modal-content bg-dark text-light border border-secondary">
          <div class="modal-header border-bottom border-secondary">
            <h4 class="modal-title fw-bold" id="modalTitle">종목명</h4>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body p-4">
            <div class="mb-4 bg-secondary bg-opacity-10 p-2 rounded"><canvas id="modalChart" height="100"></canvas></div>
            <form action="/trade" method="post" class="row g-2 align-items-end">
                <input type="hidden" name="code" id="modalCode">
                <div class="col-md-6">
                    <label class="form-label text-muted">주문 수량</label>
                    <input type="number" name="quantity" class="form-control form-control-lg" required>
                </div>
                <div class="col-md-3"><button name="action" value="buy" class="btn btn-danger btn-lg w-100 fw-bold">매수</button></div>
                <div class="col-md-3"><button name="action" value="sell" class="btn btn-primary btn-lg w-100 fw-bold">매도</button></div>
            </form>
          </div>
        </div>
      </div>
    </div>

    <script>
        let myChart = null;
        async function openChartModal(code, name) {{
            document.getElementById('modalTitle').innerText = name + " (" + code + ")";
            document.getElementById('modalCode').value = code;
            new bootstrap.Modal(document.getElementById('chartModal')).show();
            
            const data = await (await fetch('/api/chart/' + code)).json();
            const ctx = document.getElementById('modalChart').getContext('2d');
            if (myChart) myChart.destroy(); 
            myChart = new Chart(ctx, {{
                type: 'line',
                data: {{ labels: data.labels, datasets: [{{ label: name, data: data.prices, borderColor: '#00d6b4', backgroundColor: 'rgba(0,214,180,0.1)', borderWidth: 2, fill: true, tension: 0.3 }}] }},
                options: {{ responsive: true, plugins: {{ legend: {{ labels: {{ color: 'white' }} }} }}, scales: {{ x: {{ grid: {{ color: '#2b3553' }}, ticks: {{ color: '#aaa' }} }}, y: {{ grid: {{ color: '#2b3553' }}, ticks: {{ color: '#aaa' }} }} }} }}
            }});
        }}
    </script>
    """
    return render_layout(content)

@app.route('/api/chart/<code>')
def chart_api(code):
    return jsonify(get_stock_history(code))

@app.route('/trade', methods=['POST'])
@login_required
def trade():
    code = request.form.get('code')
    qty = int(request.form.get('quantity'))
    action = request.form.get('action')
    
    try:
        df = fdr.DataReader(code)
        price = int(df.iloc[-1]['Close'])
        name = get_stock_name(code)
    except:
        flash(f"'{code}' 종목 정보를 불러올 수 없습니다.")
        return redirect(request.referrer or url_for('home'))

    cost = price * qty
    stock = Stock.query.filter_by(user_id=current_user.id, code=code).first()

    if action == 'buy':
        if current_user.cash >= cost:
            current_user.cash -= cost
            if stock:
                total_val = (stock.quantity * stock.avg_price) + cost
                stock.quantity += qty
                stock.avg_price = total_val / stock.quantity
                stock.name = name 
            else:
                db.session.add(Stock(user_id=current_user.id, code=code, name=name, quantity=qty, avg_price=price))
            flash(f"✅ {name}({code}) {qty}주 매수 완료!")
        else: flash("❌ 잔액이 부족합니다.")
    elif action == 'sell':
        if stock and stock.quantity >= qty:
            current_user.cash += cost
            stock.quantity -= qty
            if stock.quantity == 0: db.session.delete(stock)
            flash(f"✅ {name}({code}) {qty}주 매도 완료!")
        else: flash("❌ 보유 수량이 부족합니다.")
        
    db.session.commit()
    return redirect(request.referrer or url_for('home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password_hash, request.form.get('password')):
            login_user(user)
            return redirect('/')
        flash("아이디 또는 비밀번호가 틀렸습니다.")
    return render_layout("""<div class="row justify-content-center" style="margin-top: 10vh;"><div class="col-md-4 card p-4 border border-info"><h3 class="text-center mb-4 text-info fw-bold">로그인</h3><form method="post"><input type="text" name="username" class="form-control mb-3" placeholder="ID" required><input type="password" name="password" class="form-control mb-3" placeholder="Password" required><button class="btn btn-info w-100 fw-bold text-dark">접속하기</button></form><div class="text-center mt-3"><a href="/register" class="text-muted">계정이 없으신가요? 회원가입</a></div></div></div>""")

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            pw = generate_password_hash(request.form.get('password'))
            user = User(username=request.form.get('username'), password_hash=pw, nickname=request.form.get('nickname'))
            db.session.add(user)
            db.session.commit()
            return redirect('/login')
        except: flash("이미 존재하는 아이디입니다.")
    return render_layout("""<div class="row justify-content-center" style="margin-top: 10vh;"><div class="col-md-4 card p-4 border border-success"><h3 class="text-center mb-4 text-success fw-bold">회원가입</h3><p class="text-center text-muted">가입 시 축하금 1,000,000원이 지급됩니다.</p><form method="post"><input name="username" class="form-control mb-2" placeholder="ID" required><input name="password" type="password" class="form-control mb-2" placeholder="PW" required><input name="nickname" class="form-control mb-3" placeholder="닉네임 (게시판 노출용)" required><button class="btn btn-success w-100 fw-bold">가입하기</button></form></div></div>""")

@app.route('/logout')
def logout(): logout_user(); return redirect('/login')

if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(host='0.0.0.0', port=5000)