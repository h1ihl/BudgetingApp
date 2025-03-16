from flask import Flask, render_template, request, redirect, url_for
from models import db, Transaction

app = Flask(__name__)

# Configure SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()  # Create database tables

@app.route('/')
def home():
    transactions = Transaction.query.all()
    return render_template('index.html', transactions=transactions)

@app.route('/add', methods=['GET', 'POST'])
def add_transaction():
    if request.method == 'POST':
        date = request.form.get('date')
        category = request.form.get('category')
        amount = request.form.get('amount')
        type_val = request.form.get('type')
        # Create a new Transaction record
        new_transaction = Transaction(date=date, category=category, amount=float(amount), type=type_val)
        db.session.add(new_transaction)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('add_transaction.html')

if __name__ == '__main__':
    app.run(debug=True)
