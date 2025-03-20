from flask import Flask, request, jsonify
from firebase_service import FirebaseService
from flask_cors import CORS
import os
import secrets
import jwt
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
CORS(app)

app.config['SECRET_KEY'] = os.environ.get('ADMIN_SECRET_KEY', secrets.token_hex(16)) # Secret key for JWT tokens - keep this secure
ADMIN_REGISTRATION_KEY = os.environ.get('ADMIN_REGISTRATION_KEY', 'villanova-optima-admin-2025') # registration key required to create admin accounts

firebase_service = FirebaseService()

# decorator for JWT token validation
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_admin = firebase_service.get_admin(data['admin_id'])
            if not current_admin:
                return jsonify({'success': False, 'message': 'Invalid admin token'}), 401
        except:
            return jsonify({'success': False, 'message': 'Token is invalid'}), 401
        
        return f(current_admin, *args, **kwargs)

    return decorated