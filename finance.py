import csv
import os
from datetime import datetime
import io
from flask import (
    Flask,
    Response,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

# Secret key required for session management and user login
app.config['SECRET_KEY'] = 'your-secret-key-change-this-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finance.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- DATABASE MODELS ---


class User(UserMixin, db.Model):
  id = db.Column(db.Integer, primary_key=True)
  username = db.Column(db.String(80), unique=True, nullable=False)
  password_hash = db.Column(db.String(200), nullable=False)

  # Relationships to user-owned records
  transactions = db.relationship('Transaction', backref='owner', lazy=True)
  subscriptions = db.relationship('Subscription', backref='owner', lazy=True)
  monthly_summaries = db.relationship(
      'MonthlySummary', backref='owner', lazy=True
  )
  budgets = db.relationship('Budget', backref='owner', lazy=True)
  goals = db.relationship('Goal', backref='owner', lazy=True)

  def set_password(self, password):
    self.password_hash = generate_password_hash(password)

  def check_password(self, password):
    return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
  return User.query.get(int(user_id))


class Transaction(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  category = db.Column(db.String(50), nullable=False)
  amount = db.Column(db.Float, nullable=False)
  description = db.Column(db.String(200), nullable=False)
  date = db.Column(db.DateTime, default=datetime.utcnow)


class Subscription(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  name = db.Column(db.String(100), nullable=False)
  amount = db.Column(db.Float, nullable=False)
  due_date = db.Column(db.String(10), nullable=False)
  frequency = db.Column(db.String(20), default='Monthly')
  category = db.Column(db.String(50), nullable=False)


class MonthlySummary(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  month = db.Column(db.String(20), nullable=False)
  past_expenses = db.Column(db.Float, nullable=False, default=0.0)
  recurring_bills = db.Column(db.Float, nullable=False, default=0.0)
  total_spent = db.Column(db.Float, nullable=False, default=0.0)


class Budget(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  category = db.Column(db.String(50), nullable=False)
  monthly_limit = db.Column(db.Float, nullable=False, default=0.0)


class Goal(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
  title = db.Column(db.String(100), nullable=False)
  target_amount = db.Column(db.Float, nullable=False)
  target_date = db.Column(db.String(10), nullable=False)
  is_vacation = db.Column(db.Boolean, default=False)


class GoalLog(db.Model):
  id = db.Column(db.Integer, primary_key=True)
  goal_id = db.Column(db.Integer, db.ForeignKey('goal.id'), nullable=False)
  log_type = db.Column(db.String(20), nullable=False)
  category = db.Column(db.String(50), nullable=False)
  amount = db.Column(db.Float, nullable=False)
  description = db.Column(db.String(200), nullable=False)
  date = db.Column(db.DateTime, default=datetime.utcnow)


# --- HELPER FUNCTIONS ---


def get_due_status(due_date_str):
  try:
    due_date = datetime.strptime(due_date_str, '%Y-%m-%d').date()
    today = datetime.utcnow().date()
    days_left = (due_date - today).days

    if days_left < 0:
      return {'label': f'Overdue ({abs(days_left)}d ago)', 'class': 'danger'}
    elif days_left <= 7:
      return {'label': f'Due in {days_left}d', 'class': 'warning'}
    else:
      return {'label': f'In {days_left}d', 'class': 'info'}
  except ValueError:
    return {'label': 'Scheduled', 'class': 'info'}


# --- AUTHENTICATION ROUTES ---


@app.route('/signup', methods=['GET', 'POST'])
def signup():
  if request.method == 'POST':
    username = request.form['username'].strip()
    password = request.form['password']

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
      flash('Username already exists. Please pick another one.', 'error')
      return redirect(url_for('signup'))

    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    # Create default Vacation Goal for new user
    vacation = Goal(
        user_id=user.id,
        title='Vacation Goal',
        target_amount=3000.00,
        target_date='2026-12-31',
        is_vacation=True,
    )
    db.session.add(vacation)
    db.session.commit()

    login_user(user)
    return redirect(url_for('home'))

  return render_template('signup.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
  if request.method == 'POST':
    username = request.form['username'].strip()
    password = request.form['password']

    user = User.query.filter_by(username=username).first()
    if user and user.check_password(password):
      login_user(user)
      return redirect(url_for('home'))

    flash('Invalid username or password.', 'error')
    return redirect(url_for('login'))

  return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
  logout_user()
  return redirect(url_for('login'))


# --- USER-ISOLATED PAGE ROUTES ---


@app.route('/')
@login_required
def home():
  total_spent = (
      db.session.query(func.sum(Transaction.amount))
      .filter(Transaction.user_id == current_user.id)
      .scalar()
      or 0.00
  )
  total_recurring = (
      db.session.query(func.sum(Subscription.amount))
      .filter(Subscription.user_id == current_user.id)
      .scalar()
      or 0.00
  )

  recent_tx = (
      Transaction.query.filter_by(user_id=current_user.id)
      .order_by(Transaction.date.desc())
      .limit(5)
      .all()
  )
  subscriptions = (
      Subscription.query.filter_by(user_id=current_user.id)
      .order_by(Subscription.due_date.asc())
      .all()
  )

  subs_with_alerts = [
      {'data': s, 'status': get_due_status(s.due_date)} for s in subscriptions
  ]

  return render_template(
      'home.html',
      total_spent=total_spent,
      total_recurring=total_recurring,
      recent_tx=recent_tx,
      recent_subs=subs_with_alerts[:5],
  )


@app.route('/about')
def about():
  return render_template('about.html')


@app.route('/enter_expenses')
@login_required
def enter_expenses():
  return render_template('enter_expenses.html')


@app.route('/upcoming_bills')
@login_required
def upcoming_bills():
  subscriptions = (
      Subscription.query.filter_by(user_id=current_user.id)
      .order_by(Subscription.due_date.asc())
      .all()
  )
  subs_with_alerts = [
      {'data': s, 'status': get_due_status(s.due_date)} for s in subscriptions
  ]

  sub_category_query = (
      db.session.query(Subscription.category, func.sum(Subscription.amount))
      .filter(Subscription.user_id == current_user.id)
      .group_by(Subscription.category)
      .all()
  )
  sub_chart_categories = [row[0] for row in sub_category_query]
  sub_chart_amounts = [row[1] for row in sub_category_query]

  return render_template(
      'upcoming_bills.html',
      subscriptions=subs_with_alerts,
      sub_chart_categories=sub_chart_categories,
      sub_chart_amounts=sub_chart_amounts,
  )


@app.route('/past_expenses')
@login_required
def past_expenses():
  transactions = (
      Transaction.query.filter_by(user_id=current_user.id)
      .order_by(Transaction.date.desc())
      .all()
  )
  total_spent = sum(t.amount for t in transactions)

  category_query = (
      db.session.query(Transaction.category, func.sum(Transaction.amount))
      .filter(Transaction.user_id == current_user.id)
      .group_by(Transaction.category)
      .all()
  )
  chart_categories = [row[0] for row in category_query]
  chart_amounts = [row[1] for row in category_query]

  return render_template(
      'past_expenses.html',
      transactions=transactions,
      total_spent=total_spent,
      chart_categories=chart_categories,
      chart_amounts=chart_amounts,
  )


@app.route('/budgets')
@login_required
def budgets():
  default_categories = [
      'Food & Dining',
      'Utilities',
      'Entertainment',
      'Shopping',
      'Other',
  ]
  now = datetime.utcnow()
  current_month = now.month
  current_year = now.year

  budget_data = []
  for cat in default_categories:
    budget_record = Budget.query.filter_by(
        user_id=current_user.id, category=cat
    ).first()
    limit = budget_record.monthly_limit if budget_record else 0.00

    spent = (
        db.session.query(func.sum(Transaction.amount))
        .filter(
            Transaction.user_id == current_user.id,
            Transaction.category == cat,
            func.strftime('%m', Transaction.date) == f'{current_month:02d}',
            func.strftime('%Y', Transaction.date) == str(current_year),
        )
        .scalar()
        or 0.00
    )

    percent = (spent / limit * 100) if limit > 0 else 0
    budget_data.append({
        'category': cat,
        'limit': limit,
        'spent': spent,
        'remaining': limit - spent,
        'percent': min(percent, 100),
        'is_over': spent > limit if limit > 0 else False,
    })

  return render_template('budgets.html', budget_data=budget_data)


@app.route('/goals')
@login_required
def goals():
  all_goals = (
      Goal.query.filter_by(user_id=current_user.id)
      .order_by(Goal.is_vacation.desc(), Goal.id.asc())
      .all()
  )

  goal_cards = []
  for g in all_goals:
    logs = GoalLog.query.filter_by(goal_id=g.id).order_by(GoalLog.date.desc()).all()

    total_saved = (
        db.session.query(func.sum(GoalLog.amount))
        .filter_by(goal_id=g.id, log_type='contribution')
        .scalar()
        or 0.00
    )
    total_spent = (
        db.session.query(func.sum(GoalLog.amount))
        .filter_by(goal_id=g.id, log_type='expense')
        .scalar()
        or 0.00
    )

    left_to_save = max(g.target_amount - total_saved, 0.00)
    available_to_spend = max(total_saved - total_spent, 0.00)
    progress_percent = (
        min((total_saved / g.target_amount * 100), 100)
        if g.target_amount > 0
        else 0
    )

    goal_cards.append({
        'goal': g,
        'total_saved': total_saved,
        'left_to_save': left_to_save,
        'total_spent': total_spent,
        'available_to_spend': available_to_spend,
        'progress_percent': progress_percent,
        'logs': logs,
    })

  return render_template('goals.html', goal_cards=goal_cards)


@app.route('/monthly_totals')
@login_required
def monthly_totals():
  monthly_summaries = (
      MonthlySummary.query.filter_by(user_id=current_user.id)
      .order_by(MonthlySummary.id.desc())
      .all()
  )
  return render_template(
      'monthly_totals.html', monthly_summaries=monthly_summaries
  )


# --- USER ACTION ROUTES ---


@app.route('/add_transaction', methods=['POST'])
@login_required
def add_transaction():
  db.session.add(
      Transaction(
          user_id=current_user.id,
          category=request.form['category'],
          amount=float(request.form['amount']),
          description=request.form['description'],
      )
  )
  db.session.commit()
  return redirect(url_for('past_expenses'))


@app.route('/add_subscription', methods=['POST'])
@login_required
def add_subscription():
  db.session.add(
      Subscription(
          user_id=current_user.id,
          name=request.form['name'],
          amount=float(request.form['amount']),
          due_date=request.form['due_date'],
          frequency=request.form['frequency'],
          category=request.form['category'],
      )
  )
  db.session.commit()
  return redirect(url_for('upcoming_bills'))


@app.route('/edit_sub/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_sub(id):
  sub = Subscription.query.filter_by(
      id=id, user_id=current_user.id
  ).first_or_404()
  if request.method == 'POST':
    sub.name = request.form['name']
    sub.amount = float(request.form['amount'])
    sub.due_date = request.form['due_date']
    sub.frequency = request.form['frequency']
    sub.category = request.form['category']
    db.session.commit()
    return redirect(url_for('upcoming_bills'))
  return render_template('edit_subscription.html', sub=sub)


@app.route('/set_budget', methods=['POST'])
@login_required
def set_budget():
  category = request.form['category']
  limit = float(request.form['limit'])
  budget_record = Budget.query.filter_by(
      user_id=current_user.id, category=category
  ).first()

  if budget_record:
    budget_record.monthly_limit = limit
  else:
    db.session.add(
        Budget(user_id=current_user.id, category=category, monthly_limit=limit)
    )

  db.session.commit()
  return redirect(url_for('budgets'))


@app.route('/add_goal', methods=['POST'])
@login_required
def add_goal():
  db.session.add(
      Goal(
          user_id=current_user.id,
          title=request.form['title'],
          target_amount=float(request.form['target_amount']),
          target_date=request.form['target_date'],
          is_vacation=False,
      )
  )
  db.session.commit()
  return redirect(url_for('goals'))


@app.route('/update_goal/<int:id>', methods=['POST'])
@login_required
def update_goal(id):
  goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
  goal.title = request.form['title']
  goal.target_amount = float(request.form['target_amount'])
  goal.target_date = request.form['target_date']
  db.session.commit()
  return redirect(url_for('goals'))


@app.route('/add_goal_log/<int:goal_id>', methods=['POST'])
@login_required
def add_goal_log(goal_id):
  goal = Goal.query.filter_by(
      id=goal_id, user_id=current_user.id
  ).first_or_404()
  db.session.add(
      GoalLog(
          goal_id=goal.id,
          log_type=request.form['log_type'],
          amount=float(request.form['amount']),
          description=request.form['description'],
          category=request.form.get('category', 'General'),
      )
  )
  db.session.commit()
  return redirect(url_for('goals'))


@app.route('/add_monthly_summary', methods=['POST'])
@login_required
def add_monthly_summary():
  db.session.add(
      MonthlySummary(
          user_id=current_user.id,
          month=request.form['month'],
          past_expenses=float(request.form.get('past_expenses', 0.0)),
          recurring_bills=float(request.form.get('recurring_bills', 0.0)),
          total_spent=float(request.form.get('total_spent', 0.0)),
      )
  )
  db.session.commit()
  return redirect(url_for('monthly_totals'))


# --- EXPORT ROUTES ---


@app.route('/export/transactions')
@login_required
def export_transactions():
  transactions = (
      Transaction.query.filter_by(user_id=current_user.id)
      .order_by(Transaction.date.desc())
      .all()
  )
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(['ID', 'Date', 'Category', 'Description', 'Amount'])
  for t in transactions:
    writer.writerow([
        t.id,
        t.date.strftime('%Y-%m-%d %H:%M:%S'),
        t.category,
        t.description,
        f'{t.amount:.2f}',
    ])
  output.seek(0)
  return Response(
      output.getvalue(),
      mimetype='text/csv',
      headers={
          'Content-Disposition': 'attachment; filename=past_expenses.csv'
      },
  )


@app.route('/export/subscriptions')
@login_required
def export_subscriptions():
  subscriptions = (
      Subscription.query.filter_by(user_id=current_user.id)
      .order_by(Subscription.due_date.asc())
      .all()
  )
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(
      ['ID', 'Due Date', 'Service/Bill', 'Frequency', 'Category', 'Amount']
  )
  for s in subscriptions:
    writer.writerow(
        [s.id, s.due_date, s.name, s.frequency, s.category, f'{s.amount:.2f}']
    )
  output.seek(0)
  return Response(
      output.getvalue(),
      mimetype='text/csv',
      headers={
          'Content-Disposition': 'attachment; filename=upcoming_bills.csv'
      },
  )


@app.route('/export/monthly')
@login_required
def export_monthly():
  summaries = (
      MonthlySummary.query.filter_by(user_id=current_user.id)
      .order_by(MonthlySummary.id.desc())
      .all()
  )
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow([
      'ID',
      'Month',
      'Monthly Past Expenses',
      'Monthly Recurring Bills',
      'Total Spent',
  ])
  for m in summaries:
    writer.writerow([
        m.id,
        m.month,
        f'{m.past_expenses:.2f}',
        f'{m.recurring_bills:.2f}',
        f'{m.total_spent:.2f}',
    ])
  output.seek(0)
  return Response(
      output.getvalue(),
      mimetype='text/csv',
      headers={
          'Content-Disposition': 'attachment; filename=monthly_summaries.csv'
      },
  )


# --- DELETE ROUTES ---


@app.route('/delete_tx/<int:id>')
@login_required
def delete_tx(id):
  tx = Transaction.query.filter_by(
      id=id, user_id=current_user.id
  ).first_or_404()
  db.session.delete(tx)
  db.session.commit()
  return redirect(url_for('past_expenses'))


@app.route('/delete_sub/<int:id>')
@login_required
def delete_sub(id):
  sub = Subscription.query.filter_by(
      id=id, user_id=current_user.id
  ).first_or_404()
  db.session.delete(sub)
  db.session.commit()
  return redirect(url_for('upcoming_bills'))


@app.route('/delete_goal/<int:id>')
@login_required
def delete_goal(id):
  goal = Goal.query.filter_by(id=id, user_id=current_user.id).first_or_404()
  if not goal.is_vacation:
    GoalLog.query.filter_by(goal_id=goal.id).delete()
    db.session.delete(goal)
    db.session.commit()
  return redirect(url_for('goals'))


@app.route('/delete_goal_log/<int:id>')
@login_required
def delete_goal_log(id):
  log = GoalLog.query.get_or_404(id)
  if log.goal_id in [g.id for g in current_user.goals]:
    db.session.delete(log)
    db.session.commit()
  return redirect(url_for('goals'))


@app.route('/delete_monthly/<int:id>')
@login_required
def delete_monthly(id):
  ms = MonthlySummary.query.filter_by(
      id=id, user_id=current_user.id
  ).first_or_404()
  db.session.delete(ms)
  db.session.commit()
  return redirect(url_for('monthly_totals'))


with app.app_context():
  db.create_all()

if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
