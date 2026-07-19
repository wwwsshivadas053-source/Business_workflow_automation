from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import os
import re
import json

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bpa_suite_secret_key_129837")

# Database URI configuration: Check for Render environment variable, otherwise fallback to SQLite
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Render and other platforms sometimes use postgres://, which SQLAlchemy 1.4+ no longer supports
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    db_url = "sqlite:///bpa_suite.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

app.jinja_env.globals.update(min=min, max=max)

# ----------------------------------------------------
# Initialize database on first request (covers production deployments where __main__ is not executed)
# ----------------------------------------------------
@app.before_first_request
def initialize_database():
    # Create tables if they don't exist
    db.create_all()
    # Seed with default data only if empty
    seed_database()

# ----------------------------------------------------
# Models
# ----------------------------------------------------

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(100), nullable=False) # Admin, HR, Manager, Employee
    department = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.Text, nullable=True)
    gross_pay = db.Column(db.Float, default=0.0)
    deductions = db.Column(db.Float, default=0.0)
    net_pay = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(50), default="Ready") # Ready, On Hold, Review Required, Paid
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    attendance_logs = db.relationship('AttendanceLog', backref='employee', lazy=True, cascade="all, delete-orphan")
    leave_requests = db.relationship('LeaveRequest', backref='employee', lazy=True, cascade="all, delete-orphan")
    expense_claims = db.relationship('ExpenseClaim', backref='employee', lazy=True, cascade="all, delete-orphan")


class AttendanceLog(db.Model):
    __tablename__ = 'attendance_logs'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    check_in_time = db.Column(db.String(20), nullable=False) # e.g. "08:58 AM"
    check_out_time = db.Column(db.String(20), nullable=True) # e.g. "06:12 PM"
    status = db.Column(db.String(50), nullable=False) # On Time, Late, Absent


class LeaveRequest(db.Model):
    __tablename__ = 'leave_requests'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    leave_type = db.Column(db.String(50), nullable=False) # Annual Leave, Sick Leave, Personal, Unpaid
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), default="Pending") # Pending, Approved, Rejected
    approver = db.Column(db.String(100), nullable=True) # Sarah Chen, Auto-Optimizer, System Policy


class Invoice(db.Model):
    __tablename__ = 'invoices'
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(50), unique=True, nullable=False)
    vendor = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default="Review") # Extracting, Review, Validated, Flagged
    payment_status = db.Column(db.String(50), default="Pending") # Pending, Paid, Void


class ExpenseClaim(db.Model):
    __tablename__ = 'expense_claims'
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(100), nullable=False) # Travel & Lodging, Meals & Entertainment, etc.
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(50), default="Pending") # Reviewing, Approved, Rejected
    receipt_url = db.Column(db.Text, nullable=True)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    action = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100), nullable=False) # System, Security, Payroll, Invoice, Attendance
    user_email = db.Column(db.String(120), nullable=True)


def log_activity(action, category, user_email=None):
    try:
        log = ActivityLog(action=action, category=category, user_email=user_email)
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Logging error: {e}")

# ----------------------------------------------------
# Database Seeding Logic
# ----------------------------------------------------

