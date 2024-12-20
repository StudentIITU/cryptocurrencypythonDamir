from pyexpat import features
from urllib.parse import urlparse
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from passlib.hash import sha256_crypt
import psycopg2
from datetime import datetime, timedelta
import random
from sqlhelpers import Table, get_balance, send_money, get_db_connection, InsufficientFundsException, \
    InvalidTransactionException, get_transaction_history
from forms import RegisterForm, LoginForm, BuyForm, SendMoneyForm, SellForm

# Flask app configuration
app = Flask(__name__)
app.config.update(
    SECRET_KEY='dev_key_here',
    SESSION_COOKIE_SECURE=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_REFRESH_EACH_REQUEST=True
)

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'warning'
login_manager.session_protection = "strong"
login_manager.refresh_view = "login"
login_manager.needs_refresh_message = "Please login again to confirm your identity"
login_manager.needs_refresh_message_category = "info"


# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        print(f"Creating user object with data: {user_data}")  # Debug print
        self.id = str(user_data['username'])  # Must be username column
        self.name = user_data['name']
        self.email = user_data['email']
        self.username = user_data['username']
        self.balance = float(user_data.get('balance', 0.00))

    def get_id(self):
        print(f"get_id called, returning: {self.username}")  # Debug print
        return str(self.username)

@login_manager.user_loader
def load_user(user_id):
    print(f"Loading user with ID: {user_id}")
    try:
        with get_db_connection() as conn:
            users = Table(conn, "users", "name", "username", "email", "password", "balance")
            # Ensure we're querying by username column
            user_data = users.getone("username", user_id)
            if user_data:
                print(f"Found user data: {user_data['username']}")
                return User(user_data)
            print(f"No user found for username: {user_id}")
    except Exception as e:
        print(f"Error loading user: {e}")
    return None



# Database connection
try:
    conn = psycopg2.connect(
        host="localhost",
        database="crypto",
        user="postgres",
        password="postgres"  # Replace with your password
    )
except psycopg2.Error as e:
    print(f"Unable to connect to the database: {e}")
    conn = None


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        print(f"Login attempt with username: {username}")  # Debug print

        try:
            with get_db_connection() as conn:
                users = Table(conn, "users", "name", "username", "email", "password", "balance")
                user_data = users.getone("username", username)

                if user_data and sha256_crypt.verify(password, user_data['password']):
                    user = User(user_data)
                    # Store username, not email
                    result = login_user(user)
                    print(f"Login result: {result}")  # Debug print
                    print(f"User ID after login: {user.get_id()}")  # Debug print

                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))

                flash('Invalid username or password', 'danger')
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login error occurred', 'danger')

    return render_template('login.html')


@app.route("/dashboard")
@login_required
def dashboard():
    try:
        if not current_user.is_authenticated:
            return redirect(url_for('login'))

        print(f"Current user in dashboard: {current_user.username}")

        with get_db_connection() as conn:
            balance = get_balance(current_user.username, conn)

            # Generate price data
            end_date = datetime.now()
            dates = [(end_date - timedelta(days=i)).strftime('%Y-%m-%d')
                    for i in range(7, -1, -1)]
            prices = [round(random.uniform(10, 20), 2) for _ in range(8)]
            current_price = prices[-1]

            # Mock transaction data - replace with real data later
            transactions = [
                {
                    'date': datetime.now() - timedelta(hours=2),
                    'type': 'RECEIVED',
                    'amount': 50.0,
                    'status': 'COMPLETED'
                },
                {
                    'date': datetime.now() - timedelta(hours=5),
                    'type': 'SENT',
                    'amount': 25.0,
                    'status': 'PENDING'
                }
            ]

            return render_template(
                'dashboard.html',
                balance=balance,
                current_price=current_price,
                current_time=datetime.now().strftime("%I:%M %p"),
                dates=dates,
                prices=prices,
                transactions=transactions
            )
    except Exception as e:
        print(f"Dashboard error: {e}")  # Debug print
        flash('Error loading dashboard', 'danger')
        return redirect(url_for('login'))

