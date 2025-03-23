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
            return jsonify({
                'success': False,
                'message': 'Token is missing'
            }), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_admin = firebase_service.get_admin(data['admin_id'])
            if not current_admin:
                return jsonify({
                    'success': False,
                    'message': 'Invalid admin token'
                }), 401
        except:
            return jsonify({
                'success': False,
                'message': 'Token is invalid'
            }), 401
        
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
            return jsonify({
                'success': False,
                'error': 'Email and password are required'
            }), 400
        
        # authenticate admin
        admin_user = firebase_service.login_admin(email, password)
        # check if auth successful
        if not admin_user:
            return jsonify({
                'success': False,
                'error': 'Invalid credentials'
            }), 401
        
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
            return jsonify({
                'success': False,
                'error': 'All fields are required'
            }), 400
        
        # validate registration key
        if registration_key != ADMIN_REGISTRATION_KEY:
            return jsonify({
                'success': False,
                'error': 'Invalid registration key'
            }), 403
        
        # Register admin
        admin_user = firebase_service.register_admin(email, password, name)
        
        
        return jsonify({
            'success': True,
            'admin': admin_user
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

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

# Post management routes

@app.route('/api/admin/posts', methods=['GET'])
@token_required
def get_posts(current_admin):
    try:
        # extract pagination params
        limit = request.args.get('limit', 50, type=int)
        start_after = request.args.get('startAfter')
        
        # Get posts with pagination
        posts_data = firebase_service.get_all_posts(limit=limit, start_after=start_after)
        
        return jsonify({
            'success': True,
            'posts': posts_data['posts'],
            'last_post': posts_data['last_post']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/posts/<post_id>', methods=['GET'])
@token_required
def get_post_details(current_admin, post_id):
    try:
        post = firebase_service.get_post(post_id) # get post details
        
        return jsonify({
            'success': True,
            'post': post
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/posts/<post_id>', methods=['DELETE'])
@token_required
def delete_posts(current_admin, post_id):
    try:
        firebase_service.delete_post(post_id, admin_id=current_admin['id'])
        
        return jsonify({
            'success': True,
            'message': f'Post {post_id} has been deleted'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/posts/<post_id>/content', methods=['PUT'])
@token_required
def update_post_content(current_admin, post_id):
    try:
        data = request.json
        new_content = data.get('content')
        
        if not new_content: # validate content
            return jsonify({
                'success': False,
                'error': 'Content is required'
            }), 400
        
        firebase_service.update_post_content(post_id, new_content, admin_id=current_admin['id'])
        
        return jsonify({
            'success': True,
            'message': f'Post {post_id} content updated'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/posts/<post_id>/comments/<comment_id>', methods=['DELETE'])
@token_required
def delete_comment(current_admin, post_id, comment_id):
    try:
        # delete comment
        firebase_service.delete_comment(post_id=post_id, comment_id=comment_id, admin_id=current_admin['id'])
        
        return jsonify({
            'success': True,
            'message': f'Comment {comment_id} has been deleted from post {post_id}'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# User management Routes

@app.route('/api/admin/users', methods=['GET'])
@token_required
def get_users(current_admin):
    try:
        # Extract pagination params
        limit = request.args.get('limit', 50, type=int)
        start_after = request.args.get('startAfter')
        
        users_data = firebase_service.get_all_users(limit=limit, start_after=start_after) # get users with pagination
        
        return jsonify({
            'success': True,
            'users': users_data['users'],
            'last_user': users_data['last_user']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/users/<user_id>', methods=['GET'])
@token_required
def get_user_details(current_admin, user_id):
    try:
        # get user profile
        user = firebase_service.get_user_profile(user_id)
        
        # get user's posts
        posts = firebase_service.get_user_posts(user_id)
        
        # add posts to user data
        user['posts'] = posts
        
        return jsonify({
            'success': True,
            'user': user
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/users/<user_id>/suspend', methods=['POST'])
@token_required
def suspend_user(current_admin, user_id):
    try:
        data = request.json
        suspended = data.get('suspended', True)
        
        # suspend/unsuspend user
        firebase_service.suspend_user(user_id, suspended=suspended, admin_id=current_admin['id'])
        
        message = f'User {user_id} has been {'suspended' if suspended else 'unsuspended'}'
        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
@token_required
def delete_user(current_admin, user_id):
    try:
        result = firebase_service.delete_user(user_id, admin_id=current_admin['id'])
        return jsonify({
            'success': True,
            'message': f'User {user_id} and {result['posts_deleted']} posts have been deleted'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Analytics routes

@app.route('/api/admin/analytics/summary', methods=['GET'])
@token_required
def get_analytics_summary(current_admin):
    try:
        # extract time period
        days = request.args.get('days', 30, type=int)
        
        # get analytics summary
        summary = firebase_service.get_analytics_summary(days=days)
        
        return jsonify({
            'success': True,
            'summary': summary
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Admin Logs Routes

@app.route('/api/admin/logs', methods=['GET'])
@token_required
def get_admin_logs(current_admin):
    try:
        # extract limit params
        limit = request.args.get('limit', 100, type=int)
        
        # get admin logs
        logs = firebase_service.get_admin_logs(limit=limit)
        
        return jsonify({
            'success': True,
            'logs': logs
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

# Start server
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001)) # we use 5001 for now to use a different port than the main API
    app.run(host='0.0.0.0', port=port, debug=True)