def seed_database():
    # Only seed if no employees exist
    if Employee.query.first() is not None:
        return

    print("Seeding database...")
    
    default_pass_hash = generate_password_hash("password123")
    
    # 1. Add Employees
    admin = Employee(
        name="Admin User",
        role="Admin",
        department="IT",
        email="admin@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDCpHwGgsbtNeP2K11cc8PQ4UOQpk9YGhNnj3us_z7wZZJ1ZIUe6iGAbyXibMZ9Sz_p8yZbUOPf27lV4Yk_O5GjfkPxqae66G0oHXHJCDf-j-xq1_St6isLCvPtUV77eiGsx33YaTyQFPU8-HOfzsE57LnDJtC4WnBPTV-FKpI99_qqQTRxyVE6L_ku8wTTPRNKAq1QVDoJ2kAptw9_poWpmlrDAH1sKpNN4oitnq_xQ7QC1OxMY3YksQ",
        gross_pay=15000.00,
        deductions=3000.00,
        net_pay=12000.00,
        status="Ready"
    )
    hr = Employee(
        name="HR Specialist",
        role="HR",
        department="HR",
        email="hr@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDCpHwGgsbtNeP2K11cc8PQ4UOQpk9YGhNnj3us_z7wZZJ1ZIUe6iGAbyXibMZ9Sz_p8yZbUOPf27lV4Yk_O5GjfkPxqae66G0oHXHJCDf-j-xq1_St6isLCvPtUV77eiGsx33YaTyQFPU8-HOfzsE57LnDJtC4WnBPTV-FKpI99_qqQTRxyVE6L_ku8wTTPRNKAq1QVDoJ2kAptw9_poWpmlrDAH1sKpNN4oitnq_xQ7QC1OxMY3YksQ",
        gross_pay=8500.00,
        deductions=1500.00,
        net_pay=7000.00,
        status="Ready"
    )
    manager = Employee(
        name="Team Manager",
        role="Manager",
        department="Engineering",
        email="manager@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDCpHwGgsbtNeP2K11cc8PQ4UOQpk9YGhNnj3us_z7wZZJ1ZIUe6iGAbyXibMZ9Sz_p8yZbUOPf27lV4Yk_O5GjfkPxqae66G0oHXHJCDf-j-xq1_St6isLCvPtUV77eiGsx33YaTyQFPU8-HOfzsE57LnDJtC4WnBPTV-FKpI99_qqQTRxyVE6L_ku8wTTPRNKAq1QVDoJ2kAptw9_poWpmlrDAH1sKpNN4oitnq_xQ7QC1OxMY3YksQ",
        gross_pay=11000.00,
        deductions=2000.00,
        net_pay=9000.00,
        status="Ready"
    )
    sarah = Employee(
        name="Sarah Jenkins",
        role="Employee",
        department="Engineering",
        email="sarah.jenkins@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDfk-1rzbDNIFCLAq_wKyRuXs_TYDxxfFwNe2C5yQAn5Wdb4IPPcL8ie6jk0PCclJ4ZyAMF8NIsDJZ-U4dbIYC2CvjZU7JJn2Ny1O8FJoBhHcg--QYwVreM-GVVEZ-5ajJB4kvp_-8448mIdEvAzxsR-0UpcoooK7eJQON5pBtDdm1un9uRSi8UL3D6AZm8Guu98Na5oYJmIm6DAcxjU08pDUsuM-PivIknylxVc118cIeZFHSmFAi5XA",
        gross_pay=12450.00,
        deductions=2860.00,
        net_pay=9590.00,
        status="Ready"
    )
    michael = Employee(
        name="Michael Chen",
        role="Employee",
        department="Product",
        email="michael.chen@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuCy3h4Fi63n_sbbwP87N72-R0v7UhbQdIXgGvYp5is_pvg94Io_kqXFlFaT_cpp3oJqwvJqh9EaqvBgd2MwCvaRNAtxemczhoeZ8Nmq7YmlFpLle5cL9JU_EynEsI4kDyXeZ-7_OCd4rlq8d3jpanYF-MwUv0fV2uPUQiqDpIR2kakVzAaGQOt2gZgZ_kLlMYOnhRT_N_gcyXQds-cYcaopQkTTNK9KOAyOBIifCV2gn7AVEB4I52f20w",
        gross_pay=8200.00,
        deductions=1150.00,
        net_pay=7050.00,
        status="On Hold"
    )
    elena = Employee(
        name="Elena Rodriguez",
        role="Employee",
        department="Marketing",
        email="elena.rodriguez@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuAE2cwU-QsmnP5X9qPtqIAH3FCFU97ppYCWnMyV13xnDsGpapR2l8V9VHTnRjAXYp739sHKynQw_zpdJKGCahS6uR1XqzzNEv22I-JeNlZyN4D7eo0D4k2yKkdcermUNLmQ4YQRmLsX6tgpxWkpSGdFB_nWmYCbirqIZObClozVotQ0SYOpTNd0l-m0ixxHEqv3ukSpKj59vqPvDVPdjBZUUavLqjBRopPYY5elGejbKuA3CCj19o511A",
        gross_pay=9800.00,
        deductions=1420.00,
        net_pay=8380.00,
        status="Ready"
    )
    david = Employee(
        name="David Thompson",
        role="Employee",
        department="Sales",
        email="david.thompson@bpasuite.com",
        password_hash=default_pass_hash,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuAI94eW7kqvwwqisZ5Yg5dmbFRThzFQKCgyDDp43AAVCTt0BMcsbYXrpc2GJ674IyBMhm5Th0n6lU6NKo0vRNzfoHW3A_IgP7nk2EhyNSfWSW4jdS_e933S5DozqxI9FrlOASB3aYT9b6NjS0NBfLkskJezB5MBoANfkSi031GBhwdSwy4SOQihaG8KIjTmlrEyqsQFoAFfXtvNie-mOxUSJCS4WzZt3PJPiJXQjjIzE32nTHqil5agYg",
        gross_pay=15200.00,
        deductions=3100.00,
        net_pay=12100.00,
        status="Review Required"
    )

    db.session.add_all([admin, hr, manager, sarah, michael, elena, david])
    db.session.commit()

    # 2. Add Attendance Logs (For Sarah Jenkins as the primary user mockup context)
    logs = [
        AttendanceLog(employee_id=sarah.id, date=date(2023, 10, 20), check_in_time="08:58 AM", check_out_time="06:05 PM", status="On Time"),
        AttendanceLog(employee_id=sarah.id, date=date(2023, 10, 19), check_in_time="09:02 AM", check_out_time="06:10 PM", status="On Time"),
        AttendanceLog(employee_id=sarah.id, date=date(2023, 10, 18), check_in_time="09:15 AM", check_out_time="05:55 PM", status="Late"),
        AttendanceLog(employee_id=sarah.id, date=date(2023, 10, 17), check_in_time="08:55 AM", check_out_time="06:15 PM", status="On Time"),
        AttendanceLog(employee_id=sarah.id, date=date(2023, 10, 16), check_in_time="09:01 AM", check_out_time="06:00 PM", status="On Time"),
        AttendanceLog(employee_id=sarah.id, date=date(2023, 10, 13), check_in_time="08:45 AM", check_out_time="06:30 PM", status="On Time")
    ]
    db.session.add_all(logs)

    # 3. Add Leave Requests (For Sarah Jenkins)
    leaves = [
        LeaveRequest(employee_id=sarah.id, leave_type="Annual Leave", start_date=date(2023, 10, 12), end_date=date(2023, 10, 14), reason="Family trip", status="Pending", approver="Sarah Chen"),
        LeaveRequest(employee_id=sarah.id, leave_type="Sick Leave", start_date=date(2023, 9, 4), end_date=date(2023, 9, 4), reason="Dental appointment", status="Approved", approver="Auto-Optimizer"),
        LeaveRequest(employee_id=sarah.id, leave_type="Annual Leave", start_date=date(2023, 8, 15), end_date=date(2023, 8, 19), reason="Summer break request", status="Rejected", approver="System Policy"),
        LeaveRequest(employee_id=sarah.id, leave_type="Annual Leave", start_date=date(2023, 7, 1), end_date=date(2023, 7, 5), reason="Personal time off", status="Approved", approver="Sarah Chen")
    ]
    db.session.add_all(leaves)

    # 4. Add Invoices
    invoices = [
        Invoice(invoice_number="INV-2024-001", vendor="Acme Corp", amount=1240.00, date=date(2023, 10, 12), due_date=date(2023, 11, 12), status="Extracting"),
        Invoice(invoice_number="GT-99281", vendor="Global Tech", amount=45000.00, date=date(2023, 10, 15), due_date=date(2023, 11, 15), status="Review"),
        Invoice(invoice_number="SV-AX-8", vendor="Stellar Venture", amount=3420.50, date=date(2023, 10, 18), due_date=date(2023, 11, 18), status="Validated"),
        Invoice(invoice_number="LD-2023-F", vendor="Lunar Designs", amount=890.00, date=date(2023, 10, 20), due_date=date(2023, 11, 20), status="Flagged")
    ]
    db.session.add_all(invoices)

    # 5. Add Expense Claims (For Sarah Jenkins)
    expenses = [
        ExpenseClaim(
            employee_id=sarah.id,
            title="Hotel Stay - NYC",
            category="Travel & Lodging",
            amount=845.20,
            date=date(2023, 10, 24),
            status="Reviewing",
            receipt_url="https://lh3.googleusercontent.com/aida-public/AB6AXuCH1r5OEQ6Nz5vZaoP0TK6SkbJZTxzew7gp-sLUhiDb0hIEkUOdQi2QFRadIDtOFaLKvGBgxHgJltFSKqKiKFUf9FWqojxUFpM5Xd02G64opXYZJGVKF7KyAnMYiClu1vPcf0y6rFe3tamc-DjeDjS_I6qdI5XbjVjS_sI_cRDTHYSrKjziqcWRF8XknLjt-N7lpMLwNCKHPKJiXEgwz91iM1ainjZoEZA9z26jvnntbjmq5ffV2Xcx9w"
        ),
        ExpenseClaim(
            employee_id=sarah.id,
            title="Client Lunch",
            category="Meals & Entertainment",
            amount=124.00,
            date=date(2023, 10, 22),
            status="Approved",
            receipt_url="https://lh3.googleusercontent.com/aida-public/AB6AXuBzsXBfjMNav0bgmW-PxtKx4oTXcDne1_tM5hJcnDamyMj_ICOC81lkPNNQGatcEVls8X7hJD4c_TJoh1r5AVrRUqmGGhWY5TnvS86aDmYK98au9q2-FnqbEaJjdH-Mb8L0YzjJNFGNyK_dZiFd9GC4jWjV3a3sYkP88iI1C8UHw00aowZ-yNSgh10XHcQVlSMgN1FjEYVtXC2fXwnfTiUHwMvgRgjwQ7fj3lHI2YSQqvt8HWVTQ-KAuw"
        ),
        ExpenseClaim(
            employee_id=sarah.id,
            title="Cloud API License",
            category="Software & Tools",
            amount=299.99,
            date=date(2023, 10, 20),
            status="Rejected",
            receipt_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDGPMJ5FnO1p15elfedbhmdEcHrlqybXJcvGiiJRW_Srm88TFxUQrnvvawqJ0Q5R5urst7_1yFsqctLxhrUYI51b16pqm51mmAre_YYlIszmZkMHbP5Ch7vSBlkzdsvmzMp5fdioDUYcaPuazrbbTsonybNlizAzGalSLkEJw5Rf9WkqmL9MhXzJxCWa4bxRIa2hl3MoW9P2afw9QonvEnGvFgTGXWTJgDyWkurSB1zXhhQauxh7w_gsA"
        ),
        ExpenseClaim(
            employee_id=sarah.id,
            title="Flight: SFO - LHR",
            category="Travel & Lodging",
            amount=1250.00,
            date=date(2023, 10, 18),
            status="Approved",
            receipt_url="https://lh3.googleusercontent.com/aida-public/AB6AXuCyy48y6pE-9KdeUjv2lvxUjoqAXbUH09yEHOL6mDaTX_lwU5z_Iqd9dQMulpwbwLm04D_S751v_cTNHtz5Yb-m2D51j4HDmKz0T7qmwclgK6gS-oY6pMaHZ8kiHGemGUkIZQ6ho5tRIpXGuWIl7XUCJ5gIu84GuXACvhDCKynVOOYPFEI-gwlCac6AkB4wrycJo3cry6am0vhMOSWK0K7fb2Vdqafw9U2KYhrOzL3fRRIgnRryzwS76Q"
        )
    ]
    db.session.add_all(expenses)
    db.session.commit()

    # Seed mock activity logs
    logs_activity = [
        ActivityLog(action="System database initialized and seeded", category="System", user_email="system@bpasuite.com"),
        ActivityLog(action="OCR processing verified 4 invoice extractions", category="Invoice", user_email="system@bpasuite.com"),
        ActivityLog(action="Admin profile generated for admin@bpasuite.com", category="Security", user_email="admin@bpasuite.com"),
        ActivityLog(action="HR profile generated for hr@bpasuite.com", category="Security", user_email="hr@bpasuite.com")
    ]
    db.session.add_all(logs_activity)
    db.session.commit()
    print("Database seeded successfully.")

