from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp

class RegistrationForm(FlaskForm):
    username = StringField('Логин', validators=[
        DataRequired(),
        Length(min=3, max=50)
    ])

    password = PasswordField('Пароль', validators=[
        DataRequired(),
        Length(min=5)
    ])

    password_confirm = PasswordField('Повторите пароль', validators=[
        DataRequired(),
        EqualTo('password', message='Пароли не совпадают.')
    ])

    company = StringField('Название организации', validators=[DataRequired()])
    address = StringField('Адрес', validators=[DataRequired()])
    phone = StringField('Телефон', validators=[
        DataRequired(),
        Regexp(r'^\+?\d{10,15}$', message='Введите корректный номер телефона.')
    ])

    email = StringField('Email', validators=[
        DataRequired(),
        Email(message='Введите корректный email.')
    ])

    submit = SubmitField('Зарегистрироваться')
