from flask import Flask, render_template, request, session, redirect, url_for
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet, write_sheet, get_max_order_number, update_sheet_range
from collections import defaultdict
from datetime import datetime
from forms import RegistrationForm
from werkzeug.security import generate_password_hash, check_password_hash
from flask_mail import Mail, Message
import requests


app = Flask(__name__)
# Настройки почты
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'tsysn1@gmail.com'   # твой email
app.config['MAIL_PASSWORD'] = 'wsnq oqfd rsbb fljq'           # пароль приложения

mail = Mail(app)
# API TELEGA bot 7360824344:AAFBPSYExdZ4cXX95HBpJNxFnWImSO61FRA
# Tsy_simple_bot  Tsy_simple_istore
#chat id 384456688

TELEGRAM_BOT_TOKEN = '7360824344:AAFBPSYExdZ4cXX95HBpJNxFnWImSO61FRA'
TELEGRAM_CHAT_ID = '384456688'  # например: '-1001234567890'

app.secret_key = 'supersecretkey'  # замените на безопасный ключ в продакшене

def send_telegram_message(text):
    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
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


@app.template_filter('format_date')
def format_date(value):
    try:
        dt = datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
        return dt.strftime('%Y-%m')
    except:
        return ''


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

import threading
from flask_mail import Message

def send_order_email(subject, recipients, body):
    """Фоновая отправка email."""
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
            email_body = f'Здравствуйте, {session["client_name"]}!\n\n'
            email_body += f'Ваш заказ № {new_order_number} оформлен {now}.\n\n'
            email_body += 'Состав заказа:\n'

            telegram_message = f'📦 Новый заказ № {new_order_number} от {session["client_name"]} ({now})\n\n'

            for o in orders:
                line = f"{o[4]} (Артикул: {o[3]}) — {o[5]} шт. по {float(o[6]):.2f} руб.\n"
                email_body += line
                telegram_message += line
                total_sum += int(o[5]) * float(o[6])

            email_body += f'\nИтоговая сумма: {total_sum:.2f} руб.\n\nСпасибо за ваш заказ!'
            telegram_message += f'\n💰 Итог: {total_sum:.2f} руб.'

            admin_email = read_sheet('admin!A2:B2')[0][0]
            recipients = [session['client_email'], admin_email]

            threading.Thread(
                target=send_order_email,
                args=(f'Заказ № {new_order_number}', recipients, email_body)
            ).start()

            threading.Thread(
                target=send_telegram_message,
                args=(telegram_message,)
            ).start()

            session['shop_message'] = f'Заказ № {new_order_number} размещен успешно. Уведомление отправлено.'
        else:
            session['shop_message'] = 'Вы не выбрали товары.'

        return redirect('/shop')

    return render_template('shop.html',
                           products=products,
                           discount=discount,
                           client=session,
                           message=message)


@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    if session.get('username') != 'admin':
        return redirect('/login')

    admin_data = read_sheet('admin!A2:B2')
    admin_email = admin_data[0][0] if admin_data and len(admin_data[0]) >= 1 else ''
    admin_phone = admin_data[0][1] if admin_data and len(admin_data[0]) >= 2 else ''

    success = False

    if request.method == 'POST' and request.form.get('action') == 'update_admin':
        admin_email = request.form['admin_email'].strip()
        admin_phone = request.form['admin_phone'].strip()
        update_sheet_range('admin!A2', [[admin_email, admin_phone]])
        success = True

    users = read_sheet('Users!A2:H')

    return render_template('admin.html',
                           admin_email=admin_email,
                           admin_phone=admin_phone,
                           users=users,
                           success=success)


@app.route('/admin/delete/<username>')
def admin_delete_user(username):
    if session.get('username') != 'admin':
        return redirect('/login')

    users = read_sheet('Users!A2:H')
    users = [u for u in users if u[0] != username]

    from utils.google_api import clear_sheet_range, write_sheet

    clear_sheet_range('Users!A2:H')  # 1️⃣ Очищаем старый диапазон

    if users:
        write_sheet('Users!A2', users)  # 2️⃣ Записываем оставшиеся строки

    return redirect('/admin')



@app.route('/admin/edit/<username>', methods=['GET', 'POST'])
def admin_edit_user(username):
    # ✅ Ограничение доступа: только для администратора
    if session.get('username') != 'admin':
        return redirect('/login')

    # ✅ Чтение всех пользователей
    users = read_sheet('Users!A2:H')
    user_data = next((u for u in users if u[0] == username), None)

    if not user_data:
        return "Пользователь не найден", 404

    if request.method == 'POST':
        # ✅ Получаем изменённые данные из формы
        discount = request.form['discount']
        company = request.form['company']
        address = request.form['address']
        phone = request.form['phone']
        email = request.form['email']
        comment = request.form['comment']

        # ✅ Формируем обновлённую строку
        updated_row = [
            user_data[0],     # Логин (не меняется)
            user_data[1],     # Пароль (хеш, не меняется)
            discount,
            company,
            address,
            phone,
            email,
            comment
        ]

        # ✅ Обновляем конкретную строку в Google Sheets
        row_number = users.index(user_data) + 2  # строка A2 = 2
        #write_sheet(f'Users!A{row_number}:H{row_number}', [updated_row])
        update_sheet_range(f'Users!A{row_number}:H{row_number}', [updated_row])
        return redirect('/admin')

    # ✅ Отображаем форму редактирования
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

        record = [
            now,
            client_name,
            name,
            email,
            phone,
            message_type,
            order_number,
            message_text
        ]

        write_sheet('Feedback!A2', [record])  # добавляем строку в таблицу

        success = True

    return render_template('feedback.html',
                           year=datetime.now().year,
                           success=success,
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

    total_sum = 0
    total_qty = 0
    for group in grouped.values():
        for o in group:
            if len(o) >= 8 and o[7].strip() != 'отказано':
                qty = int(o[5])
                price = float(o[6])
                total_sum += price * qty
                total_qty += qty

    months = set()
    for o in client_orders:
        if o[0]:
            dt = datetime.strptime(o[0], '%d.%m.%Y %H:%M:%S')
            months.add(dt.strftime('%Y-%m'))

    months = sorted(months, reverse=True)

    return render_template('orders.html',
                           grouped=grouped,
                           discount=session['discount'],
                           client=session,
                           total_sum=total_sum,
                           total_qty=total_qty,
                           months=months)


@app.route('/about')
def about():
    return render_template('about.html', year=datetime.now().year)


if __name__ == '__main__':
    app.run(debug=True)
