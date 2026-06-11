# server.py
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import json
import hashlib
from datetime import datetime, timedelta
import os

app = Flask(__name__)
CORS(app)

# Файлы для хранения данных
USERS_FILE = 'users.json'
REQUESTS_FILE = 'requests.json'


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_users(users):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def load_requests():
    if os.path.exists(REQUESTS_FILE):
        with open(REQUESTS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_requests(requests_data):
    with open(REQUESTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(requests_data, f, indent=2, ensure_ascii=False)


# Загружаем данные при старте
users = load_users()
requests_data = load_requests()


# ============ API для клиента ============

@app.route('/api/request_activation', methods=['POST'])
def request_activation():
    """Запрос на активацию от сотрудника"""
    data = request.json
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    pc_fingerprint = data.get('pc_fingerprint')
    pc_name = data.get('pc_name')
    os_info = data.get('os_info')

    if not first_name or not last_name:
        return jsonify({'error': 'Введите имя и фамилию'}), 400

    user_id = f"{first_name}_{last_name}".lower()

    # Создаем заявку
    request_id = hashlib.md5(f"{user_id}_{datetime.now().isoformat()}".encode()).hexdigest()[:8]

    requests_data[request_id] = {
        'user_id': user_id,
        'first_name': first_name,
        'last_name': last_name,
        'pc_fingerprint': pc_fingerprint,
        'pc_name': pc_name,
        'os_info': os_info,
        'request_time': datetime.now().isoformat(),
        'status': 'pending'
    }
    save_requests(requests_data)

    return jsonify({
        'status': 'pending',
        'request_id': request_id,
        'message': 'Заявка отправлена администратору'
    })


@app.route('/api/check_access', methods=['POST'])
def check_access():
    """Проверка доступа при запуске ПО"""
    data = request.json
    first_name = data.get('first_name', '').strip()
    last_name = data.get('last_name', '').strip()
    pc_fingerprint = data.get('pc_fingerprint')

    user_id = f"{first_name}_{last_name}".lower()

    if user_id not in users:
        return jsonify({
            'has_access': False,
            'reason': 'Пользователь не активирован'
        })

    user = users[user_id]

    # Проверка на приостановку
    if user.get('user_status') == 'suspended':
        return jsonify({
            'has_access': False,
            'reason': 'Доступ приостановлен администратором'
        })

    if user.get('pc_fingerprint') != pc_fingerprint:
        return jsonify({
            'has_access': False,
            'reason': 'Доступ только с активированного компьютера'
        })

    expires = datetime.fromisoformat(user['expires'])
    if expires < datetime.now():
        return jsonify({
            'has_access': False,
            'reason': f'Срок доступа истек {user["expires"]}'
        })

    # Обновляем время последней проверки
    user['last_check'] = datetime.now().isoformat()
    save_users(users)

    return jsonify({
        'has_access': True,
        'expires': user['expires'],
        'days_left': (expires - datetime.now()).days,
        'user_status': user.get('user_status', 'active')
    })


@app.route('/api/ping', methods=['POST'])
def ping():
    """Периодический пинг от ПО"""
    data = request.json
    first_name = data.get('first_name')
    last_name = data.get('last_name')
    pc_fingerprint = data.get('pc_fingerprint')

    user_id = f"{first_name}_{last_name}".lower()

    if user_id in users:
        users[user_id]['last_seen'] = datetime.now().isoformat()
        users[user_id]['last_pc'] = pc_fingerprint
        save_users(users)

    return jsonify({'status': 'ok'})


# ============ Админка (ваш веб-интерфейс) ============

ADMIN_PASSWORD_HASH = hashlib.sha256("admin123".encode()).hexdigest()

LOGIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Админка - Вход</title>
    <style>
        body { font-family: Arial; display: flex; justify-content: center; align-items: center; height: 100vh; background: #1e1e1e; margin: 0; }
        .login { width: 320px; padding: 30px; background: #2b2b2b; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }
        h2 { color: #3b82f6; text-align: center; margin-bottom: 25px; }
        input { width: 100%; padding: 10px; margin: 10px 0; background: #3b3b3b; border: 1px solid #555; color: white; border-radius: 6px; font-size: 14px; box-sizing: border-box; }
        button { width: 100%; padding: 12px; background: #3b82f6; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; }
        button:hover { background: #2563eb; }
        .error { color: #ef4444; text-align: center; margin-top: 10px; }
    </style>
</head>
<body>
    <div class="login">
        <h2>🔐 Вход в админку</h2>
        <form method="post">
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit">Войти</button>
        </form>
        {% if error %}<p class="error">{{ error }}</p>{% endif %}
    </div>
</body>
</html>
'''

ADMIN_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>Админка Ozon Калькулятор</title>
    <style>
        * { box-sizing: border-box; }
        body { font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #1e1e1e; color: #fff; }
        .container { max-width: 1600px; margin: 0 auto; }
        h1 { color: #3b82f6; margin-bottom: 10px; }
        h2 { color: #3b82f6; margin: 25px 0 15px 0; padding-bottom: 8px; border-bottom: 2px solid #3b82f6; }
        .stats { display: flex; gap: 20px; margin-bottom: 30px; flex-wrap: wrap; }
        .stat-card { background: #2b2b2b; border-radius: 12px; padding: 15px 25px; text-align: center; flex: 1; min-width: 150px; }
        .stat-number { font-size: 32px; font-weight: bold; color: #3b82f6; }
        .stat-label { font-size: 14px; color: #aaa; margin-top: 5px; }
        table { width: 100%; border-collapse: collapse; margin: 15px 0; background: #2b2b2b; border-radius: 10px; overflow: hidden; }
        th, td { border: 1px solid #444; padding: 12px 10px; text-align: left; }
        th { background: #3b3b3b; color: #3b82f6; font-weight: 600; }
        td { word-break: break-word; }
        .badge { display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: bold; }
        .badge-pending { background: #f59e0b; color: #000; }
        .badge-approved { background: #22c55e; color: #000; }
        .badge-active { background: #22c55e; color: #000; }
        .badge-suspended { background: #f59e0b; color: #000; }
        .badge-expired { background: #ef4444; color: #fff; }
        button { padding: 6px 12px; margin: 2px; cursor: pointer; border: none; border-radius: 6px; font-size: 12px; font-weight: bold; transition: all 0.2s; }
        button:hover { opacity: 0.85; transform: scale(1.02); }
        .approve { background: #22c55e; color: #000; }
        .reject { background: #ef4444; color: #fff; }
        .suspend { background: #f59e0b; color: #000; }
        .unsuspend { background: #22c55e; color: #000; }
        .extend { background: #3b82f6; color: #fff; }
        .revoke { background: #dc2626; color: #fff; }
        .refresh-btn { background: #3b82f6; color: #fff; padding: 8px 16px; font-size: 14px; margin-bottom: 15px; }
        .footer { text-align: center; margin-top: 30px; padding: 20px; color: #666; font-size: 12px; border-top: 1px solid #444; }
        code { font-size: 11px; background: #1e1e1e; padding: 2px 5px; border-radius: 4px; }
        @media (max-width: 768px) {
            th, td { font-size: 12px; padding: 8px 5px; }
            button { padding: 4px 8px; font-size: 10px; }
            .stat-number { font-size: 24px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
            <h1>📊 Админка Ozon Калькулятор</h1>
            <button class="refresh-btn" onclick="location.reload()">🔄 Обновить</button>
        </div>

        <!-- Статистика -->
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ users|length }}</div>
                <div class="stat-label">Всего пользователей</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ users.values()|selectattr('user_status', 'equalto', 'active')|list|length }}</div>
                <div class="stat-label">Активных</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ users.values()|selectattr('user_status', 'equalto', 'suspended')|list|length }}</div>
                <div class="stat-label">Приостановленных</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ requests.values()|selectattr('status', 'equalto', 'pending')|list|length }}</div>
                <div class="stat-label">Новых заявок</div>
            </div>
        </div>

        <!-- Новые заявки -->
        <h2>📋 Новые заявки</h2>
        <table>
            <thead>
                <tr><th>Имя</th><th>Фамилия</th><th>ID ПК</th><th>Имя ПК</th><th>ОС</th><th>Время</th><th>Действие</th></tr>
            </thead>
            <tbody>
                {% for req_id, req in requests.items() if req.status == 'pending' %}
                <tr>
                    <td>{{ req.first_name }}</td>
                    <td>{{ req.last_name }}</td>
                    <td><code>{{ req.pc_fingerprint[:20] }}...</code></td>
                    <td>{{ req.pc_name }}</td>
                    <td>{{ req.os_info[:40] }}{% if req.os_info|length > 40 %}...{% endif %}</td>
                    <td>{{ req.request_time[:19] }}</td>
                    <td>
                        <button class="approve" onclick="approve('{{ req_id }}')">✅ Активировать</button>
                        <button class="reject" onclick="reject('{{ req_id }}')">❌ Отклонить</button>
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="7" style="text-align: center;">✨ Нет новых заявок</td></tr>
                {% endfor %}
            </tbody>
        </table>

        <!-- Все пользователи -->
        <h2>👥 Все пользователи</h2>
        <table>
            <thead>
                <tr><th>Имя</th><th>Фамилия</th><th>Статус</th><th>Активирован до</th><th>Осталось дней</th><th>Последний вход</th><th>Действие</th></tr>
            </thead>
            <tbody>
                {% for user_id, user in users.items() %}
                {% set expires = datetime.fromisoformat(user.expires) %}
                {% set days_left = (expires - datetime.now()).days %}
                {% set is_suspended = user.user_status == 'suspended' %}
                <tr>
                    <td>{{ user.first_name }}</td>
                    <td>{{ user.last_name }}</td>
                    <td>
                        {% if is_suspended %}
                        <span class="badge badge-suspended">⏸ ПРИОСТАНОВЛЕН</span>
                        {% elif days_left < 0 %}
                        <span class="badge badge-expired">❌ ИСТЕК</span>
                        {% else %}
                        <span class="badge badge-active">✅ АКТИВЕН</span>
                        {% endif %}
                    </td>
                    <td>{{ user.expires[:19] }}</td>
                    <td style="color: {% if days_left < 0 %}#ef4444{% elif is_suspended %}#f59e0b{% elif days_left < 7 %}#f59e0b{% else %}#22c55e{% endif %}; font-weight: bold;">
                        {{ days_left if days_left >= 0 else 0 }} дн.
                    </td>
                    <td>{{ user.last_seen[:19] if user.last_seen else 'никогда' }}</td>
                    <td>
                        {% if not is_suspended and days_left >= 0 %}
                        <button class="suspend" onclick="suspend('{{ user_id }}')">⏸ Приостановить</button>
                        <button class="extend" onclick="extend('{{ user_id }}')">➕ Продлить</button>
                        <button class="revoke" onclick="revoke('{{ user_id }}')">🔴 Отозвать</button>
                        {% elif is_suspended %}
                        <button class="unsuspend" onclick="unsuspend('{{ user_id }}')">▶ Возобновить</button>
                        <button class="extend" onclick="extend('{{ user_id }}')">➕ Продлить</button>
                        <button class="revoke" onclick="revoke('{{ user_id }}')">🔴 Отозвать</button>
                        {% else %}
                        <button class="revoke" onclick="revoke('{{ user_id }}')">🔴 Отозвать</button>
                        {% endif %}
                    </td>
                </tr>
                {% else %}
                <tr><td colspan="7" style="text-align: center;">👻 Нет пользователей</td></tr>
                {% endfor %}
            </tbody>
        </table>

        <!-- История заявок -->
        <h2>📜 История заявок</h2>
        <table>
            <thead>
                <tr><th>Имя</th><th>Фамилия</th><th>Статус</th><th>Время запроса</th><th>Время решения</th></tr>
            </thead>
            <tbody>
                {% for req_id, req in requests.items() if req.status != 'pending' %}
                <tr>
                    <td>{{ req.first_name }}</td>
                    <td>{{ req.last_name }}</td>
                    <td><span class="badge badge-{{ req.status }}">{{ req.status }}</span></td>
                    <td>{{ req.request_time[:19] }}</td>
                    <td>{{ req.approved_at[:19] if req.approved_at else '-' }}</td>
                </tr>
                {% else %}
                <tr><td colspan="5" style="text-align: center;">📭 Нет истории</td></tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="footer">
            Ozon Калькулятор - Система лицензирования
        </div>
    </div>

    <script>
        async function approve(requestId) {
            if(confirm('✅ Активировать доступ пользователю на 30 дней?')) {
                let response = await fetch(`/admin/approve/${requestId}`, {method: 'POST'});
                if(response.ok) location.reload();
                else alert('Ошибка при активации');
            }
        }

        async function reject(requestId) {
            if(confirm('❌ Отклонить заявку?')) {
                let response = await fetch(`/admin/reject/${requestId}`, {method: 'POST'});
                if(response.ok) location.reload();
                else alert('Ошибка при отклонении');
            }
        }

        async function suspend(userId) {
            if(confirm('⏸ Приостановить доступ пользователю? Он не сможет работать до возобновления.')) {
                let response = await fetch(`/admin/suspend/${userId}`, {method: 'POST'});
                if(response.ok) location.reload();
                else alert('Ошибка при приостановке');
            }
        }

        async function unsuspend(userId) {
            if(confirm('▶ Возобновить доступ пользователю?')) {
                let response = await fetch(`/admin/unsuspend/${userId}`, {method: 'POST'});
                if(response.ok) location.reload();
                else alert('Ошибка при возобновлении');
            }
        }

        async function revoke(userId) {
            if(confirm('🔴 ОТОЗВАТЬ доступ пользователю? Это действие нельзя отменить. Пользователю потребуется новая заявка.')) {
                let response = await fetch(`/admin/revoke/${userId}`, {method: 'POST'});
                if(response.ok) location.reload();
                else alert('Ошибка при отзыве');
            }
        }

        async function extend(userId) {
            if(confirm('➕ Продлить доступ пользователю на 30 дней?')) {
                let response = await fetch(`/admin/extend/${userId}`, {method: 'POST'});
                if(response.ok) location.reload();
                else alert('Ошибка при продлении');
            }
        }
    </script>
</body>
</html>
'''


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password')
        if hashlib.sha256(password.encode()).hexdigest() != ADMIN_PASSWORD_HASH:
            return render_template_string(LOGIN_HTML, error="Неверный пароль")
        return render_template_string(ADMIN_HTML, requests=requests_data, users=users, datetime=datetime)
    return render_template_string(LOGIN_HTML, error=None)


@app.route('/admin/approve/<request_id>', methods=['POST'])
def approve_request(request_id):
    if request_id not in requests_data:
        return jsonify({'error': 'Заявка не найдена'}), 404

    req = requests_data[request_id]
    user_id = req['user_id']
    expires = (datetime.now() + timedelta(days=30)).isoformat()

    users[user_id] = {
        'first_name': req['first_name'],
        'last_name': req['last_name'],
        'pc_fingerprint': req['pc_fingerprint'],
        'pc_name': req['pc_name'],
        'os_info': req['os_info'],
        'expires': expires,
        'activated': datetime.now().isoformat(),
        'last_seen': datetime.now().isoformat(),
        'user_status': 'active'
    }

    req['status'] = 'approved'
    req['approved_at'] = datetime.now().isoformat()
    save_requests(requests_data)
    save_users(users)

    return jsonify({'status': 'ok'})


@app.route('/admin/reject/<request_id>', methods=['POST'])
def reject_request(request_id):
    if request_id in requests_data:
        requests_data[request_id]['status'] = 'rejected'
        save_requests(requests_data)
    return jsonify({'status': 'ok'})


@app.route('/admin/revoke/<user_id>', methods=['POST'])
def revoke_user(user_id):
    if user_id in users:
        del users[user_id]
        save_users(users)
    return jsonify({'status': 'ok'})


@app.route('/admin/extend/<user_id>', methods=['POST'])
def extend_user(user_id):
    if user_id in users:
        new_expires = (datetime.now() + timedelta(days=30)).isoformat()
        users[user_id]['expires'] = new_expires
        users[user_id]['user_status'] = 'active'  # При продлении снимаем приостановку
        save_users(users)
    return jsonify({'status': 'ok'})


@app.route('/admin/suspend/<user_id>', methods=['POST'])
def suspend_user(user_id):
    """Приостановить доступ пользователя"""
    if user_id in users:
        users[user_id]['user_status'] = 'suspended'
        users[user_id]['suspended_at'] = datetime.now().isoformat()
        save_users(users)
        return jsonify({'status': 'ok', 'message': 'Доступ приостановлен'})
    return jsonify({'error': 'Пользователь не найден'}), 404


@app.route('/admin/unsuspend/<user_id>', methods=['POST'])
def unsuspend_user(user_id):
    """Возобновить доступ пользователя"""
    if user_id in users:
        users[user_id]['user_status'] = 'active'
        users[user_id]['unsuspended_at'] = datetime.now().isoformat()
        save_users(users)
        return jsonify({'status': 'ok', 'message': 'Доступ восстановлен'})
    return jsonify({'error': 'Пользователь не найден'}), 404


if __name__ == '__main__':
    print("\n" + "=" * 50)
    print("🚀 License Server запущен")
    print("=" * 50)
    print(f"📍 Админка: http://localhost:5000/admin")
    print(f"🔑 Пароль админа: admin123")
    print("=" * 50)
    print("\nНажмите Ctrl+C для остановки сервера\n")
    app.run(host='0.0.0.0', port=5000, debug=True)