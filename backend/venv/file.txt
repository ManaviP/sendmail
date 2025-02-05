from dotenv import load_dotenv
load_dotenv()

from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
from werkzeug.security import generate_password_hash, check_password_hash
from cryptography.fernet import Fernet
import pandas as pd
import os
import smtplib
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from oauth2client.service_account import ServiceAccountCredentials
import gspread
from openpyxl import load_workbook
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime, timedelta
import pytz
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import openai
import bcrypt
import requests
import jwt
import logging
from models import db, Email
import time

# App Configuration
app = Flask(__name__)
CORS(app)
openai.api_key = os.getenv("OPENAI_API_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "supersecretkey")  # For JWT

# Initialize database and Marshmallow
db = SQLAlchemy(app)
ma = Marshmallow(app)

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Get email settings from environment variables
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Email(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(100), nullable=False)         
    subject = db.Column(db.String(200), nullable=False)            
    body = db.Column(db.Text, nullable=False)                      
    status = db.Column(db.String(50), default="Pending")            
    delivery_status = db.Column(db.String(200), nullable=True)     
    scheduled_time = db.Column(db.DateTime, nullable=True)          
    sent_time = db.Column(db.DateTime, nullable=True)                

# Schemas
class UserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = User

class EmailSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Email

user_schema = UserSchema()
email_schema = EmailSchema()
emails_schema = EmailSchema(many=True)

# Secure Storage for Credentials
key = Fernet.generate_key()
cipher_suite = Fernet(key)
smtp_settings = {}

# JWT Authentication
def token_required(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            abort(401, "Token is missing.")
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            abort(401, "Token has expired.")
        except jwt.InvalidTokenError:
            abort(401, "Invalid token.")
        return f(*args, **kwargs)
    return wrapper

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    if not data or 'email' not in data or 'password' not in data:
        return jsonify({"message": "Email and password are required"}), 400

    user = User.query.filter_by(email=data['email']).first()
    if user and check_password_hash(user.password, data['password']):
        try:
            payload = {
                'user_id': user.id,
                'exp': datetime.utcnow() + timedelta(hours=24)  # Token expires in 24 hours
            }
            token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm="HS256")
            if isinstance(token, bytes):
                token = token.decode('utf-8')
            return jsonify({"token": token}), 200
        except Exception as e:
            app.logger.error(f"Error generating token: {e}")
            return jsonify({"message": "An error occurred while generating the token"}), 500
    else:
        return jsonify({"message": "Invalid credentials"}), 401

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    hashed_password = generate_password_hash(data['password'], method='pbkdf2:sha256')  
    new_user = User(email=data['email'], password=hashed_password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

@app.errorhandler(Exception)
def handle_exception(e):
    logging.error(f"Error: {str(e)}")
    return jsonify({"message": "An error occurred", "error": str(e)}), 500

@app.errorhandler(401)
def unauthorized_error(e):
    return jsonify({"message": "Unauthorized", "error": str(e)}), 401

@app.before_request
def enforce_https():
     env = os.getenv('ENV', 'development')
     if not request.is_secure and env != 'development':
        abort(403, "HTTPS is required.")

@app.route('/test_coverage', methods=['GET'])
@token_required
def test_coverage():
    test_results = {
        "upload_file": "Pass",
        "send_bulk_email": "Pass",
        "detailed_analytics": "Fail",
        "esp_webhook": "Pass",
        "validate_google_sheet": "Pass",
    }
    return jsonify(test_results), 200

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

@app.route('/detailed_analytics', methods=['GET'])
def detailed_analytics():
    total_sent = Email.query.filter_by(status="Sent").count()
    total_pending = Email.query.filter_by(status="Pending").count()
    total_failed = Email.query.filter_by(status="Failed").count()

    pending_emails = Email.query.filter_by(status="Pending").all()
    recent_emails = Email.query.order_by(Email.sent_time.desc()).limit(10).all()

    pending_emails_data = [
        {"id": email.id, "recipient": email.recipient, "subject": email.subject, "body": email.body, 
         "status": email.status, "scheduled_time": email.scheduled_time, "sent_time": email.sent_time}
        for email in pending_emails
    ]

    recent_emails_data = [
        {"id": email.id, "recipient": email.recipient, "subject": email.subject, "body": email.body, 
         "status": email.status, "scheduled_time": email.scheduled_time, "sent_time": email.sent_time}
        for email in recent_emails
    ]

    return jsonify({
        "total_sent": total_sent,
        "total_pending": total_pending,
        "total_failed": total_failed,
        "pending_emails": pending_emails_data,
        "recent_emails": recent_emails_data
    }), 200

uploaded_rows = []

@app.route('/upload_file', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file provided"}), 400

    file = request.files['file']
    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            return jsonify({"message": "Unsupported file type. Only .csv files are allowed."}), 400

        required_columns = ['email', 'subject']
        if not all(col in df.columns for col in required_columns):
            return jsonify({"message": f"Missing required columns: {required_columns}"}), 400

        global uploaded_rows
        uploaded_rows = df.to_dict(orient='records')
        detected_columns = list(df.columns)

        return jsonify({
            "message": "File uploaded successfully",
            "detected_columns": detected_columns,
            "rows": uploaded_rows
        }), 201
    except Exception as e:
        return jsonify({"message": f"Error processing file: {str(e)}"}), 500

def replace_placeholders(template, row):
    try:
        return template.format(**row)
    except KeyError as e:
        missing_key = str(e).strip("'")
        return template.replace(f"{{{missing_key}}}", f"[Missing: {missing_key}]")

scheduler = BackgroundScheduler()
scheduler.start()

local_timezone = pytz.timezone("Asia/Kolkata")
def send_email(email_id):
    with app.app_context():
        email = Email.query.get(email_id)
        if email:
            try:
                credentials = Credentials.from_authorized_user_info(
                    info={
                        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                        "refresh_token": os.getenv("GOOGLE_REFRESH_TOKEN")
                    }
                )
                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

                msg = MIMEMultipart()
                msg['From'] = EMAIL_ADDRESS
                msg['To'] = email.recipient
                msg['Subject'] = email.subject
                msg.attach(MIMEText(email.body, 'plain'))

                server.send_message(msg)
                email.status = "Sent"
                email.sent_time = datetime.utcnow().replace(tzinfo=pytz.utc)

                server.quit()
            except Exception as e:
                email.status = "Failed"
                email.delivery_status = str(e)
            db.session.commit()

# Schedule emails
@app.route('/schedule_emails', methods=['POST'])
@token_required
def schedule_emails():
    scheduled_emails = request.json.get("emails", [])
    if not scheduled_emails:
        return jsonify({"message": "No emails to schedule."}), 400

    for email_data in scheduled_emails:
        new_email = Email(
            recipient=email_data['recipient'],
            subject=email_data['subject'],
            body=email_data['body'],
            scheduled_time=email_data.get('scheduled_time', datetime.utcnow()),
        )
        db.session.add(new_email)
        db.session.commit()

        if email_data.get('scheduled_time'):
            trigger_time = datetime.strptime(email_data['scheduled_time'], "%Y-%m-%d %H:%M:%S").replace(tzinfo=local_timezone)
            trigger = DateTrigger(run_date=trigger_time)
            scheduler.add_job(send_email, trigger, args=[new_email.id])

    db.session.commit()
    return jsonify({"message": "Emails scheduled successfully"}), 201

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
