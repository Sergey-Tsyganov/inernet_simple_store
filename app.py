from flask import Flask, render_template, request, session, redirect, url_for
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet, write_sheet, get_max_order_number, update_sheet_range, clear_sheet_range
from collections import defaultdict
from datetime import datetime
from forms import RegistrationForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import threading
import requests
from flask import send_from_directory

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # замените в продакшене


# ======== Загрузка параметров из admin листа =========
def load_admin_settings():
    admin_data = read_sheet('admin!A2:H2')[0]
    return {
        'admin_email': admin_data[0],
        'admin_phone': admin_data[1],
        'telegram_bot_token': admin_data[2],
        'telegram_chat_id': admin_data[3],
        'mail_server': admin_data[4],
        'mail_port': int(admin_data[5]),
        'mail_password': admin_data[6],
        'mail_use_ssl': admin_data[7].strip().upper() == 'TRUE'
    }


def apply_mail_settings(config):
    app.config['MAIL_SERVER'] = config['mail_server']
    app.config['MAIL_PORT'] = config['mail_port']
    app.config['MAIL_USE_SSL'] = config['mail_use_ssl']
    app.config['MAIL_USERNAME'] = config['admin_email']
    app.config['MAIL_PASSWORD'] = config['mail_password']


admin_settings = load_admin_settings()
apply_mail_settings(admin_settings)
mail = Mail(app)


# ========== Telegram ==========
def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{admin_settings["telegram_bot_token"]}/sendMessage'
    payload = {
        'chat_id': admin_settings["telegram_chat_id"],
        'text': text
    }
    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            print(f'❌ Ошибка Telegram: {response.text}')
        else:
            print('✅ Сообщение отправлено в Telegram')
    except Exception as e:
        print(f'❌ Ошибка при отправке в Telegram: {e}')


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.template_filter('format_date')
def format_date(value):
    try:
        dt = datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
        return dt.strftime('%Y-%m')
    except:
        return ''


# ========== Почта ==========
def send_order_email(subject, recipients, body):
    try:
        msg = Message(subject=subject,
                      sender=app.config['MAIL_USERNAME'],
                      recipients=recipients,
                      body=body)
        with app.app_context():
            mail.send(msg)
        print("✅ Email отправлен")
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {e}")


# ========== Основные маршруты ==========
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha_input = request.form['captcha']

        if captcha_input != session.get('captcha_text'):
            captcha_text, captcha_path = generate_captcha()
            session['captcha_text'] = captcha_text
            return render_template('login.html', captcha=captcha_path, error='Неверная капча')

        users = read_sheet('Users!A2:H')
        user_dict = {u[0]: u for u in users}

        if username in user_dict and check_password_hash(user_dict[username][1], password):
            user_data = user_dict[username]
            session['username'] = username
            session['discount'] = float(user_data[2]) if len(user_data) > 2 else 0
            session['client_name'] = user_data[3] if len(user_data) > 3 else ''
            session['client_address'] = user_data[4] if len(user_data) > 4 else ''
            session['client_phone'] = user_data[5] if len(user_data) > 5 else ''
            session['client_email'] = user_data[6] if len(user_data) > 6 else ''
            session['client_comment'] = user_data[7] if len(user_data) > 7 else ''

            if username == 'admin':
                return redirect('/admin')
            return redirect('/shop')

        captcha_text, captcha_path = generate_captcha()
        session['captcha_text'] = captcha_text
        return render_template('login.html', captcha=captcha_path, error='Неверный логин или пароль')

    captcha_text, captcha_path = generate_captcha()
    session['captcha_text'] = captcha_text
    return render_template('login.html', captcha=captcha_path)


