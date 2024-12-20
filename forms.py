from wtforms import Form, StringField, DecimalField, IntegerField, TextAreaField, PasswordField, validators
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Length, NumberRange


class RegisterForm(Form):
    name = StringField('Full Name', [validators.Length(min=1, max=50)])
    username = StringField('Username', [validators.Length(min=4, max=25)])
    email = StringField('Email', [validators.Length(min=6, max=50)])
    password = PasswordField('Password', [
        validators.DataRequired(),
        validators.EqualTo('confirm', message='Passwords do not match')
    ])
    confirm = PasswordField('Confirm Password')


class LoginForm(FlaskForm):
    username = StringField('Username',
        validators=[
            DataRequired(message="Username is required"),
            Length(min=4, max=25, message="Username must be between 4 and 25 characters")
        ])
    password = PasswordField('Password',
        validators=[
            DataRequired(message="Password is required")
        ])



class SendMoneyForm(Form):  # Change from FlaskForm to Form
    recipient = StringField('Recipient',
                          validators=[DataRequired(message="Recipient username is required")])
    amount = DecimalField('Amount',
                         validators=[
                             DataRequired(message="Amount is required"),
                             NumberRange(min=0.01, message="Amount must be greater than 0")
                         ])

class BuyForm(Form):
    amount = DecimalField('Amount', [validators.DataRequired(), validators.NumberRange(min=0.01)])


class SellForm(Form):
    amount = DecimalField('Amount', [validators.DataRequired(), validators.NumberRange(min=0.01)])