# ----------------------------------------------------
# Authentication Decorators & Views
# ----------------------------------------------------

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            user = Employee.query.get(session['user_id'])
            if not user or user.role not in roles:
                flash("You do not have permission to view that page.", "danger")
                if user:
                    if user.role == 'Admin':
                        return redirect(url_for('admin_dashboard'))
                    elif user.role == 'HR':
                        return redirect(url_for('payroll'))
                    elif user.role == 'Manager':
                        return redirect(url_for('leave'))
                    else:
                        return redirect(url_for('attendance'))
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

@app.context_processor
def inject_user():
    user = None
    if 'user_id' in session:
        user = Employee.query.get(session['user_id'])
    return dict(current_user=user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = request.form.get('remember')
        
        user = Employee.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            if remember:
                session.permanent = True
            flash(f"Welcome back, {user.name}!", "success")
            
            # Role based redirection
            if user.role == 'Admin':
                return redirect(url_for('admin_dashboard'))
            elif user.role == 'HR':
                return redirect(url_for('payroll'))
            elif user.role == 'Manager':
                return redirect(url_for('leave'))
            else:
                return redirect(url_for('attendance'))
        else:
            flash("Invalid email or password. Please try again.", "danger")
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash("You have been signed out.", "info")
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        role = request.form.get('role')
        department = request.form.get('department')
        password = request.form.get('password')
        
        existing = Employee.query.filter_by(email=email).first()
        if existing:
            flash("This email address is already registered.", "danger")
            return redirect(url_for('register'))
            
        pass_hash = generate_password_hash(password)
        new_emp = Employee(
            name=name,
            role=role,
            department=department,
            email=email,
            password_hash=pass_hash,
            gross_pay=5000.0,
            deductions=500.0,
            net_pay=4500.0,
            status="Ready",
            avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDCpHwGgsbtNeP2K11cc8PQ4UOQpk9YGhNnj3us_z7wZZJ1ZIUe6iGAbyXibMZ9Sz_p8yZbUOPf27lV4Yk_O5GjfkPxqae66G0oHXHJCDf-j-xq1_St6isLCvPtUV77eiGsx33YaTyQFPU8-HOfzsE57LnDJtC4WnBPTV-FKpI99_qqQTRxyVE6L_ku8wTTPRNKAq1QVDoJ2kAptw9_poWpmlrDAH1sKpNN4oitnq_xQ7QC1OxMY3YksQ"
        )
        db.session.add(new_emp)
        db.session.commit()
        
        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))
        
    return render_template('register.html')

simulated_otps = {}

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        user = Employee.query.filter_by(email=email).first()
        if user:
            simulated_otps[email] = "123456"
            flash("A password reset OTP '123456' has been simulated for your email address.", "success")
            return redirect(url_for('reset_password'))
        else:
            flash("No account associated with that email was found.", "danger")
            
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        otp = request.form.get('otp')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for('reset_password'))
            
        email_found = None
        for email, stored_otp in simulated_otps.items():
            if stored_otp == otp:
                email_found = email
                break
                
        if email_found:
            user = Employee.query.filter_by(email=email_found).first()
            if user:
                user.password_hash = generate_password_hash(password)
                db.session.commit()
                del simulated_otps[email_found]
                flash("Your password has been reset successfully. Please log in.", "success")
                return redirect(url_for('login'))
        
        flash("Invalid OTP verification code. Please try again.", "danger")
        
    return render_template('reset_password.html')

# ----------------------------------------------------
# Routes & Views
# ----------------------------------------------------

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = Employee.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
        
    if user.role == 'Admin':
        return redirect(url_for('admin_dashboard'))
    elif user.role == 'HR':
        return redirect(url_for('payroll'))
    elif user.role == 'Manager':
        return redirect(url_for('leave'))
    else:
        return redirect(url_for('attendance'))


