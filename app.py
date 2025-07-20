from flask import Flask, render_template, request, session, redirect, url_for
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet, write_sheet, get_max_order_number
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # Замени на безопасный ключ в продакшене


# Фильтр Jinja2 для форматирования даты
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

        if username in user_dict and user_dict[username][1] == password:
            user_data = user_dict[username]
            session['username'] = username
            session['discount'] = float(user_data[2])
            session['client_name'] = user_data[3]
            session['client_address'] = user_data[4]
            session['client_phone'] = user_data[5]
            session['client_email'] = user_data[6]
            session['client_comment'] = user_data[7]
            return redirect(url_for('shop'))
        else:
            captcha_text, captcha_path = generate_captcha()
            session['captcha_text'] = captcha_text
            return render_template('login.html', captcha=captcha_path, error='Неверный логин или пароль')

    captcha_text, captcha_path = generate_captcha()
    session['captcha_text'] = captcha_text
    return render_template('login.html', captcha=captcha_path)


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
    if request.method == 'POST':
        success = True  # В дальнейшем: отправка email или запись в таблицу
    return render_template('feedback.html', year=datetime.now().year, success=success)


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
