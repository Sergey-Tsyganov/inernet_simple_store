from flask import Flask, render_template, request, session
from utils.captcha_generator import generate_captcha
from utils.google_api import read_sheet

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # для работы session


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
            return f"Добро пожаловать, {session['client_name']}! Скидка {session['discount']}%"
        else:
            captcha_text, captcha_path = generate_captcha()
            session['captcha_text'] = captcha_text
            return render_template('login.html', captcha=captcha_path, error='Неверный логин или пароль')

    captcha_text, captcha_path = generate_captcha()
    session['captcha_text'] = captcha_text
    return render_template('login.html', captcha=captcha_path)


if __name__ == '__main__':
    app.run(debug=True)
