from datetime import date, datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user

app = Flask(__name__)
app.secret_key = 'Donttellthistoanyone'


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@app.context_processor
def inject_user():
    return dict(current_user=current_user)



class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id       = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.Text, nullable=False, unique=True)
    email    = db.Column(db.Text, nullable=False)
    password = db.Column(db.Text, nullable=False)

    transactions = db.relationship('Transaction', backref='owner', lazy=True)


class Transaction(db.Model):
    __tablename__ = 'transactions'

    id       = db.Column(db.Integer, primary_key=True)
    title    = db.Column(db.Text, nullable=False)
    amount   = db.Column(db.Float, nullable=False)
    type     = db.Column(db.Text, nullable=False)
    category = db.Column(db.Text, nullable=False, default='Other')
    date     = db.Column(db.Text, nullable=False)
    notes    = db.Column(db.Text, default='')

    user_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)


class History(db.Model):
    __tablename__ = 'history'

    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.Text, nullable=False)
    amount     = db.Column(db.Float, nullable=False)
    type       = db.Column(db.Text, nullable=False)
    category   = db.Column(db.Text, nullable=False, default='Other')
    date       = db.Column(db.Text, nullable=False)
    notes      = db.Column(db.Text, default='')
    deleted_at = db.Column(db.Text, default=lambda: datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))

    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)





@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email    = request.form['email']
        password = generate_password_hash(request.form['password'])

        if User.query.filter_by(username=username).first():
            flash('Username already exists.')
        else:
            new_user = User(username=username, email=email, password=password)
            db.session.add(new_user)
            db.session.commit()
            flash('Account created! Please log in.')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Wrong username or password.')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))




@app.route('/')
@app.route('/index')
@login_required
def index():
    today = date.today()
    month = int(request.args.get('month', 0))
    year = int(request.args.get('year', 0))
    no_month_filter = (month == 0)
    filter_type = request.args.get('type', 'all')
    filter_category= request.args.get('category', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')

    query = Transaction.query.filter_by(user_id=current_user.id)

    if not no_month_filter:

        query = query.filter(
            db.func.strftime('%m', Transaction.date) == str(month).zfill(2),
            db.func.strftime('%Y', Transaction.date) == str(year)
        )

    if filter_type != 'all':
        query = query.filter_by(type=filter_type)

    if filter_category != 'all':
        query = query.filter_by(category=filter_category)

    if date_from:
        query = query.filter(Transaction.date >= date_from)

    if date_to:
        query = query.filter(Transaction.date <= date_to)

    transactions = query.order_by(Transaction.date.desc()).all()

    total_income   = sum(t.amount for t in transactions if t.type == 'income')
    total_expenses = sum(t.amount for t in transactions if t.type == 'expense')
    balance        = max(0, total_income - total_expenses)

    return render_template('index.html',
                           transactions=transactions,
                           total_income=total_income,
                           total_expenses=total_expenses,
                           balance=balance,
                           month=month,
                           year=year,
                           no_month_filter=no_month_filter,
                           filter_type=filter_type,
                           filter_category=filter_category,
                           date_from=date_from,
                           date_to=date_to)




@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        txn = Transaction(
            title    = request.form['title'],
            amount   = float(request.form['amount']),
            type     = request.form['type'],
            category = request.form['category'],
            date     = request.form['date'],
            notes    = request.form.get('notes', ''),
            user_id  = current_user.id
        )
        db.session.add(txn)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('add.html')


@app.route('/delete/<int:id>')
@login_required
def delete(id):
    txn = Transaction.query.filter_by(id=id, user_id=current_user.id).first()
    if txn:
        record = History(
            title      = txn.title,
            amount     = txn.amount,
            type       = txn.type,
            category   = txn.category,
            date       = txn.date,
            notes      = txn.notes,
            user_id    = current_user.id
        )
        db.session.add(record)
        db.session.delete(txn)
        db.session.commit()

    return redirect(url_for('index'))


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    txn = Transaction.query.filter_by(id=id, user_id=current_user.id).first_or_404()

    if request.method == 'POST':
        txn.title    = request.form['title']
        txn.amount   = float(request.form['amount'])
        txn.type     = request.form['type']
        txn.category = request.form['category']
        txn.date     = request.form['date']
        txn.notes    = request.form.get('notes', '')

        db.session.commit()
        return redirect(url_for('index'))

    return render_template('edit.html', trn=txn)


@app.route('/history')
@login_required
def history():
    records = History.query.filter_by(user_id=current_user.id)\
                           .order_by(History.date.desc()).all()
    return render_template('history.html', records=records)




if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5001)