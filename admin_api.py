from flask import Flask, request, jsonify
from firebase_service import FirebaseService
from flask_cors import CORS
import os
from dotenv import load_dotenv
import secrets
import jwt
import datetime
from datetime import timedelta
from functools import wraps

app = Flask(__name__)
CORS(app)

# Load environment variables from .env file
load_dotenv()

# Access environment variables
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

# Community

@app.route('/api/admin/community-tasks', methods=['GET'])
@token_required
def get_community_tasks(current_admin):
    try:
        limit = request.args.get('limit', 50, type=int)
        start_after = request.args.get('startAfter')
        
        tasks_data = firebase_service.get_community_tasks(limit=limit, start_after=start_after)
        
        return jsonify({
            'success': True,
            'tasks': tasks_data['tasks'],
            'last_task': tasks_data['last_task']
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks/<task_id>', methods=['GET'])
@token_required
def get_community_task(current_admin, task_id):
    try:
        
        task = firebase_service.get_community_task(task_id=task_id)
        
        return jsonify({
            'success': True,
            'task': task
        })
    except Exception as e:
        return jsonify({
            'sucess': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks', methods=['POST'])
@token_required
def create_community_task(current_admin):
    try:
        data = request.json
        title = data.get('title')
        category = data.get('category')
        reward_minutes = data.get('reward_minutes')
        deadline = data.get('deadline')
        
        if not all([title, category, reward_minutes, deadline]):
            return jsonify({
                'success': False,
                'error': 'All fields are required. Fields are: title, category, reward_minutes, deadline'
            }), 400
        
        try: 
            reward_minutes = int(reward_minutes)
            if reward_minutes <= 0:
                raise ValueError('Reward minutes must be positive')
        except (TypeError, ValueError):
            return jsonify({
                'success': False,
                'error': 'Reward minutes must be a positive number'
            }), 400
        
        try:
            deadline_dt = datetime.datetime.strptime(deadline, '%d/%m/%Y %H:%M')
            if deadline_dt <= datetime.datetime.now():
                return jsonify({
                    'success': False,
                    'error': 'Deadline must be a future date'
                }), 400
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid deadline format. Use format DD/MM/YYYY HH:MM'
            }), 400
        
        task = firebase_service.create_community_task(title=title, category=category, reward_minutes=reward_minutes, deadline=deadline_dt, admin_id=current_admin['id'])
        
        return jsonify({
            'success': True,
            'community_task': task
        })
    except Exception as e:
        print(f'Error: {e}')
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks/<task_id>', methods=['PUT'])
@token_required
def update_community_task(current_admin, task_id):
    try:
        data = request.json
        deadline = data.get('deadline')
        
        if deadline:
            try:
                deadline_dt = datetime.datetime.strptime(deadline, '%d/%m/%Y %H:%M')
                if deadline_dt <= datetime.datetime.now():
                    return jsonify({
                        'success': False,
                        'error': 'Deadline must be a future date'
                    }), 400
                data['deadline'] = deadline_dt
            except ValueError:
                return jsonify({
                    'success': False,
                    'error': 'Invalid deadline format. Use format DD/MM/YYYY HH:MM'
                }), 400
        
        updated_task = firebase_service.update_community_task(
            task_id=task_id,
            updates=data,
            admin_id=current_admin['id']
        )
        
        return jsonify({
            'success': True,
            'task': updated_task
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks/<task_id>', methods=['PUT'])
@token_required
def delete_community_task_route(current_admin, task_id):
    try:
        
        firebase_service.delete_community_task(
            task_id=task_id,
            admin_id=current_admin['id']
        )
        
        return jsonify({
            'success': True,
            'message': f'Community task {task_id} has been deleted'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks/stats', methods=['GET'])
@token_required
def get_community_task_stats(current_admin):
    try:
        stats = firebase_service.get_community_task_stats()
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks/categories', methods=['GET'])
@token_required
def get_community_task_categories(current_admin):
    try:
        limit = request.args.get('limit', 50, type=int)
        start_after = request.args.get('startAfter')
        
        categories = firebase_service.get_task_categories()
        
        return jsonify({
            'success': True,
            'categories': categories
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community-tasks/categories/<category_id>', methods=['GET'])
@token_required
def get_task_category(current_admin, category_id):
    try:
        category = firebase_service.get_task_category(category_id=category_id)
        
        return jsonify({
            'success': True,
            'category': category 
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('api/admin/community-tasks/categories', methods=['POST'])
@token_required
def create_task_category(current_admin):
    try:
        data = request.json
        
        required_fields = ['category_name', 'category_type', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Field {field} is required'
                }), 400

        category = firebase_service.create_community_task_category(
            category_name=data['category_name'],
            category_type=data['category_type'],
            description=data['description'],
            admin_id=current_admin['id']
        )
        
        return jsonify({
            'success': True,
            'category': category
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community_task/categories/<category_id>', methods=['PUT'])
@token_required
def update_task_category(current_admin, category_id):
    try:
        data = request.json
        
        updated_category = firebase_service.update_task_category(
            category_id=category_id,
            updates=data,
            admin_id=current_admin['id']
        )
        
        return jsonify({
            'success': True,
            'category': updated_category
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400

@app.route('/api/admin/community_task/categories/<category_id>', methods=['DELETE'])
@token_required
def delete_task_category(current_admin, category_id):
    try:
        firebase_service.delete_community_task_category(category_id=category_id, admin_id=current_admin['id'])
        
        return jsonify({
            'success': True,
            'message': f'Category {category_id} has been deleted'
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