@app.route('/payroll')
@login_required
def payroll():
    employees = Employee.query.all()
    # Mock data for top bar and summary stats
    current_cycle = "Cycle: Oct 01 - Oct 31, 2026"
    return render_template('payroll_automation_dashboard.html', 
                           employees=employees, 
                           current_cycle=current_cycle,
                           page="payroll")


@app.route('/attendance')
@login_required
def attendance():
    user = Employee.query.get(session['user_id'])
    logs = AttendanceLog.query.filter_by(employee_id=user.id).order_by(AttendanceLog.date.desc()).all()
    
    # Calculate consistency & stats
    total_days = len(logs)
    on_time_count = sum(1 for log in logs if log.status == "On Time")
    late_count = sum(1 for log in logs if log.status == "Late")
    absent_count = sum(1 for log in logs if log.status == "Absent")
    
    consistency = int((on_time_count / total_days * 100)) if total_days > 0 else 100
    
    # Determine clock state based on today's logs
    today = date.today()
    today_log = AttendanceLog.query.filter_by(employee_id=user.id, date=today).first()
    clocked_in = today_log is not None and today_log.check_out_time is None
    
    logs_data = []
    for l in logs:
        logs_data.append({
            "date": l.date.strftime('%Y-%m-%d'),
            "status": l.status,
            "check_in": l.check_in_time,
            "check_out": l.check_out_time or ""
        })
    logs_json = json.dumps(logs_data)
    
    return render_template('employee_attendence_system.html', 
                           logs=logs, 
                           logs_json=logs_json,
                           employee=user,
                           on_time_count=on_time_count,
                           late_count=late_count,
                           absent_count=absent_count,
                           consistency=consistency,
                           clocked_in=clocked_in,
                           page="attendance")


@app.route('/leave', methods=['GET', 'POST'])
@login_required
def leave():
    user = Employee.query.get(session['user_id'])
        
    if request.method == 'POST':
        leave_type = request.form.get('leave_type')
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        reason = request.form.get('reason')
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # Submit to database
            new_leave = LeaveRequest(
                employee_id=user.id,
                leave_type=leave_type,
                start_date=start_date,
                end_date=end_date,
                reason=reason,
                status="Pending",
                approver="Auto-Optimizer"
            )
            db.session.add(new_leave)
            db.session.commit()
            flash("Leave request submitted successfully!")
        except Exception as e:
            flash(f"Error submitting request: {str(e)}")
            
        return redirect(url_for('leave'))
        
    leaves = LeaveRequest.query.filter_by(employee_id=user.id).order_by(LeaveRequest.start_date.desc()).all()
    
    # Calculate leave balances dynamically based on approved leaves YTD
    approved_leaves = [l for l in leaves if l.status == "Approved"]
    annual_approved = sum((l.end_date - l.start_date).days + 1 for l in approved_leaves if l.leave_type == "Annual Leave")
    sick_approved = sum((l.end_date - l.start_date).days + 1 for l in approved_leaves if l.leave_type == "Sick Leave")
    personal_approved = sum((l.end_date - l.start_date).days + 1 for l in approved_leaves if "Personal" in l.leave_type)
    
    annual_leave_balance = max(0.0, 18.5 - annual_approved)
    sick_leave_used = 12 + sick_approved
    personal_leave_balance = max(0, 4 - personal_approved)
    
    # Simple count for visual dashboard
    pending_count = sum(1 for l in leaves if l.status == "Pending")
    
    return render_template('leave_approval_workflow.html', 
                           leaves=leaves, 
                           employee=user,
                           pending_count=pending_count,
                           annual_leave_balance=annual_leave_balance,
                           sick_leave_used=sick_leave_used,
                           personal_leave_balance=personal_leave_balance,
                           page="leave")


@app.route('/invoices')
@login_required
def invoices():
    inv_list = Invoice.query.order_by(Invoice.date.desc()).all()
    
    pending_approval = sum(1 for inv in inv_list if inv.status in ["Review", "Extracting"])
    extracted_today = sum(1 for inv in inv_list if inv.date == date.today()) or 142
    
    return render_template('invoice_processing_automation.html', 
                           invoices=inv_list, 
                           pending_approval=pending_approval,
                           extracted_today=extracted_today,
                           page="invoices")


@app.route('/expenses', methods=['GET', 'POST'])
@login_required
def expenses():
    user = Employee.query.get(session['user_id'])
        
    if request.method == 'POST':
        category = request.form.get('category')
        amount_str = request.form.get('amount')
        title = request.form.get('title', f"Expense: {category}")
        
        try:
            amount = float(amount_str)
            new_expense = ExpenseClaim(
                employee_id=user.id,
                title=title,
                category=category,
                amount=amount,
                date=date.today(),
                status="Reviewing",
                receipt_url="https://lh3.googleusercontent.com/aida-public/AB6AXuDGPMJ5FnO1p15elfedbhmdEcHrlqybXJcvGiiJRW_Srm88TFxUQrnvvawqJ0Q5R5urst7_1yFsqctLxhrUYI51b16pqm51mmAre_YYlIszmZkMHbP5Ch7vSBlkzdsvmzMp5fdioDUYcaPuazrbbTsonybNlizAzGalSLkEJw5Rf9WkqmL9MhXzJxCWa4bxRIa2hl3MoW9P2afw9QonvEnGvFgTGXWTJgDyWkurSB1zXhhQauxh7w_gsA"
            )
            db.session.add(new_expense)
            db.session.commit()
            flash("Expense claim submitted successfully!")
        except Exception as e:
            flash(f"Error submitting claim: {str(e)}")
            
        return redirect(url_for('expenses'))
        
    claims = ExpenseClaim.query.filter_by(employee_id=user.id).order_by(ExpenseClaim.date.desc()).all()
    
    # Reimbursement metrics
    reimbursed_this_month = sum(c.amount for c in claims if c.status == "Approved")
    pending_claims_amount = sum(c.amount for c in claims if c.status in ["Pending", "Reviewing"])
    pending_count = sum(1 for c in claims if c.status in ["Pending", "Reviewing"])
    
    return render_template('expense_reimbursement_build.html', 
                           claims=claims, 
                           reimbursed_this_month=reimbursed_this_month,
                           pending_claims_amount=pending_claims_amount,
                           pending_count=pending_count,
                           employee=user,
                           page="expenses")


@app.route('/settings')
@login_required
def settings():
    user = Employee.query.get(session['user_id'])
    return render_template('settings.html', employee=user, page="settings")


@app.route('/support')
@login_required
def support():
    user = Employee.query.get(session['user_id'])
    return render_template('support.html', employee=user, page="support")

