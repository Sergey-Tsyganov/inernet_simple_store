from flask import Flask, render_template, request, session, redirect, url_for
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet, write_sheet, get_max_order_number
from collections import defaultdict
from datetime import datetime
from forms import RegistrationForm
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # В продакшене замените на безопасный ключ


# Фильтр для Jinja2 (форматирование дат)
@app.template_filter('format_date')
def format_date(value):
    try:
        dt = datetime.strptime(value, '%d.%m.%Y %H:%M:%S')
        return dt.strftime('%Y-%m')
    except:
        return ''


# Авторизация
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
            return redirect(url_for('shop'))

        captcha_text, captcha_path = generate_captcha()
        session['captcha_text'] = captcha_text
        return render_template('login.html', captcha=captcha_path, error='Неверный логин или пароль')

    captcha_text, captcha_path = generate_captcha()
    session['captcha_text'] = captcha_text
    return render_template('login.html', captcha=captcha_path)


# Регистрация
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
                "0",  # Скидка 0%
                form.company.data.strip(),
                form.address.data.strip(),
                form.phone.data.strip(),
                email,
                ""  # Комментарий
            ]
            write_sheet('Users!A3', [new_user])
            success = True

    return render_template('registration.html', form=form, error=error, success=success)


# Выход
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# Каталог (Shop)
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

    message = None

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
            for o in orders:
                write_sheet('Orders!A3', [o])
            message = f'Заказ № {new_order_number} размещен успешно.'
        else:
            message = 'Вы не выбрали товары.'

    return render_template('shop.html',
                           products=products,
                           discount=discount,
                           client=session,
                           message=message)


# Главная
@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html', year=datetime.now().year)


# Контакты
@app.route('/contacts')
def contacts():
    return render_template('contacts.html', year=datetime.now().year)


# Обратная связь
@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    success = False
    if request.method == 'POST':
        success = True  # В дальнейшем: запись в таблицу или отправка письма
    return render_template('feedback.html', year=datetime.now().year, success=success)


# Страница заказов
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


# О проекте
@app.route('/about')
def about():
    return render_template('about.html', year=datetime.now().year)


if __name__ == '__main__':
    app.run(debug=True)
