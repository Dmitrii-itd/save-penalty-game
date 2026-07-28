import json
import random
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-in-production'

daily_track = []
last_track_date = None
user_balance = {}
attempts_today = {}

BASE_PRICE = 100
PRIZES = {5: 316, 4: 134, 3: 60, 2: 0, 1: 0, 0: 0}
REACTION_WINDOW_MS = 400  # настройка сложности
MIN_REACTION_TIME = 100

def generate_daily_track():
    track = []
    for _ in range(5):
        sector = random.randint(0, 8)
        track.append({
            "sector": sector,
            "prompt_time": random.uniform(0.5, 1.5)
        })
    return track

def get_track():
    global daily_track, last_track_date
    today = datetime.now().date()
    if last_track_date != today:
        daily_track = generate_daily_track()
        last_track_date = today
    return daily_track

@app.before_request
def init_session():
    if 'user_id' not in session:
        session['user_id'] = f"user_{random.randint(1000, 9999)}"
    uid = session['user_id']
    if uid not in user_balance:
        user_balance[uid] = 0
    if uid not in attempts_today:
        attempts_today[uid] = 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/balance', methods=['GET'])
def get_balance():
    uid = session['user_id']
    return jsonify({"balance": user_balance[uid]})

@app.route('/api/deposit', methods=['POST'])
def deposit():
    uid = session['user_id']
    amount = request.json.get('amount', 300)
    if amount < 300:
        return jsonify({"error": "Минимальное пополнение 300 руб."}), 400
    user_balance[uid] += amount
    return jsonify({"balance": user_balance[uid]})

@app.route('/api/training', methods=['GET'])
def training():
    track = get_track()
    return jsonify({"track": track})

@app.route('/api/attempt', methods=['POST'])
def make_attempt():
    uid = session['user_id']
    stake = request.json.get('stake', BASE_PRICE)
    if stake not in [100, 200, 500, 1000]:
        return jsonify({"error": "Неверный номинал"}), 400
    if user_balance[uid] < stake:
        return jsonify({"error": "Недостаточно средств"}), 402
    if attempts_today[uid] >= 20:
        return jsonify({"error": "Лимит попыток на сегодня исчерпан"}), 429

    user_balance[uid] -= stake
    attempts_today[uid] += 1
    track = get_track()
    return jsonify({
        "message": "Попытка начата",
        "track": track,
        "stake": stake,
        "balance": user_balance[uid]
    })

@app.route('/api/submit_result', methods=['POST'])
def submit_result():
    uid = session['user_id']
    data = request.json
    stake = data.get('stake', BASE_PRICE)
    results = data.get('results', [])
    if len(results) != 5:
        return jsonify({"error": "Неверное количество ударов"}), 400

    saved = 0
    for res in results:
        if res['sector_clicked'] == res['correct_sector'] and res['reaction_time_ms'] >= MIN_REACTION_TIME:
            saved += 1

    base_prize = PRIZES.get(saved, 0)
    multiplier = stake / BASE_PRICE
    prize = int(base_prize * multiplier)
    user_balance[uid] += prize
    return jsonify({
        "saved": saved,
        "prize": prize,
        "balance": user_balance[uid],
        "message": f"Отбито {saved}/5. Выигрыш: {prize} руб."
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
