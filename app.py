from flask import Flask, render_template, request, session, redirect, url_for
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet, write_sheet, get_max_order_number
from collections import defaultdict
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # замени на безопасный ключ


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        captcha_input = request.form['captcha']

        # проверка капчи
        if captcha_input != session['captcha_text']:
            captcha_text, captcha_path = generate_captcha()
            session['captcha_text'] = captcha_text
            return render_template('login.html', captcha=captcha_path, error='Неверная капча')

        # проверка логина/пароля
        users = read_sheet('Users!A2:H')  # читаем всех пользователей
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


@app.route('/shop', methods=['GET', 'POST'])
def shop():
    if 'username' not in session:
        return redirect('/')

    discount = session['discount']
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

    total_qty = 0
    total_sum_no_discount = 0
    total_sum_with_discount = 0

    if request.method == 'POST':
        from datetime import datetime
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        max_order_number = get_max_order_number()
        new_order_number = max_order_number + 1

        orders = []

        for i, p in enumerate(products):
            qty = request.form.get(f'qty_{i}')
            if qty:
                qty = int(qty)
                if qty > 0 and qty <= p['stock']:
                    price_with_discount = p['price_discounted']

                    orders.append([
                        now,
                        session['client_name'],
                        new_order_number,
                        p['sku'],
                        p['name'],
                        qty,
                        price_with_discount,
                        'новый'
                    ])

        if orders:
            for o in orders:
                write_sheet('Orders!A3', [o])  # запись с 3 строки, append

            message = f'Заказ № {new_order_number} размещен успешно.'
        else:
            message = 'Вы не выбрали товары.'

        return render_template('shop.html',
                               products=products,
                               discount=discount,
                               client=session,
                               total_qty=0,
                               total_sum_no_discount=0,
                               total_sum_with_discount=0,
                               message=message)

    else:
        # При GET-запросе суммы = 0
        return render_template('shop.html',
                               products=products,
                               discount=discount,
                               client=session,
                               total_qty=total_qty,
                               total_sum_no_discount=total_sum_no_discount,
                               total_sum_with_discount=total_sum_with_discount)


@app.route('/')
def index():
    from datetime import datetime
    return render_template('index.html', year=datetime.now().year)


@app.route('/contacts')
def contacts():
    from datetime import datetime
    return render_template('contacts.html', year=datetime.now().year)


@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    from datetime import datetime
    success = False
    if request.method == 'POST':
        # Здесь можно добавить обработку отправки сообщения
        success = True
    return render_template('feedback.html', year=datetime.now().year, success=success)

@app.route('/orders')
def orders():
    username = session.get('username')
    if not username:
        return redirect('/')

    # Чтение всех заказов
    orders_raw = read_sheet('Orders!A3:H')

    # Фильтрация по клиенту
    client_name = session['client_name']
    client_orders = [o for o in orders_raw if o[1] == client_name]

    from collections import defaultdict
    grouped = defaultdict(list)
    for o in client_orders:
        order_number = o[2]
        grouped[order_number].append(o)

    # Подготовка итогов по всем заказам
    total_sum = 0
    total_qty = 0
    for group in grouped.values():
        for o in group:
            if len(o) >= 8 and o[7].strip() != 'отказано':
                qty = int(o[5])
                price = float(o[6])
                total_sum += price * qty
                total_qty += qty

    # Получение всех месяцев для фильтра
    from datetime import datetime
    months = set()
    for o in client_orders:
        if o[0]:
            dt = datetime.strptime(o[0], '%d.%m.%Y %H:%M:%S')
            months.add(dt.strftime('%Y-%m'))

    months = sorted(list(months), reverse=True)

    return render_template('orders.html',
                           grouped=grouped,
                           discount=session['discount'],
                           client=session,
                           total_sum=total_sum,
                           total_qty=total_qty,
                           months=months)
# о проекте
@app.route('/about')
def about():
    from datetime import datetime
    return render_template('about.html', year=datetime.now().year)

if __name__ == '__main__':
    app.run(debug=True)
