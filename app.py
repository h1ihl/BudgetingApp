from flask import Flask, render_template, request, redirect, url_for
from models import db, Transaction
import plotly.express as px
import json
import io
import csv
from flask import make_response

app = Flask(__name__)

# Configure SQLite Database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///budget.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()  # Create database tables


@app.route('/')
def home():
    # Get the query parameter, e.g., ?type_filter=income
    type_filter = request.args.get('type_filter', 'all').lower()

    # Query all transactions
    query = Transaction.query

    # Filter if 'income' or 'expense' is selected
    if type_filter in ['income', 'expense']:
        query = query.filter(Transaction.type.ilike(type_filter))

    transactions = query.all()

    # Calculate summary stats
    total_income = sum(t.amount for t in transactions if t.type.lower() == 'income')
    total_expense = sum(t.amount for t in transactions if t.type.lower() == 'expense')
    net_balance = total_income - total_expense

    # Prepare data for Plotly chart
    chart_data = [
        {"category": "Income", "amount": total_income},
        {"category": "Expenses", "amount": total_expense}
    ]
    chart_json = json.dumps(chart_data, ensure_ascii=False)

    print("DEBUG: Chart JSON Data:", chart_json)

    return render_template(
        'index.html',
        transactions=transactions,
        total_income=total_income,
        total_expense=total_expense,
        net_balance=net_balance,
        chart_json=chart_json,
        type_filter=type_filter  # Pass the current filter to the template
    )

@app.route('/add', methods=['GET', 'POST'])
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
            type=type_val
        )
        db.session.add(new_transaction)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('add_transaction.html')

# NEW: Route to delete a transaction by ID
@app.route('/delete/<int:transaction_id>', methods=['GET'])
def delete_transaction(transaction_id):
    transaction_to_delete = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction_to_delete)
    db.session.commit()
    return redirect(url_for('home'))

@app.route('/edit/<int:transaction_id>', methods=['GET', 'POST'])
def edit_transaction(transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
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

if __name__ == '__main__':
    app.run(debug=True)
