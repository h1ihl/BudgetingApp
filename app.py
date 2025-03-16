from flask import Flask, render_template, request, redirect, url_for
from models import db, Transaction
import plotly.express as px
import json
import io
import csv
from flask import make_response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import User
import datetime
from collections import defaultdict

app = Flask(__name__)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Configure SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your-unique-secret-key'

db.init_app(app)

with app.app_context():
    db.create_all()  # Create database tables

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
@login_required
def home():
    # Get the query parameters
    type_filter = request.args.get('type_filter', 'all').lower()
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)

    # Query only transactions for the logged-in user
    query = Transaction.query.filter_by(user_id=current_user.id)

    # Filter by type if specified
    if type_filter in ['income', 'expense']:
        query = query.filter(Transaction.type.ilike(type_filter))

    # Filter by date range if provided (assuming YYYY-MM-DD format)
    if start_date:
        query = query.filter(Transaction.date >= start_date)
    if end_date:
        query = query.filter(Transaction.date <= end_date)

    transactions = query.all()

    # Calculate summary stats
    total_income = sum(t.amount for t in transactions if t.type.lower() == 'income')
    total_expense = sum(t.amount for t in transactions if t.type.lower() == 'expense')
    net_balance = total_income - total_expense

    # Prepare data for Plotly bar chart (Income vs Expenses)
    chart_data = [
        {"category": "Income", "amount": total_income},
        {"category": "Expenses", "amount": total_expense}
    ]
    chart_json = json.dumps(chart_data, ensure_ascii=False)

    # Compute category breakdown for expenses (for pie chart)
    category_breakdown = {}
    for t in transactions:
        if t.type.lower() == 'expense':
            category = t.category
            if category in category_breakdown:
                category_breakdown[category] += t.amount
            else:
                category_breakdown[category] = t.amount

    # Prepare data for the pie chart
    category_data = [{"category": cat, "amount": amt} for cat, amt in category_breakdown.items()]
    category_json = json.dumps(category_data, ensure_ascii=False)

    # Compute monthly overview for a line chart
    monthly_totals = defaultdict(lambda: {"income": 0, "expense": 0})
    for t in transactions:
        try:
            dt = datetime.datetime.strptime(t.date, "%Y-%m-%d")
            month = dt.strftime("%Y-%m")
            if t.type.lower() == "income":
                monthly_totals[month]["income"] += t.amount
            elif t.type.lower() == "expense":
                monthly_totals[month]["expense"] += t.amount
        except Exception as e:
            print("Error parsing date:", t.date, e)

    sorted_months = sorted(monthly_totals.keys())
    line_chart_data = {
        "months": sorted_months,
        "income": [monthly_totals[m]["income"] for m in sorted_months],
        "expense": [monthly_totals[m]["expense"] for m in sorted_months],
    }
    line_chart_json = json.dumps(line_chart_data, ensure_ascii=False)

    print("DEBUG: Chart JSON Data:", chart_json)
    print("DEBUG: Category JSON Data:", category_json)
    print("DEBUG: Line Chart JSON Data:", line_chart_json)

    grouped_transactions = defaultdict(list)
    for t in transactions:
        month = t.date.strip()[:7]
        grouped_transactions[month].append(t)

    # No sorting or ascending
    sorted_grouped_transactions = dict(sorted(grouped_transactions.items(), reverse=True))

    return render_template(
        'index.html',
        transactions=transactions,
        grouped_transactions=sorted_grouped_transactions,  # New
        total_income=total_income,
        total_expense=total_expense,
        net_balance=net_balance,
        chart_json=chart_json,
        type_filter=type_filter,
        category_json=category_json,
        start_date=start_date,
        end_date=end_date,
        line_chart_json=line_chart_json
    )

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_transaction():
    if request.method == 'POST':
        date = request.form.get('date')
        category = request.form.get('category')
        amount = request.form.get('amount')
        type_val = request.form.get('type')
        new_transaction = Transaction(
            date=date,
            category=category,
            amount=float(amount),
            type=type_val,
            user_id=current_user.id  # Associate transaction with current user
        )
        db.session.add(new_transaction)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('add_transaction.html')

@app.route('/delete/<int:transaction_id>', methods=['GET'])
@login_required
def delete_transaction(transaction_id):
    transaction_to_delete = Transaction.query.get_or_404(transaction_id)
    if transaction_to_delete.user_id != current_user.id:
        return "You are not authorized to delete this transaction", 403
    db.session.delete(transaction_to_delete)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/edit/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.user_id != current_user.id:
        return "You are not authorized to edit this transaction", 403
    if request.method == 'POST':
        transaction.date = request.form.get('date')
        transaction.category = request.form.get('category')
        transaction.amount = float(request.form.get('amount'))
        transaction.type = request.form.get('type')
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('edit_transaction.html', transaction=transaction)

@app.route('/export')
def export_csv():
    # Optionally, you can also apply filtering by type here if needed.
    transactions = Transaction.query.all()

    # Create an in-memory text stream to write CSV data.
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV header
    writer.writerow(["ID", "Date", "Category", "Amount", "Type"])

    # Write data rows
    for t in transactions:
        writer.writerow([t.id, t.date, t.category, t.amount, t.type])

    # Create a response with the CSV data, and set headers for file download.
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=transactions.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            return "Username already exists"  # You can improve error handling
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('home'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('home'))
        else:
            return "Invalid username or password"  # Improve with proper error messages
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        # Update password if provided
        new_password = request.form.get('new_password')
        if new_password:
            current_user.set_password(new_password)
            db.session.commit()
            return redirect(url_for('profile'))
    return render_template('profile.html', user=current_user)

if __name__ == '__main__':
    app.run(debug=True)
