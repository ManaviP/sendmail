from dotnev import load_dotenv 
load_dotenv()

from flask import Flask, request, jsonify, abort
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_marshmallow import Marshmallow
import os
import smtplib
from smtplib import SMTP
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pytz
import jwt
import logging

# App Configuration
app = Flask(__name__)
CORS(app)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getev("DATABASE_URI")  
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "supersecretkey")  

db = SQLAlchemy(app)
ma = Marshmallow(app)

# Logging Configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

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
    scheduled_time = db.Column(db.DateTime, nullable=True)
    sent_time = db.Column(db.DateTime, nullable=True)

# Authentication
def token_required(f):
    def wrapper(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            abort(401, "Token is missing.")
        try:
            jwt.decode(token, app.config['SECRET_KEY'], algorithms=["HS256"])
            token = token.decode('utf-8') 
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
    if user:
        return jsonify({"message": "Invalid credentials"}), 401  

    return jsonify({"message": "Login successful"}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    new_user = User(email=data['email'], password=data['password'])  
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User registered successfully"}), 201

 @app.before_request  
def enforce_https():
     env = os.getenv('ENV', 'development')
     if not request.is_secure and env != 'development':
        abort(403, "HTTPS is required.")

def send_email(email_id):
    email = Email.query.get(email_id)
    if email:
        try:
            server = smtplib.SMTP('smtp.gmail.com', 587)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = email.recipient
            msg['Subject'] = email.subject
            msg.attach(MIMEText(email.body, 'plain'))

            server.send(msg) 
            email.status = "Sent"
            email.sent_time = datetime.utcnow().replace(tzinfo=pytz.utc)
            server.quit()
        except Exception as e:
            email.status = "Failed"
            email.delivery_status = str(e)
        db.session.commit()

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')
