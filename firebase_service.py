# firebase_service.py
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage, db
import hashlib
from werkzeug.utils import secure_filename
import uuid
import datetime
import tempfile
import os

class FirebaseService:
    def __init__(self):
        # Use the application default credentials or specify path to service account
        # You'll need to generate a service account key from Firebase console
        cred_path = os.environ.get('FIREBASE_CREDENTIALS', 'firebase-credentials.json')
        
        if not firebase_admin._apps:
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred, {
                'storageBucket': 'optima-88380.firebasestorage.app'
            })
            
        self.db = firestore.client()
        self.bucket = storage.bucket()
        
    # Authentication Methods
    def register_user(self, email, password, username):
        try:
            # Create user in Firebase Auth
            user = auth.create_user(
                email=email,
                password=password,
                display_name=username
            )
            
            # Create user document in Firestore
            self.db.collection('users').document(user.uid).set({
                'email': email,
                'username': username,
                'friends': [],
                'createdAt': firestore.SERVER_TIMESTAMP
            })
            
            return {
                'uid': user.uid,
                'email': user.email,
                'displayName': user.display_name
            }
        except Exception as e:
            print(f"Error in register_user: {e}")
            raise e
    
    def login_user(self, email, password):
        try:
            # Firebase Admin SDK doesn't support sign-in with email/password directly
            # In a production app, you would use Firebase Auth REST API or client SDKs
            # Here we'll simulate login by fetching the user by email
            
            # Note: In production, you should use Firebase Auth tokens for authentication
            users = list(self.db.collection('users').where('email', '==', email).limit(1).stream())
            
            if not users:
                raise Exception("User not found")
                
            user_doc = users[0]
            user_id = user_doc.id
            user_data = user_doc.to_dict()
            
            # Check if user document exists, if not create it
            if not user_data:
                # Get auth user
                auth_user = auth.get_user_by_email(email)
                self.db.collection('users').document(user_id).set({
                    'email': email,
                    'username': auth_user.display_name or email.split('@')[0],
                    'friends': [],
                    'createdAt': firestore.SERVER_TIMESTAMP
                })
                user_data = {
                    'email': email,
                    'username': auth_user.display_name or email.split('@')[0],
                    'friends': []
                }
            
            return {
                'uid': user_id,
                'email': user_data.get('email'),
                'displayName': user_data.get('username')
            }
        except Exception as e:
            print(f"Error in login_user: {e}")
            raise e
    
    # User Methods
    def get_user_profile(self, user_id):
        try:
            user_doc = self.db.collection('users').document(user_id).get()
            
            if not user_doc.exists:
                raise Exception("User not found")
                
            user_data = user_doc.to_dict()
            user_data['id'] = user_doc.id
            
            return user_data
        except Exception as e:
            print(f"Error in get_user_profile: {e}")
            raise e
    
    def search_users(self, search_term):
        try:
            # Get users where username starts with search_term
            query = (
                self.db.collection('users')
                .where('username', '>=', search_term)
                .where('username', '<=', search_term + '\uf8ff')
                .limit(10)
            )
            
            users = []
            current_user = None  # In production, get from authenticated context
            
            for doc in query.stream():
                if current_user and doc.id == current_user.uid:
                    continue
                    
                user_data = doc.to_dict()
                user_data['id'] = doc.id
                
                # Check if user is a friend of current user
                if current_user:
                    user_data['isFriend'] = current_user.uid in user_data.get('friends', [])
                    
                users.append(user_data)
                
            return users
        except Exception as e:
            print(f"Error in search_users: {e}")
            raise e
    
    # Friend Methods
    def add_friend(self, user_id, friend_id):
        try:
            # Add friend to user's friends list
            self.db.collection('users').document(user_id).update({
                'friends': firestore.ArrayUnion([friend_id])
            })
            
            # Add user to friend's friends list
            self.db.collection('users').document(friend_id).update({
                'friends': firestore.ArrayUnion([user_id])
            })
            
            return True
        except Exception as e:
            print(f"Error in add_friend: {e}")
            raise e
    
    def remove_friend(self, user_id, friend_id):
        try:
            # Remove friend from user's friends list
            self.db.collection('users').document(user_id).update({
                'friends': firestore.ArrayRemove([friend_id])
            })
            
            # Remove user from friend's friends list
            self.db.collection('users').document(friend_id).update({
                'friends': firestore.ArrayRemove([user_id])
            })
            
            return True
        except Exception as e:
            print(f"Error in remove_friend: {e}")
            raise e
    
    # Post Methods
    def create_post(self, user_id, content):
        try:
            user = self.get_user_profile(user_id)
            post_ref = self.db.collection('posts').document()
            
            post_ref.set({
                'userId': user_id,
                'username': user['username'],
                'content': content,
                'likes': [],
                'comments': [],
                'createdAt': firestore.SERVER_TIMESTAMP
            })
            
            return post_ref.id
        except Exception as e:
            print(f"Error in create_post: {e}")
            raise e
    
    def get_friends_posts(self, user_id):
        try:
            # Get user's friends
            user_doc = self.db.collection('users').document(user_id).get()
            user_data = user_doc.to_dict()
            friends = user_data.get('friends', []) if user_data else []
            
            # Include user's own posts
            friends.append(user_id)
            
            # Get posts from user and friends
            posts = []
            
            # Handle case with no friends
            if not friends:
                return []
                
            query = (
                self.db.collection('posts')
                .where('userId', 'in', friends)
                .order_by('createdAt', direction=firestore.Query.DESCENDING)
                .limit(20)
            )
            
            for doc in query.stream():
                post_data = doc.to_dict()
                # Convert timestamps to strings for JSON serialization
                if 'createdAt' in post_data and post_data['createdAt']:
                    post_data['createdAt'] = post_data['createdAt'].isoformat()
                    
                post_data['id'] = doc.id
                posts.append(post_data)
                
            return posts
        except Exception as e:
            print(f"Error in get_friends_posts: {e}")
            raise e
    
    # Like Methods
    def toggle_like(self, post_id, user_id):
        try:
            post_ref = self.db.collection('posts').document(post_id)
            post_doc = post_ref.get()
            
            if not post_doc.exists:
                raise Exception("Post not found")
                
            post_data = post_doc.to_dict()
            likes = post_data.get('likes', [])
            has_liked = user_id in likes
            
            if has_liked:
                post_ref.update({
                    'likes': firestore.ArrayRemove([user_id])
                })
            else:
                post_ref.update({
                    'likes': firestore.ArrayUnion([user_id])
                })
                
            return not has_liked
        except Exception as e:
            print(f"Error in toggle_like: {e}")
            raise e
    
    def add_comment(self, post_id, user_id, content):
        try:
            user = self.get_user_profile(user_id)
            post_ref = self.db.collection('posts').document(post_id)
            
            comment = {
                'id': str(uuid.uuid4()),
                'userId': user_id,
                'username': user['username'],
                'content': content,
                'createdAt': datetime.datetime.now().isoformat()
            }
            
            post_ref.update({
                'comments': firestore.ArrayUnion([comment])
            })
            
            return comment
        except Exception as e:
            print(f"Error in add_comment: {e}")
            raise e
            
    def get_like_details(self, post_id):
        try:
            likes = []
            post_doc = self.db.collection('posts').document(post_id).get()
            
            if not post_doc.exists:
                raise Exception("Post not found")
                
            like_user_ids = post_doc.to_dict().get('likes', [])
            
            # Get user details for each like
            for user_id in like_user_ids:
                user_doc = self.db.collection('users').document(user_id).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    likes.append({
                        'userId': user_id,
                        'username': user_data.get('username')
                    })
                    
            return likes
        except Exception as e:
            print(f"Error in get_like_details: {e}")
            raise e
    
    # Additional methods from star.jsx
    def get_post(self, post_id):
        try:
            post_doc = self.db.collection('posts').document(post_id).get()
            
            if not post_doc.exists:
                raise Exception("Post not found")
                
            post_data = post_doc.to_dict()
            post_data['id'] = post_doc.id
            
            # Convert timestamp to string
            if 'createdAt' in post_data and post_data['createdAt']:
                post_data['createdAt'] = post_data['createdAt'].isoformat()
                
            return post_data
        except Exception as e:
            print(f"Error in get_post: {e}")
            raise e
    
    def get_feed(self, user_id, last_post=None):
        try:
            # Create base query
            query = (
                self.db.collection('posts')
                .order_by('createdAt', direction=firestore.Query.DESCENDING)
                .limit(10)
            )
            
            # If last_post provided, use it as start_after
            if last_post:
                last_post_doc = self.db.collection('posts').document(last_post).get()
                if last_post_doc.exists:
                    query = query.start_after(last_post_doc)
                    
            # Execute query
            posts = []
            for doc in query.stream():
                post_data = doc.to_dict()
                post_data['id'] = doc.id
                
                # Convert timestamp to string
                if 'createdAt' in post_data and post_data['createdAt']:
                    post_data['createdAt'] = post_data['createdAt'].isoformat()
                    
                posts.append(post_data)
                
            return {
                'posts': posts,
                'last_post': posts[-1]['id'] if posts else None
            }
        except Exception as e:
            print(f"Error in get_feed: {e}")
            raise e
    
    def get_comments(self, post_id, last_comment=None):
        try:
            # Create base query
            query = (
                self.db.collection('comments')
                .where('post_id', '==', post_id)
                .order_by('createdAt', direction=firestore.Query.DESCENDING)
                .limit(20)
            )
            
            # If last_comment provided, use it as start_after
            if last_comment:
                last_comment_doc = self.db.collection('comments').document(last_comment).get()
                if last_comment_doc.exists:
                    query = query.start_after(last_comment_doc)
                    
            # Execute query
            comments = []
            for doc in query.stream():
                comment_data = doc.to_dict()
                comment_data['id'] = doc.id
                
                # Convert timestamp to string
                if 'createdAt' in comment_data and comment_data['createdAt']:
                    comment_data['createdAt'] = comment_data['createdAt'].isoformat()
                    
                comments.append(comment_data)
                
            return {
                'comments': comments,
                'last_comment': comments[-1]['id'] if comments else None
            }
        except Exception as e:
            print(f"Error in get_comments: {e}")
            raise e
    
    def check_like_status(self, post_id, user_id):
        try:
            like_ref = self.db.collection('likes').document(f"{post_id}_{user_id}").get()
            return like_ref.exists
        except Exception as e:
            print(f"Error in check_like_status: {e}")
            raise e
    
    def toggle_follow(self, follower_id, target_user_id):
        try:
            follower_ref = self.db.collection('users').document(follower_id)
            target_ref = self.db.collection('users').document(target_user_id)
            
            follower_doc = follower_ref.get()
            if not follower_doc.exists:
                raise Exception("Follower user not found")
                
            following = follower_doc.to_dict().get('following', [])
            
            if target_user_id in following:
                # Unfollow
                follower_ref.update({
                    'following': firestore.ArrayRemove([target_user_id])
                })
                target_ref.update({
                    'followers_count': firestore.Increment(-1)
                })
                return False
            else:
                # Follow
                follower_ref.update({
                    'following': firestore.ArrayUnion([target_user_id])
                })
                target_ref.update({
                    'followers_count': firestore.Increment(1)
                })
                return True
        except Exception as e:
            print(f"Error in toggle_follow: {e}")
            raise e
    
    def update_user_profile(self, user_id, updates):
        try:
            updates['updated_at'] = firestore.SERVER_TIMESTAMP
            self.db.collection('users').document(user_id).update(updates)
            return True
        except Exception as e:
            print(f"Error in update_user_profile: {e}")
            raise e
    
    def upload_profile_picture(self, user_id, file):
        try:
            # Create a temporary file
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                file.save(tmp.name)
                
                # Upload to Firebase Storage
                blob = self.bucket.blob(f"profile_pictures/{user_id}")
                blob.upload_from_filename(tmp.name)
                
                # Make the blob publicly accessible
                blob.make_public()
                url = blob.public_url
                
            # Update user profile with picture URL
            self.update_user_profile(user_id, {'profile_picture': url})
            
            # Clean up temp file
            os.unlink(tmp.name)
            
            return {'url': url}
        except Exception as e:
            print(f"Error in upload_profile_picture: {e}")
            raise e
    
    # Admin auth Methods
    
    def register_admin(self, email, password, name):
        '''Register a new admin user'''
        try:
            # Check if admin with this email alr exists
            admins_query = self.db.collection('admins').where('email', '==', email).limit(1).stream()
            if list(admins_query):
                raise Exception('Admin with this email already exists')
            
            admins_ref = self.db.collection('admins').document()
            admin_id = admins_ref.id
            
            hashed_password = hashlib.sha256(password.encode()).hexdigest() # hashes the password, to change in prod for more secure hashing
            
            admin_data = {
                'id': admin_id,
                'email': email,
                'password': hashed_password, # to change in prod
                'name': name,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            
            admins_ref.set(admin_data)
            self.log_admin_action(admin_id, 'ADMIN_CREATED', {
                'admin_email': email
            })
            admin_return = admin_data.copy()
            admin_return.pop('password')
            return admin_return
        except Exception as e:
            print(f'Error in register_admin: {e}')
            raise(e)
    
    def login_admin(self, email, password):
        '''Authenticate an admin user'''
        try: 
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            admins_query = self.db.collection('admins').where('email', '==', email).limit(1).stream()
            admins = list(admins_query)
            
            if not admins:
                return None
            
            admin_doc = admins[0]
            admin_data = admin_doc.to_dict()
            
            if admin_data.get('password') != hashed_password:
                return None
            
            admin_return = admin_data.copy()
            admin_return.pop('password')
            admin_return['id'] = admin_doc.id
            
            return admin_return
        except Exception as e:
            print(f'Error in login_admin: {e}')
            raise(e)

    def get_admin(self, admin_id):
        '''Get admin by id'''
        try:
            admin_doc = self.db.collection('admins').document(admin_id).get()
            
            if not admin_doc.exists:
                return None
            
            admin_data = admin_doc.to_dict()
            
            # remove passw from return obj
            admin_return = admin_data.copy()
            admin_return.pop('password', None)
            admin_return['id'] = admin_doc.id
            
            return admin_return
        except Exception as e:
            print(f'Error in get_admin: {e}')
            raise(e)

    # Task management methods
    
    def get_all_tasks(self):
        '''get all task templates'''
        tasks_ref = self.db.child('tasks')
        tasks = tasks_ref.get() or {}
        
        # convert dict to list with ID included
        tasks_list = [
            {**task, 'id': task_id}
            for task_id, task in tasks.items()
        ]
        
        return tasks_list
    
    def create_task_template(self, title, reward, category='General', description=''):
        '''Create new task template'''
        tasks_ref = self.db.child('tasks')
        
        task_id = str(uuid.uuid4())
        task_data = {
            'title': title,
            'reward': reward,
            'category': category,
            'description': description,
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat
        }
        
        tasks_ref.child(task_id).set(task_data)
        return task_id
    
    def update_task(self, task_id, updates):
        '''Update an existing task template'''
        task_ref = self.db.child('tasks').child(task_id)
        
        task = task_ref.get()
        if not task:
            raise Exception('Task not found')
        
        task_ref.update(updates)
        return True
    
    def delete_task(self, task_id):
        '''Delete a task template'''
        task_ref = self.db.child('tasks').child(task_id)
        
        task = task_ref.get()
        if not task:
            raise Exception('Task not found')
        
        task_ref.delete()
        return True
    
    # User management methods
    
    def get_all_users(self):
        '''Get all users with basic info'''
        users_ref = self.db.child('users')
        users = users_ref.get() or {}
        
        users_list = [] # filter sensitive info and conv to list
        for user_id, user in users.items():
            filtered_user = {
                'id': user_id,
                'username': user.get('username', ''),
                'email': user.get('email', ''),
                'created_at': user.get('created_at', ''),
                'last_login': user.get('last_login', ''), # pretty sure we don't have this attribute but will test and can be added in future pretty easily
                'suspended': user.get('suspended', False)
            }
            users_list.append(filtered_user)
        
        return users_list
    
    def get_user_tasks(self, user_id):
        '''Get tasks associated with specific user'''
        user_tasks_ref = self.db.child('user_tasks').child(user_id)
        user_tasks = user_tasks_ref.get() or {}
        
        tasks_list = [
            {**task, 'id': task_id}
            for task_id, task in user_tasks.items()
        ]
        
        return tasks_list
    
    def get_user_screentime(self, user_id):
        '''Get screentime data for a user'''
        screentime_ref = self.db.child('screentime').child(user_id)
        screentime = screentime_ref.get() or {}
        
        return screentime

    def reset_user_password(self, user_id, new_password):
        '''Reset a user's password'''
        user_ref = self.db.child('users').child(user_id)
        
        user = user_ref.get()
        if not user:
            raise Exception('User not found')
        
        hashed_password = hashlib.sha256(new_password.encode()).hexdigest() # check back on hashing password functionality
        
        user_ref.update({'password': hashed_password})
        return True
    
    def suspend_user(self, user_id, suspend=True):
        '''Suspend or unsuspend a user account'''
        user_ref = self.db.child('users').child(user_id)
        
        user = user_ref.get()
        if not user:
            raise Exception('User not found')
        
        user_ref.update({'suspend': suspend})
        return True
    
    # Post Management methods
    
    def get_all_posts(self, limit=50):
        '''Get all posts with a specific limit'''
        posts_ref = self.db.child('posts')
        posts = posts_ref.get() or {}
        
        posts_list = [
            {**post, 'post_id': post_id}
            for post_id, post in posts.items()
        ]
        
        posts_list.sort(key=lambda x: x.get('created_at', ''), reverse=True)
        return posts_list[:limit]
    
    def delete_post(self, post_id):
        '''Delete a specifified post'''
        post_ref = self.db.child('posts').child(post_id)
        post = post_ref.get() or {}
        
        if not post:
            raise Exception('POst not found')
        
        post_ref.delete()
        
        self.db.child('comments').child(post_id).delete()
        self.db.child('likes').child(post_id).delete()
        return True

    def get_analytics_summary(self): # Can be refactored
        '''Get summary analytics for the dashboard'''
        users_count = len(self.db.child('users').get() or {})
        tasks_count = len(self.db.child('tasks').get() or {})
        posts_count = len(self.db.child('posts').get() or {})
        
        users = self.db.child('users').get() or {}
        active_users = 0
        seven_days_ago = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
        
        for user in users.values():
            if user.get('last_login'):
                try:
                    last_login = datetime.datetime.fromisoformat(user.get('last_login'))
                    if last_login > seven_days_ago:
                        active_users += 1
                except (ValueError, TypeError):
                    pass
        
        all_user_tasks = self.db.child('user_tasks').get() or {} # check if valid
        completed_tasks = 0
        
        for user_tasks in all_user_tasks.values():
            for task in user_tasks.values():
                if task.get('completed', False):
                    completed_tasks += 1
        
        return {
            'total_users': users_count,
            'active_users_7d': active_users,
            'total_tasks': tasks_count,
            'completed_tasks': completed_tasks,
            'posts_count': posts_count
        }
    
    def get_task_analytics(self):
        '''Get analytics about tasks usage'''
        all_tasks = self.db.child('tasks').get() or {}
        all_user_tasks = self.db.child('user_tasks').get() or {}
        
        categories = {}
        for task in all_tasks.values():
            category = task.get('category', 'General')
            categories[category] = categories.get(category, 0) + 1
        
        # get completion data
        completion_rate = 0
        total_user_tasks = 0
        completed_user_tasks = 0
        
        for user_tasks in all_user_tasks.values():
            for task in user_tasks.values():
                total_user_tasks += 1
                if task.get('completed', False):
                    completed_user_tasks += 1
        
        if total_user_tasks > 0:
            completion_rate = (completed_user_tasks/total_user_tasks)*100
        
        return {
            'categories': [{'name': k, 'count': v} for k, v in categories.items()],
            'completion_rate': completion_rate,
            'total_tasks_assigned': total_user_tasks,
            'tasks_completed': completed_user_tasks
        }
    
    def get_screentime_analytics(self):
        '''Get analytics about screentime usage'''
        pass
    
    # admin logs methods
    
    def log_admin_action(self, admin_id, action_type, details=None):
        '''Log an action taken/performed by an admin'''
        logs_ref = self.db.child('admin_logs')
        
        log_id = str(uuid.uuid4())
        log_data = {
            'admin_id': admin_id,
            'action_type': action_type,
            'details': details or {},
            'timestamp': firestore.SERVER_TIMESTAMP,
            'ip_address': request.remote_addr if 'request' in globals() else None
        }
        
        logs_ref.child(log_id).set(log_data)
        return log_id
    
    def get_admin_logs(self, limit=100):
        '''Get admin activity logs'''
        logs_ref = self.db.child('admin_logs')
        logs = logs_ref.get() or {}
        
        logs_list = [
            {**log, 'id': log_id}
            for log_id, log in logs.items()
        ]
        
        logs_list.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return logs_list[:limit]