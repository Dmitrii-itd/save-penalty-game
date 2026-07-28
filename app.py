import json
import random
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = 'super-secret-key-change-in-production'

# Глобальное хранилище (для прототипа, в продакшене — БД)
daily_track = []
last_track_date = None
user_balance = {}  # ключ - session id, значение - баланс в рублях
attempts_today = {}  # количество попыток пользователя сегодня

# Настройки
BASE_PRICE = 100  # базовая цена попытки
PRIZES = {5: 316, 4: 134, 3: 60, 2: 0, 1: 0, 0: 0}
REACTION_WINDOW_MS = 300  # окно появления подсказки до удара
MIN_REACTION_TIME = 100   # минимальное физиологическое время реакции, мс

def generate_daily_track():
    """Генерирует трассу дня (5 ударов). Для простоты сектора: 0-верх-лево, 1-верх-центр, 2-верх-право,
    3-середина-лево, 4-середина-центр, 5-середина-право, 6-низ-лево, 7-низ-центр, 8-низ-право."""
    track = []
    for _ in range(5):
        sector = random.randint(0, 8)
        track.append({
            "sector": sector,
            "prompt_time": random.uniform(0.5, 1.5)  # секунд от начала раунда, когда загорается подсказка
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
    return jsonify({"balance": user_balance[uid], "message": f"Счёт пополнен на {amount} руб."})

@app.route('/api/attempt', methods=['POST'])
def make_attempt():
    uid = session['user_id']
    stake = request.json.get('stake', BASE_PRICE)
    if stake not in [100, 200, 500, 1000]:
        return jsonify({"error": "Неверный номинал"}), 400
    if user_balance[uid] < stake:
        return jsonify({"error": "Недостаточно средств"}), 402
    if attempts_today[uid] >= 20:
        return jsonify({"error": "Достигнут лимит попыток на сегодня"}), 429

    # Списание
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