# ----------------------------------------------------
# API Endpoint for Clock-In / Clock-Out Interaction
# ----------------------------------------------------

@app.route('/api/clock-in-out', methods=['POST'])
@login_required
def clock_in_out():
    user = Employee.query.get(session['user_id'])
        
    today = date.today()
    log = AttendanceLog.query.filter_by(employee_id=user.id, date=today).first()
    
    now_str = datetime.now().strftime("%I:%M %p")
    
    if not log:
        current_time = datetime.now()
        nine_fifteen = datetime.now().replace(hour=9, minute=15, second=0, microsecond=0)
        status = "On Time" if current_time <= nine_fifteen else "Late"
        
        new_log = AttendanceLog(
            employee_id=user.id,
            date=today,
            check_in_time=now_str,
            status=status
        )
        db.session.add(new_log)
        db.session.commit()
        return jsonify({"success": True, "state": "Clocked In", "time": now_str, "status": status})
    elif log.check_out_time is None:
        log.check_out_time = now_str
        db.session.commit()
        return jsonify({"success": True, "state": "Clocked Out", "time": now_str})
    else:
        log.check_out_time = None
        db.session.commit()
        return jsonify({"success": True, "state": "Clocked In", "time": log.check_in_time})

@app.route('/api/run-payroll', methods=['POST'])
@login_required
def run_payroll():
    user = Employee.query.get(session['user_id'])
    if user.role not in ['Admin', 'HR']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    employees = Employee.query.all()
    updated_count = 0
    for emp in employees:
        if emp.status == "Ready":
            emp.status = "Paid"
            updated_count += 1
    db.session.commit()
    log_activity(f"Payroll run successfully. Disbursed payments to {updated_count} employees.", "Payroll", user.email)
    return jsonify({"success": True, "count": updated_count})

@app.route('/api/employee/update-status/<int:id>', methods=['POST'])
@login_required
def api_update_employee_status(id):
    user = Employee.query.get(session['user_id'])
    if user.role not in ['Admin', 'HR']:
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    emp = Employee.query.get_or_404(id)
    data = request.get_json() or {}
    status = data.get('status')
    if status in ['Ready', 'On Hold', 'Review Required', 'Paid']:
        emp.status = status
        db.session.commit()
        log_activity(f"HR/Admin updated employee status for {emp.name} to {status}", "Payroll", user.email)
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid status"}), 400

@app.route('/api/upload-invoice', methods=['POST'])
def upload_invoice():
    import random
    vendors = ["Amazon Web Services", "Google Cloud", "Slack Technologies", "Github Inc", "Zoom Video"]
    vendor = random.choice(vendors)
    inv_num = f"INV-2026-{random.randint(100, 999)}"
    amount = round(random.uniform(150.0, 4500.0), 2)
    
    new_invoice = Invoice(
        invoice_number=inv_num,
        vendor=vendor,
        amount=amount,
        date=date.today(),
        due_date=date.today() + timedelta(days=30),
        status="Extracting"
    )
    db.session.add(new_invoice)
    db.session.commit()
    return jsonify({"success": True})

# ----------------------------------------------------
# Profile Settings & CSV Exports
# ----------------------------------------------------

@app.route('/settings/update', methods=['POST'])
@login_required
def settings_update():
    user = Employee.query.get(session['user_id'])
    name = request.form.get('name')
    email = request.form.get('email')
    
    if name:
        user.name = name
    if email:
        user.email = email
        
    if 'avatar' in request.files:
        file = request.files['avatar']
        if file and file.filename != '':
            uploads_dir = os.path.join(app.root_path, 'static', 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            filename = f"avatar_{user.id}_{int(datetime.now().timestamp())}.png"
            filepath = os.path.join(uploads_dir, filename)
            file.save(filepath)
            user.avatar_url = f"/static/uploads/{filename}"
            
    db.session.commit()
    log_activity(f"User updated profile details (name: {user.name})", "Security", user.email)
    flash("Profile updated successfully!", "success")
    return redirect(url_for('settings'))


@app.route('/api/export/<module>')
@login_required
def export_csv(module):
    import io, csv
    from flask import Response
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    filename = f"{module}_export.csv"
    
    if module == "employees":
        writer.writerow(["ID", "Name", "Role", "Department", "Email", "Gross Pay", "Deductions", "Net Pay", "Status", "Created At"])
        for emp in Employee.query.all():
            writer.writerow([emp.id, emp.name, emp.role, emp.department, emp.email, emp.gross_pay, emp.deductions, emp.net_pay, emp.status, emp.created_at])
    elif module == "attendance":
        writer.writerow(["ID", "Employee ID", "Employee Name", "Date", "Check-In", "Check-Out", "Status"])
        for log in AttendanceLog.query.all():
            writer.writerow([log.id, log.employee_id, log.employee.name if log.employee else '', log.date, log.check_in_time, log.check_out_time, log.status])
    elif module == "leaves":
        writer.writerow(["ID", "Employee ID", "Employee Name", "Leave Type", "Start Date", "End Date", "Reason", "Status", "Approver"])
        for req in LeaveRequest.query.all():
            writer.writerow([req.id, req.employee_id, req.employee.name if req.employee else '', req.leave_type, req.start_date, req.end_date, req.reason, req.status, req.approver])
    elif module == "invoices":
        writer.writerow(["ID", "Invoice Number", "Vendor", "Amount", "Date", "Due Date", "Status", "Payment Status"])
        for inv in Invoice.query.all():
            writer.writerow([inv.id, inv.invoice_number, inv.vendor, inv.amount, inv.date, inv.due_date, inv.status, inv.payment_status])
    elif module == "expenses":
        writer.writerow(["ID", "Employee ID", "Employee Name", "Title", "Category", "Amount", "Date", "Status"])
        for c in ExpenseClaim.query.all():
            writer.writerow([c.id, c.employee_id, c.employee.name if c.employee else '', c.title, c.category, c.amount, c.date, c.status])
    else:
        return "Invalid module", 400
        
    user = Employee.query.get(session['user_id'])
    log_activity(f"Exported CSV report for {module}", "System", user.email)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )


# ----------------------------------------------------
# Admin Dashboard & CRUD Endpoints
# ----------------------------------------------------