@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    error = None
    success = False

    if form.validate_on_submit():
        username = form.username.data.strip()
        email = form.email.data.strip().lower()

        users = read_sheet('Users!A2:H')
        existing_usernames = [u[0] for u in users]
        existing_emails = [u[6].strip().lower() for u in users if len(u) >= 7]

        if username in existing_usernames:
            error = 'Этот логин уже используется.'
        elif email in existing_emails:
            error = 'Этот email уже зарегистрирован.'
        else:
            hashed_password = generate_password_hash(form.password.data)
            new_user = [
                username,
                hashed_password,
                "0",
                form.company.data.strip(),
                form.address.data.strip(),
                form.phone.data.strip(),
                email,
                ""
            ]
            write_sheet('Users!A3', [new_user])
            success = True

    return render_template('registration.html', form=form, error=error, success=success)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


@app.route('/shop', methods=['GET', 'POST'])
def shop():
    if 'username' not in session:
        return redirect('/login')

    discount = session.get('discount', 0)
    products_raw = read_sheet('Products!A2:F')
    products = []
    for p in products_raw:
        price = float(p[2])
        price_discounted = price * (1 - discount / 100)
        products.append({
            'sku': p[0],
            'name': p[1],
            'price': price,
            'price_discounted': price_discounted,
            'photo': p[3],
            'stock': int(p[4]),
            'description': p[5]
        })

    message = session.pop('shop_message', None)

    if request.method == 'POST':
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        max_order_number = get_max_order_number()
        new_order_number = max_order_number + 1

        orders = []

        for i, p in enumerate(products):
            qty = request.form.get(f'qty_{i}')
            if qty:
                qty = int(qty)
                if 0 < qty <= p['stock']:
                    orders.append([
                        now,
                        session['client_name'],
                        new_order_number,
                        p['sku'],
                        p['name'],
                        qty,
                        p['price_discounted'],
                        'новый'
                    ])

        if orders:
            write_sheet('Orders!A3', orders)

            total_sum = 0
            email_body = f'Здравствуйте, {session["client_name"]}!\n\nВаш заказ № {new_order_number} оформлен {now}.\n\nСостав заказа:\n'
            telegram_message = f'📦 Новый заказ № {new_order_number} от {session["client_name"]} ({now})\n\n'

            for o in orders:
                line = f"{o[4]} (Артикул: {o[3]}) — {o[5]} шт. по {float(o[6]):.2f} руб.\n"
                email_body += line
                telegram_message += line
                total_sum += int(o[5]) * float(o[6])

            email_body += f'\nИтоговая сумма: {total_sum:.2f} руб.\n\nСпасибо за ваш заказ!'
            telegram_message += f'\n💰 Итог: {total_sum:.2f} руб.'

            recipients = [session['client_email'], admin_settings['admin_email']]

            threading.Thread(target=send_order_email,
                             args=(f'Заказ № {new_order_number}', recipients, email_body)).start()
            threading.Thread(target=send_telegram_message, args=(telegram_message,)).start()

            session['shop_message'] = f'Заказ № {new_order_number} размещен успешно. Уведомление отправлено.'
        else:
            session['shop_message'] = 'Вы не выбрали товары.'

        return redirect('/shop')

    return render_template('shop.html', products=products, discount=discount, client=session, message=message)


@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if session.get('username') != 'admin':
        return redirect('/login')

    # Чтение настроек из admin!A2:H2
    admin_data = read_sheet('admin!A2:H2')[0]
    admin_email = admin_data[0]
    admin_phone = admin_data[1]
    telegram_token = admin_data[2]
    telegram_chat_id = admin_data[3]
    mail_server = admin_data[4]
    mail_port = admin_data[5]
    mail_password = admin_data[6]
    mail_use_ssl = admin_data[7]

    success = False
    message = None

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'update_admin':
            admin_email = request.form['admin_email'].strip()
            admin_phone = request.form['admin_phone'].strip()
            telegram_token = request.form['telegram_token'].strip()
            telegram_chat_id = request.form['telegram_chat_id'].strip()
            mail_server = request.form['mail_server'].strip()
            mail_port = request.form['mail_port'].strip()
            mail_password = request.form['mail_password'].strip()
            mail_use_ssl = request.form['mail_use_ssl'].strip().upper()

            admin_data = [
                admin_email,
                admin_phone,
                telegram_token,
                telegram_chat_id,
                mail_server,
                mail_port,
                mail_password,
                mail_use_ssl
            ]
            print(admin_data)
            update_sheet_range('admin!A2:H2', [admin_data])
            success = True
            message = "Настройки успешно обновлены."

        elif action == 'reload_settings':
            global admin_settings
            admin_settings = load_admin_settings()
            apply_mail_settings(admin_settings)
            message = "Параметры успешно перезагружены из Google Sheets."

    users = read_sheet('Users!A2:H')

    return render_template('admin.html',
                           admin_email=admin_email,
                           admin_phone=admin_phone,
                           telegram_token=telegram_token,
                           telegram_chat_id=telegram_chat_id,
                           mail_server=mail_server,
                           mail_port=mail_port,
                           mail_password=mail_password,
                           mail_use_ssl=mail_use_ssl,
                           users=users,
                           success=success,
                           message=message)


