# 📊 Personal Finance & Savings Goal Dashboard

A full-stack, multi-user web application built with **Flask**, **SQLAlchemy**, and **Chart.js** designed to track personal expenses, manage upcoming recurring bills, monitor category budgets, and save for major goals (like vacations) in an isolated environment per user account.

---

## ✨ Features

- **🔒 Multi-User Authentication:** Secure user signup and login with password hashing via `Werkzeug` and session management via `Flask-Login`. Each user account sees strictly their own financial records.
- **🏠 Summary Dashboard:** Overview of total logged expenses, upcoming recurring bill totals, and visual due-date alerts for payments arriving soon.
- **📝 Expense & Subscription Entry:** Simple forms to log daily purchases by category and record recurring subscriptions (e.g., Rent, Netflix) with renewal frequencies and next due dates.
- **⏰ Upcoming Bills & Alerts:** Automated due-date calculations that highlight bills due within 7 days or overdue payments.
- **📊 Interactive Category Pie Charts:** Visual breakdown of spending habits and subscription distributions powered by `Chart.js`.
- **🎯 Custom Savings Goals:** Dynamic goal tracker (featuring a default Vacation Goal) with progress bars, stat cards (*Total Saved*, *Left to Save*, *Total Spent*, and *Available to Spend*), and contribution logs.
- **💡 Monthly Category Budgets:** Set monthly caps per spending category with dynamic progress bars that turn red when spending exceeds budget caps.
- **📥 One-Click CSV Exports:** Download dynamic `.csv` spreadsheet backups of past expenses, recurring bills, and monthly summaries directly from your browser.

---

## 🛠️ Tech Stack

- **Backend:** Python 3, Flask, Flask-SQLAlchemy, Flask-Login
- **Database:** SQLite (development / production persistent storage)
- **WSGI Server:** Gunicorn
- **Frontend:** HTML5, Modern CSS Flexbox/Grid, Jinja2 Templates, Chart.js

---

## 🚀 Getting Started (Local Development)

### Prerequisites

- Python 3.10+
- `pip` package manager

### Installation

1. **Clone the repository:**
   ```bash
   git clone [https://github.com/YOUR_GITHUB_USERNAME/personal-finance-dashboard.git](https://github.com/YOUR_GITHUB_USERNAME/personal-finance-dashboard.git)
   cd personal-finance-dashboard