@app.route('/admin')
@roles_required('Admin')
def admin_dashboard():
    user = Employee.query.get(session['user_id'])
    employees = Employee.query.all()
    attendance_logs = AttendanceLog.query.order_by(AttendanceLog.date.desc()).all()
    leave_requests = LeaveRequest.query.order_by(LeaveRequest.start_date.desc()).all()
    invoices = Invoice.query.order_by(Invoice.date.desc()).all()
    expenses = ExpenseClaim.query.order_by(ExpenseClaim.date.desc()).all()
    activity_logs = ActivityLog.query.order_by(ActivityLog.timestamp.desc()).all()
    
    # Summary Metrics
    total_employees = len(employees)
    clocked_in_today = AttendanceLog.query.filter_by(date=date.today(), check_out_time=None).count()
    pending_leaves = LeaveRequest.query.filter_by(status="Pending").count()
    pending_invoices = Invoice.query.filter_by(status="Review").count()
    total_payroll = sum(emp.net_pay for emp in employees if emp.status == "Paid")
    pending_expenses = ExpenseClaim.query.filter_by(status="Reviewing").count()
    
    return render_template('admin_dashboard.html',
                           employees=employees,
                           attendance_logs=attendance_logs,
                           leave_requests=leave_requests,
                           invoices=invoices,
                           expenses=expenses,
                           activity_logs=activity_logs,
                           total_employees=total_employees,
                           clocked_in_today=clocked_in_today,
                           pending_leaves=pending_leaves,
                           pending_invoices=pending_invoices,
                           total_payroll=total_payroll,
                           pending_expenses=pending_expenses,
                           current_user=user,
                           page="admin")

# --- Employee CRUD ---
@app.route('/admin/employee/add', methods=['POST'])
@roles_required('Admin')
def admin_employee_add():
    name = request.form.get('name')
    role = request.form.get('role')
    department = request.form.get('department')
    email = request.form.get('email')
    gross_pay = float(request.form.get('gross_pay', 0.0) or 0.0)
    deductions = float(request.form.get('deductions', 0.0) or 0.0)
    net_pay = gross_pay - deductions
    
    new_emp = Employee(
        name=name, role=role, department=department, email=email,
        password_hash=generate_password_hash("password123"),
        gross_pay=gross_pay, deductions=deductions, net_pay=net_pay,
        avatar_url="https://lh3.googleusercontent.com/aida-public/AB6AXuCy3h4Fi63n_sbbwP87N72-R0v7UhbQdIXgGvYp5is_pvg94Io_kqXFlFaT_cpp3oJqwvJqh9EaqvBgd2MwCvaRNAtxemczhoeZ8Nmq7YmlFpLle5cL9JU_EynEsI4kDyXeZ-7_OCd4rlq8d3jpanYF-MwUv0fV2uPUQiqDpIR2kakVzAaGQOt2gZgZ_kLlMYOnhRT_N_gcyXQds-cYcaopQkTTNK9KOAyOBIifCV2gn7AVEB4I52f20w",
        status="Ready"
    )
    db.session.add(new_emp)
    db.session.commit()
    flash("Employee added successfully!")
    return redirect(url_for('admin_dashboard', tab="employees"))

@app.route('/admin/employee/edit/<int:id>', methods=['POST'])
@roles_required('Admin')
def admin_employee_edit(id):
    emp = Employee.query.get_or_404(id)
    emp.name = request.form.get('name')
    emp.role = request.form.get('role')
    emp.department = request.form.get('department')
    emp.email = request.form.get('email')
    emp.gross_pay = float(request.form.get('gross_pay', 0.0) or 0.0)
    emp.deductions = float(request.form.get('deductions', 0.0) or 0.0)
    emp.net_pay = emp.gross_pay - emp.deductions
    emp.status = request.form.get('status', emp.status)
    db.session.commit()
    flash("Employee updated successfully!")
    return redirect(url_for('admin_dashboard', tab="employees"))

@app.route('/admin/employee/delete/<int:id>')
@roles_required('Admin')
def admin_employee_delete(id):
    emp = Employee.query.get_or_404(id)
    db.session.delete(emp)
    db.session.commit()
    flash("Employee deleted successfully!")
    return redirect(url_for('admin_dashboard', tab="employees"))

# --- Attendance CRUD ---
@app.route('/admin/attendance/add', methods=['POST'])
@roles_required('Admin')
def admin_attendance_add():
    employee_id = int(request.form.get('employee_id'))
    log_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    check_in = request.form.get('check_in_time')
    check_out = request.form.get('check_out_time')
    status = request.form.get('status')
    
    new_log = AttendanceLog(
        employee_id=employee_id, date=log_date,
        check_in_time=check_in, check_out_time=check_out or None,
        status=status
    )
    db.session.add(new_log)
    db.session.commit()
    flash("Attendance log added!")
    return redirect(url_for('admin_dashboard', tab="attendance"))

@app.route('/admin/attendance/edit/<int:id>', methods=['POST'])
@roles_required('Admin')
def admin_attendance_edit(id):
    log = AttendanceLog.query.get_or_404(id)
    log.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    log.check_in_time = request.form.get('check_in_time')
    log.check_out_time = request.form.get('check_out_time') or None
    log.status = request.form.get('status')
    db.session.commit()
    flash("Attendance log updated!")
    return redirect(url_for('admin_dashboard', tab="attendance"))

@app.route('/admin/attendance/delete/<int:id>')
@roles_required('Admin')
def admin_attendance_delete(id):
    log = AttendanceLog.query.get_or_404(id)
    db.session.delete(log)
    db.session.commit()
    flash("Attendance log deleted!")
    return redirect(url_for('admin_dashboard', tab="attendance"))

# --- Leave Approval & CRUD ---
@app.route('/admin/leave/approve/<int:id>')
@roles_required('Admin')
def admin_leave_approve(id):
    req = LeaveRequest.query.get_or_404(id)
    req.status = "Approved"
    req.approver = "Admin User"
    db.session.commit()
    flash("Leave request approved!")
    return redirect(url_for('admin_dashboard', tab="leaves"))

@app.route('/admin/leave/reject/<int:id>')
@roles_required('Admin')
def admin_leave_reject(id):
    req = LeaveRequest.query.get_or_404(id)
    req.status = "Rejected"
    req.approver = "Admin User"
    db.session.commit()
    flash("Leave request rejected!")
    return redirect(url_for('admin_dashboard', tab="leaves"))

@app.route('/admin/leave/delete/<int:id>')
@roles_required('Admin')
def admin_leave_delete(id):
    req = LeaveRequest.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash("Leave request deleted!")
    return redirect(url_for('admin_dashboard', tab="leaves"))

# --- Invoice CRUD ---
@app.route('/admin/invoice/add', methods=['POST'])
@roles_required('Admin')
def admin_invoice_add():
    vendor = request.form.get('vendor')
    inv_num = request.form.get('invoice_number')
    amount = float(request.form.get('amount', 0.0) or 0.0)
    inv_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None
    status = request.form.get('status', 'Review')
    payment_status = request.form.get('payment_status', 'Pending')
    
    new_inv = Invoice(
        vendor=vendor, invoice_number=inv_num, amount=amount,
        date=inv_date, due_date=due_date, status=status, payment_status=payment_status
    )
    db.session.add(new_inv)
    db.session.commit()
    flash("Invoice created!")
    return redirect(url_for('admin_dashboard', tab="invoices"))