@app.route('/admin/delete/<username>')
def admin_delete_user(username):
    if session.get('username') != 'admin':
        return redirect('/login')

    users = read_sheet('Users!A2:H')
    users = [u for u in users if u[0] != username]
    clear_sheet_range('Users!A2:H')
    if users:
        write_sheet('Users!A2', users)
    return redirect('/admin')


@app.route('/admin/edit/<username>', methods=['GET', 'POST'])
def admin_edit_user(username):
    if session.get('username') != 'admin':
        return redirect('/login')

    users = read_sheet('Users!A2:H')
    user_data = next((u for u in users if u[0] == username), None)

    if not user_data:
        return "Пользователь не найден", 404

    if request.method == 'POST':
        updated_row = [
            user_data[0],
            user_data[1],
            request.form['discount'],
            request.form['company'],
            request.form['address'],
            request.form['phone'],
            request.form['email'],
            request.form['comment']
        ]
        row_number = users.index(user_data) + 2
        update_sheet_range(f'Users!A{row_number}:H{row_number}', [updated_row])
        return redirect('/admin')

    return render_template('admin_edit.html', user=user_data)


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', year=datetime.now().year)


@app.route('/contacts')
def contacts():
    return render_template('contacts.html', year=datetime.now().year)


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    success = False
    client_authenticated = 'username' in session

    if request.method == 'POST':
        now = datetime.now().strftime('%d.%m.%Y %H:%M:%S')

        client_name = session.get('client_name') if client_authenticated else ''
        name = session.get('client_name') if client_authenticated else request.form.get('name', '').strip()
        email = session.get('client_email') if client_authenticated else request.form.get('email', '').strip()
        phone = session.get('client_phone') if client_authenticated else request.form.get('phone', '').strip()

        message_type = request.form.get('message_type', '').strip()
        order_number = request.form.get('order_number', '').strip()
        message_text = request.form.get('message', '').strip()

        record = [now, client_name, name, email, phone, message_type, order_number, message_text]
        write_sheet('Feedback!A2', [record])
        success = True

    return render_template('feedback.html', year=datetime.now().year, success=success,
                           client_authenticated=client_authenticated)


@app.route('/orders')
def orders():
    if 'username' not in session:
        return redirect('/login')

    orders_raw = read_sheet('Orders!A3:H')
    client_name = session['client_name']
    client_orders = [o for o in orders_raw if o[1] == client_name]

    grouped = defaultdict(list)
    for o in client_orders:
        order_number = o[2]
        grouped[order_number].append(o)

    total_sum = sum(int(o[5]) * float(o[6]) for group in grouped.values() for o in group if
                    len(o) >= 8 and o[7].strip() != 'отказано')
    total_qty = sum(
        int(o[5]) for group in grouped.values() for o in group if len(o) >= 8 and o[7].strip() != 'отказано')

    months = sorted({datetime.strptime(o[0], '%d.%m.%Y %H:%M:%S').strftime('%Y-%m') for o in client_orders if o[0]},
                    reverse=True)

    return render_template('orders.html', grouped=grouped, discount=session['discount'], client=session,
                           total_sum=total_sum, total_qty=total_qty, months=months)


@app.route('/about')
def about():
    return render_template('about.html', year=datetime.now().year)


if __name__ == '__main__':
    app.run(debug=True)
