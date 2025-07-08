from flask import Flask, render_template, request, session, redirect, url_for
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet, write_sheet

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # замени на безопасный ключ


@app.route('/', methods=['GET', 'POST'])
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
        orders = []
        for i, p in enumerate(products):
            qty = request.form.get(f'qty_{i}')
            if qty:
                qty = int(qty)
                if qty > 0 and qty <= p['stock']:
                    orders.append([session['client_name'], p['name'], qty, p['price_discounted'] * qty])
                    total_qty += qty
                    total_sum_no_discount += p['price'] * qty
                    total_sum_with_discount += p['price_discounted'] * qty
        if orders:
            for o in orders:
                write_sheet('Orders!A2', [o])
            message = f'Заказ размещен. Всего {total_qty} шт. на сумму {total_sum_with_discount:.2f} руб.'
        else:
            message = 'Вы не выбрали товары.'
        return render_template('shop.html',
                               products=products,
                               discount=discount,
                               client=session,
                               total_qty=total_qty,
                               total_sum_no_discount=total_sum_no_discount,
                               total_sum_with_discount=total_sum_with_discount,
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


if __name__ == '__main__':
    app.run(debug=True)