@app.route('/admin/invoice/edit/<int:id>', methods=['POST'])
@roles_required('Admin')
def admin_invoice_edit(id):
    inv = Invoice.query.get_or_404(id)
    inv.vendor = request.form.get('vendor')
    inv.invoice_number = request.form.get('invoice_number')
    inv.amount = float(request.form.get('amount', 0.0) or 0.0)
    inv.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    inv.due_date = datetime.strptime(request.form.get('due_date'), '%Y-%m-%d').date() if request.form.get('due_date') else None
    inv.status = request.form.get('status')
    inv.payment_status = request.form.get('payment_status')
    db.session.commit()
    flash("Invoice updated!")
    return redirect(url_for('admin_dashboard', tab="invoices"))

@app.route('/admin/invoice/approve/<int:id>')
@roles_required('Admin')
def admin_invoice_approve(id):
    inv = Invoice.query.get_or_404(id)
    inv.status = "Validated"
    inv.payment_status = "Paid"
    db.session.commit()
    flash("Invoice payment approved & paid!")
    return redirect(url_for('admin_dashboard', tab="invoices"))

@app.route('/admin/invoice/delete/<int:id>')
@roles_required('Admin')
def admin_invoice_delete(id):
    inv = Invoice.query.get_or_404(id)
    db.session.delete(inv)
    db.session.commit()
    flash("Invoice deleted!")
    return redirect(url_for('admin_dashboard', tab="invoices"))

# --- Payroll CRUD ---
@app.route('/admin/payroll/edit/<int:id>', methods=['POST'])
@roles_required('Admin')
def admin_payroll_edit(id):
    emp = Employee.query.get_or_404(id)
    emp.gross_pay = float(request.form.get('gross_pay', 0.0) or 0.0)
    emp.deductions = float(request.form.get('deductions', 0.0) or 0.0)
    emp.net_pay = emp.gross_pay - emp.deductions
    emp.status = request.form.get('status', emp.status)
    db.session.commit()
    flash("Payroll settings updated!")
    return redirect(url_for('admin_dashboard', tab="payroll"))

@app.route('/admin/payroll/delete/<int:id>')
@roles_required('Admin')
def admin_payroll_delete(id):
    emp = Employee.query.get_or_404(id)
    emp.gross_pay = 0.0
    emp.deductions = 0.0
    emp.net_pay = 0.0
    emp.status = "Review Required"
    db.session.commit()
    flash("Payroll salary settings reset!")
    return redirect(url_for('admin_dashboard', tab="payroll"))

@app.route('/payroll/payslip/<int:id>')
@login_required
def payroll_payslip(id):
    user = Employee.query.get(session['user_id'])
    emp = Employee.query.get_or_404(id)
    if user.role not in ['Admin', 'HR'] and user.id != emp.id:
        flash("You do not have permission to view that payslip.", "danger")
        return redirect(url_for('home'))
    return f"""
    <html>
    <head>
        <title>Payslip - {emp.name}</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
        <style>body {{ font-family: 'Inter', sans-serif; }}</style>
    </head>
    <body class="bg-gray-100 p-8 flex justify-center">
        <div class="bg-white max-w-2xl w-full p-8 rounded-xl shadow-lg border border-gray-200">
            <div class="flex justify-between items-start border-b pb-6 mb-6">
                <div>
                    <h1 class="text-2xl font-bold text-gray-800">BPA Suite Inc.</h1>
                    <p class="text-sm text-gray-500">100 Enterprise Way, Suite 400</p>
                </div>
                <div class="text-right">
                    <h2 class="text-lg font-bold text-blue-600">OFFICIAL PAYSLIP</h2>
                    <p class="text-sm text-gray-500">Pay Period: October 2023</p>
                </div>
            </div>
            
            <div class="grid grid-cols-2 gap-4 mb-8">
                <div>
                    <h3 class="text-xs font-bold text-gray-400 uppercase">Employee Details</h3>
                    <p class="font-semibold text-gray-700">{emp.name}</p>
                    <p class="text-sm text-gray-500">{emp.role} - {emp.department}</p>
                    <p class="text-sm text-gray-500">{emp.email}</p>
                </div>
                <div class="text-right">
                    <h3 class="text-xs font-bold text-gray-400 uppercase">Statement Summary</h3>
                    <p class="text-sm text-gray-500">Status: <span class="font-bold text-green-600">{emp.status}</span></p>
                    <p class="text-sm text-gray-500">Date Generated: {date.today().strftime('%B %d, %Y')}</p>
                </div>
            </div>
            
            <div class="border-t border-b py-4 mb-6">
                <div class="flex justify-between font-bold text-gray-700 mb-2">
                    <span>Description</span>
                    <span>Amount</span>
                </div>
                <div class="flex justify-between text-sm text-gray-600 mb-1">
                    <span>Basic Gross Earnings</span>
                    <span>${emp.gross_pay:,.2f}</span>
                </div>
                <div class="flex justify-between text-sm text-gray-600 mb-1 border-b pb-2">
                    <span>Tax & Statutory Deductions</span>
                    <span class="text-red-500">-${emp.deductions:,.2f}</span>
                </div>
                <div class="flex justify-between font-bold text-lg text-gray-800 pt-2">
                    <span>Net Disbursed Pay</span>
                    <span class="text-blue-600">${emp.net_pay:,.2f}</span>
                </div>
            </div>
            
            <div class="text-center text-xs text-gray-400 mt-12">
                This is a computer-generated document and requires no physical signature.<br/>
                <button onclick="window.print()" class="mt-4 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 print:hidden transition-all font-semibold">Print / Download PDF</button>
            </div>
        </div>
    </body>
    </html>
    """

# --- Expense CRUD ---
@app.route('/admin/expense/add', methods=['POST'])
@roles_required('Admin')
def admin_expense_add():
    employee_id = int(request.form.get('employee_id'))
    title = request.form.get('title')
    category = request.form.get('category')
    amount = float(request.form.get('amount', 0.0) or 0.0)
    exp_date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    status = request.form.get('status', 'Reviewing')
    
    new_exp = ExpenseClaim(
        employee_id=employee_id, title=title, category=category,
        amount=amount, date=exp_date, status=status,
        receipt_url="https://lh3.googleusercontent.com/aida-public/AB6AXuCH1r5OEQ6Nz5vZaoP0TK6SkbJZTxzew7gp-sLUhiDb0hIEkUOdQi2QFRadIDtOFaLKvGBgxHgJltFSKqKiKFUf9FWqojxUFpM5Xd02G64opXYZJGVKF7KyAnMYiClu1vPcf0y6rFe3tamc-DjeDjS_I6qdI5XbjVjS_sI_cRDTHYSrKjziqcWRF8XknLjt-N7lpMLwNCKHPKJiXEgwz91iM1ainjZoEZA9z26jvnntbjmq5ffV2Xcx9w"
    )
    db.session.add(new_exp)
    db.session.commit()
    flash("Expense claim created!")
    return redirect(url_for('admin_dashboard', tab="expenses"))