# Add the missing routes
@app.route("/add-funds", methods=['GET', 'POST'])
@login_required
def add_funds():
    try:
        if request.method == 'POST':
            amount = float(request.form['amount'])
            # Add funds logic here
            flash('Funds added successfully!', 'success')
            return redirect(url_for('dashboard'))
        return render_template('add_funds.html')
    except Exception as e:
        flash('Error adding funds', 'danger')
        return redirect(url_for('dashboard'))

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegisterForm(request.form)
    if request.method == 'POST' and form.validate():
        try:
            name = form.name.data
            username = form.username.data
            email = form.email.data
            password = sha256_crypt.hash(form.password.data)

            if not conn:
                flash('Database connection error', 'danger')
                return render_template("register.html", form=form)

            users = Table(conn, "users", "name", "email", "username", "password", "balance")

            if users.getone("username", username):
                flash('Username already exists', 'danger')
                return render_template("register.html", form=form)

            if users.getone("email", email):
                flash('Email already registered', 'danger')
                return render_template("register.html", form=form)

            users.insert(name, email, username, password, 0.00)
            user_data = users.getone("username", username)
            user = User(user_data)
            login_user(user)
            session['logged_in'] = True
            session['username'] = username
            session['name'] = name
            flash('Registration successful!', 'success')
            return redirect(url_for('dashboard'))

        except Exception as e:
            flash(f'Registration failed: {str(e)}', 'danger')
            return render_template("register.html", form=form)

    return render_template("register.html", form=form)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    flash('You have been logged out', 'success')
    return redirect(url_for('login'))

@app.route("/check-session")
def check_session():
    return {
        "is_authenticated": current_user.is_authenticated if hasattr(current_user, 'is_authenticated') else False,
        "session": dict(session)
    }
@app.route('/')
def index():
    return render_template("index.html", year=datetime.now().year)


# In app.py

@app.route("/transaction", methods=['GET', 'POST'])
@login_required
def transaction():
    form = SendMoneyForm(request.form)

    try:
        with get_db_connection() as conn:
            balance = get_balance(current_user.username, conn)

            if request.method == 'POST':
                app.logger.info(f"Processing transaction request from {current_user.username}")
                app.logger.info(f"Form data: {request.form}")

                recipient = request.form.get('recipient')
                amount = request.form.get('amount')

                try:
                    # Process transaction
                    send_money(current_user.username, recipient, float(amount))

                    flash(f'Successfully sent {amount} DW to {recipient}', 'success')
                    return redirect(url_for('dashboard'))

                except InsufficientFundsException:
                    flash('Insufficient funds for this transaction.', 'error')
                except InvalidTransactionException as e:
                    flash(str(e), 'error')
                except Exception as e:
                    app.logger.error(f"Transaction error: {str(e)}")
                    flash('Transaction failed. Please try again.', 'error')

            return render_template('transaction.html', form=form, balance=balance)

    except Exception as e:
        app.logger.error(f"Transaction page error: {str(e)}")
        flash('Error loading transaction page', 'error')
        return redirect(url_for('dashboard'))
@app.route("/test-db")
def test_db():
    try:
        with get_db_connection() as conn:
            users = Table(conn, "users", "name", "email", "username", "password", "balance")
            all_users = users.getall()
            return f"Database connection successful. Found {len(all_users)} users."
    except Exception as e:
        return f"Database connection failed: {str(e)}"


@app.route('/buy', methods=['GET', 'POST'])
@login_required
def buy():
    form = BuyForm()
    if request.method == 'POST':
        try:
            amount = form.amount.data
            send_money("BANK", current_user.username, amount)
            flash(f'Successfully bought {amount} DamirWave', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(str(e), 'danger')

    return render_template('buy.html', form=form)


@app.route('/sell', methods=['GET', 'POST'])
@login_required
def sell():
    form = SellForm()
    if request.method == 'POST':
        try:
            amount = form.amount.data
            send_money(current_user.username, "BANK", amount)
            flash(f'Successfully sold {amount} DamirWave', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(str(e), 'danger')

    return render_template('sell.html', form=form)


def init_db():
    try:
        # Create users table if it doesn't exist
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    name VARCHAR(100),
                    email VARCHAR(100),
                    username VARCHAR(100) PRIMARY KEY,
                    password VARCHAR(100),
                    balance NUMERIC DEFAULT 0.0
                )
            """)

            # Create blockchain table if it doesn't exist
            cur.execute("""
                CREATE TABLE IF NOT EXISTS blockchain (
                    number VARCHAR(100),
                    hash VARCHAR(100),
                    previous VARCHAR(100),
                    data VARCHAR(100),
                    nonce VARCHAR(100)
                )
            """)
            conn.commit()
            print("Database tables initialized successfully")
    except Exception as e:
        print(f"Database initialization error: {e}")


if __name__ == '__main__':
    init_db()
    app.run(debug=True)