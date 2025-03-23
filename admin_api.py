from flask import Flask, request, jsonify
from firebase_service import FirebaseService
from flask_cors import CORS
import os
import secrets
import jwt
import datetime
from datetime import timedelta
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

# admin auth routes
@app.route('/api/admin/login', methods=['POST'])
def admin_login():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        # validate required fields
        if not all([email, password]):
            return jsonify({'success': False, 'error': 'Email and password are required'}), 400
        
        # authenticate admin
        admin_user = firebase_service.login_admin(email, password)
        # check if auth successful
        if not admin_user:
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # gen JWT token
        token = jwt.encode({
            'admin_id': admin_user['id'],
            'exp': datetime.datetime.now(datetime.timezone.utc) + timedelta(hours=24)
        }, app.config['SECRET_KEY'], algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'admin': {
                'id': admin_user['id'],
                'email': admin_user['email'],
                'name': admin_user.get('name', '')
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/register', methods=['POST'])
def admin_register():
    try:
        data = request.json
        email = data.get('email')
        password = data.get('password')
        name = data.get('name')
        registration_key = data.get('registrationKey')
        
        # validate required fields
        if not all([email, password, name, registration_key]):
            return jsonify({'success': False, 'error': 'All fields are required'}), 400
        
        # validate registration key
        if registration_key != ADMIN_REGISTRATION_KEY:
            return jsonify({'success': False, 'error': 'Invalid registration key'}), 403
        
        # Register admin
        admin_user = firebase_service.register_admin(email, password, name)
        
        
        return jsonify({'success': True, 'admin': admin_user})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/admin/profile', methods=['GET'])
@token_required
def admin_profile(current_admin):
    '''Get the profile of the current admin'''
    try:
        admin_id = current_admin['id']
        admin_data = firebase_service.get_admin(admin_id) # fetch most up-to date info about the admin
        
        if not admin_data:
            return jsonify({
                'success': False,
                'error': 'Admin account not found'
            }), 404
        
        return jsonify({
            'success': True,
            'admin': admin_data
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'Error retrieving admin profile: {str(e)}'
        }), 500