@app.route('/admin/expense/edit/<int:id>', methods=['POST'])
@roles_required('Admin')
def admin_expense_edit(id):
    claim = ExpenseClaim.query.get_or_404(id)
    claim.title = request.form.get('title')
    claim.category = request.form.get('category')
    claim.amount = float(request.form.get('amount', 0.0) or 0.0)
    claim.date = datetime.strptime(request.form.get('date'), '%Y-%m-%d').date()
    claim.status = request.form.get('status')
    db.session.commit()
    flash("Expense claim updated!")
    return redirect(url_for('admin_dashboard', tab="expenses"))

@app.route('/admin/expense/approve/<int:id>')
@roles_required('Admin')
def admin_expense_approve(id):
    claim = ExpenseClaim.query.get_or_404(id)
    claim.status = "Approved"
    db.session.commit()
    flash("Expense claim approved!")
    return redirect(url_for('admin_dashboard', tab="expenses"))

@app.route('/admin/expense/reject/<int:id>')
@roles_required('Admin')
def admin_expense_reject(id):
    claim = ExpenseClaim.query.get_or_404(id)
    claim.status = "Rejected"
    db.session.commit()
    flash("Expense claim rejected!")
    return redirect(url_for('admin_dashboard', tab="expenses"))

@app.route('/admin/expense/delete/<int:id>')
@roles_required('Admin')
def admin_expense_delete(id):
    claim = ExpenseClaim.query.get_or_404(id)
    db.session.delete(claim)
    db.session.commit()
    flash("Expense claim deleted!")
    return redirect(url_for('admin_dashboard', tab="expenses"))

@app.route('/docs/<doc_id>')
@login_required
def view_doc(doc_id):
    docs_data = {
        "attendance": {
            "title": "Attendance Policies v1.2",
            "content": """
            <h3 class="text-lg font-bold text-primary mb-sm">Grace Period</h3>
            <p class="text-on-surface-variant mb-md">A grace period of 15 minutes is applied to all corporate office schedules. The official start time is 09:00 AM, making the absolute check-in cutoff 09:15 AM. Any clock-in recorded at 09:16 AM or later will be automatically flagged by the system as "Late".</p>
            <h3 class="text-lg font-bold text-primary mb-sm">Consecutive Absences</h3>
            <p class="text-on-surface-variant mb-md">Employees are required to notify their direct managers and HR specialists of any unexpected absences before 10:00 AM on the day of occurrence. Consecutive absences exceeding 3 business days without valid medical documentation (e.g. sick leave note) will trigger an automatic policy review.</p>
            <h3 class="text-lg font-bold text-primary mb-sm">Weekend and Public Holidays</h3>
            <p class="text-on-surface-variant mb-md">Work hours completed over weekends or designated public holidays require pre-approval from department heads to qualify for standard overtime multipliers.</p>
            """
        },
        "expenses": {
            "title": "Expense Claim Submission Guide",
            "content": """
            <h3 class="text-lg font-bold text-primary mb-sm">Submission Window</h3>
            <p class="text-on-surface-variant mb-md">All business expenses must be submitted within 30 calendar days of the transaction date. Claims submitted past the 30-day window are subject to internal audit and eventual rejection.</p>
            <h3 class="text-lg font-bold text-primary mb-sm">Required Documentation</h3>
            <p class="text-on-surface-variant mb-md">A clear digital upload of the physical or electronic receipt is mandatory for all expense claims. Receipts must clearly display the vendor name, date of purchase, itemized breakdown of goods/services, and final amount. Credit card statements alone do not suffice.</p>
            <h3 class="text-lg font-bold text-primary mb-sm">Expense Limits</h3>
            <ul class="list-disc pl-md text-on-surface-variant mb-md space-y-xs">
              <li><strong>Travel & Lodging</strong>: Domestic lodging is capped at $250.00/night. International lodging limits vary by city tiers.</li>
              <li><strong>Meals & Entertainment</strong>: Client lunches are capped at $75.00/person. Internal team meals are capped at $25.00/person.</li>
              <li><strong>Software & Tools</strong>: Any recurring software licenses or cloud platform expenses require manager sign-off prior to claim submission.</li>
            </ul>
            """
        },
        "invoices": {
            "title": "AI Invoice Processing FAQ",
            "content": """
            <h3 class="text-lg font-bold text-primary mb-sm">How does the AI OCR extractor work?</h3>
            <p class="text-on-surface-variant mb-md">BPA Suite uses LLM-Optimizer v2.4 to parse incoming invoice documents. It automatically extracts the vendor name, invoice number, line items, taxable amounts, total due, invoice date, and due date. This process typically takes under 15 seconds.</p>
            <h3 class="text-lg font-bold text-primary mb-sm">What causes a "Flagged" status?</h3>
            <p class="text-on-surface-variant mb-md">An invoice is flagged if the AI processor encounters a high variance during extraction (e.g. illegible text, unrecognized layout, or data discrepancy) or if the confidence score falls below 80%. Flagged invoices must be corrected manually by the finance department.</p>
            <h3 class="text-lg font-bold text-primary mb-sm">Approval and Disbursal Workflow</h3>
            <p class="text-on-surface-variant mb-md">Once validated, invoices enter a multi-stage approval flow: AI Extraction -> Finance Review -> Department Manager Approval -> Treasury Disbursement. Standard disbursal terms are Net 30 days unless specified otherwise in vendor agreements.</p>
            """
        }
    }
    
    doc = docs_data.get(doc_id)
    if not doc:
        flash("Document not found.", "warning")
        return redirect(url_for('support'))

# ----------------------------------------------------
# Error Handlers
# ----------------------------------------------------

@app.errorhandler(500)
def internal_error(error):
    # Log the error for debugging purposes
    log_activity(f"Internal server error: {error}", "System", None)
    # Render a user-friendly error page
    return render_template('500.html'), 500
        
    return render_template('doc_viewer.html', doc=doc, doc_id=doc_id, page="support")

# ----------------------------------------------------
# Main Application Startup
# ----------------------------------------------------

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        seed_database()
    # Use the PORT environment variable provided by Render (default to 5000 for local development)
    port = int(os.getenv('PORT', 5000))
    # Disable debug mode in production; can be overridden by DEBUG env variable
    debug_mode = os.getenv('DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
