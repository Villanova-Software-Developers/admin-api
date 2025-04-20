# firebase_service.py
import firebase_admin
from firebase_admin import credentials, firestore, auth, storage
import hashlib
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
    
    def get_user_posts(self, user_id): # ! Added for admin-api
        '''Get all posts created by a specific user'''
        try:
            # query posts by the user
            posts_query = self.db.collection('posts').where('userId', '==', user_id).stream()
            posts = []
            
            for doc in posts_query:
                post_data = doc.to_dict()
                post_data['id'] = doc.id
                
                if 'createdAt' in post_data and post_data['createdAt']:
                    post_data['createdAt'] = post_data['createdAt'].isoformat()
                
                post_data['commentCount'] = len(post_data.get('comments', []))
                post_data['likeCount'] = len(post_data.get('likes', []))
                
                posts.append(post_data)
            
            return posts
        except Exception as e:
            print(f'Error in get_user_posts: {e}')
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
    
    # ! everything below this point has been added to support admin-api
    
    # Admin auth methods
    
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
            
            return {
            'id': admin_id,
            'email': email,
            'name': name
            }
        except Exception as e:
            print(f'Error in register_admin: {e}')
            raise e
    
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
            
            if admin_data.get('password') != hashed_password: # check password
                return None
            
            admin_return = admin_data.copy()
            admin_return.pop('password')
            admin_return['id'] = admin_doc.id
            
            return admin_return
        except Exception as e:
            print(f'Error in login_admin: {e}')
            raise e

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
            raise e

    # Task management methods, commented out as tasks are not implemented in db yet
    
    # def get_all_tasks(self):
    #     '''get all task templates'''
    #     try:
    #         tasks = []
    #         task_query = self.db.collection('tasks').stream()
            
    #         for doc in task_query:
    #             task_data = doc.to_dict()
    #             task_data['id'] = doc.id
    #             tasks.append(task_data)
            
    #         return tasks
    #     except Exception as e:
    #         print(f'Error in get_all_tasks: {e}')
    #         raise e
    
    # def create_task_template(self, title, reward, category='General', description=''): # ? Maybe not to use
    #     '''Create new task template'''
    #     try:
    #         tasks_ref = self.db.collection('tasks').document()
            
    #         task_data = {
    #             'title': title,
    #             'reward': reward,
    #             'category': category,
    #             'description': description,
    #             'created_at': firestore.SERVER_TIMESTAMP
    #         }
            
    #         tasks_ref.set(task_data)
    #         return tasks_ref.id
    #     except Exception as e:
    #         print(f'Error in create_task_template: {e}')
    #         raise e
    
    # def update_task(self, task_id, updates):
    #     '''Update an existing task template'''
    #     try:
    #         task_ref = self.db.collection('tasks').document(task_id)
    #         task_doc = task_ref.get()
            
    #         if not task_doc.exists:
    #             raise Exception('Task not found')
            
    #         updates['UpdatedAt'] = firestore.SERVER_TIMESTAMP
    #         task_ref.update(updates)
    #         return True
    #     except Exception as e:
    #         print(f'Error in update_task: {e}')
    #         raise e
    
    # def delete_task(self, task_id):
    #     '''Delete a task template'''
    #     try:
    #         task_ref = self.db.collection('tasks').document(task_id)
    #         task_doc = task_ref.get()
            
    #         if not task_doc.exists:
    #             raise Exception('Task not found')
            
    #         task_ref.delete()
    #         return True
    #     except Exception as e:
    #         print(f'Error in delete_task: {e}')
    #         raise e
    
    # User management methods
    
    def get_all_users(self, limit=50, start_after=None):
        '''Get all users with basic info'''
        try:
            query = (
                self.db.collection('users')
                .order_by('createdAt', direction=firestore.Query.DESCENDING)
                .limit(limit)
            ) # base query
            
            if start_after: # start after given user assuming it is given and exists
                last_doc = self.db.collection('users').document(start_after).get()
                if last_doc.exists:
                    query = query.start_after(last_doc)
            
            users = []
            for doc in query.stream():
                user_data = doc.to_dict()
                
                # filtered user object wo we don't see password and other details
                filtered_user = {
                    'id': doc.id,
                    'username': user_data.get('username', ''),
                    'email': user_data.get('email', ''),
                    'friends': len(user_data.get('friends', [])),
                    'suspended': user_data.get('suspended', False)
                }
                
                if 'createdAt' in user_data and user_data['createdAt']:
                    filtered_user['createdAt'] = user_data['createdAt'].isoformat()
                
                users.append(filtered_user)
            
            return {
                'users': users,
                'last_user': users[-1]['id'] if users else None
            }
        except Exception as e:
            print(f'Error in get_all_users: {e}')
            raise e
    
    ## NOT USABLE
    # def get_user_tasks(self, user_id):
    #     '''Get tasks associated with specific user'''
    #     try:
    #         tasks = []
    #         tasks_query = self.db.collection('user_tasks').where('userId', '==', user_id).stream()
            
    #         for doc in tasks_query:
    #             task_data = doc.to_dict()
    #             task_data['id'] = doc.id
    #             tasks.append(task_data)
            
    #         return tasks
    #     except Exception as e:
    #         print(F'Error in get_user_tasks: {e}')
    #         raise e
    
    # def get_user_screentime(self, user_id):
    #     '''Get screentime data for a user'''
    #     try:
    #         screentime_query = self.db.collection('screentime').where('userId', '==', user_id).stream()
    #         screentime_data = [doc.to_dict() for doc in screentime_query]
            
    #         return screentime_data
    #     except Exception as e:
    #         print(f'Error in get_user_screentime: {e}')
    #         raise e

    # PIVOT, decide whether to allow admin password resets
    # def reset_user_password(self, user_id, new_password):
    #     '''Reset a user's password'''
    #     try:
    #         user_ref = self.db.collection('users').document(user_id) # TODO: in production environment, it would be best to use firebase auth to reset password
            
    #         user_doc = user_ref.get()
    #         if not user_doc.exists:
    #             raise Exception('User not found')
            
    #         hashed_password = hashlib.sha256(new_password.encode()).hexdigest() # check back on hashing password functionality
            
    #         user_ref.update({'password': hashed_password})
    #         return True
    #     except Exception as e:
    #         print(f'Error in reset_user_password: {e}')
    #         raise e
    
    def delete_user(self, user_id, admin_id=None):
        '''Delete a user and their posts'''
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                raise Exception('User not found')
            
            user_data = user_doc.to_dict()
            
            # get user's posts
            posts_query = self.db.collection('posts').where('userId', '==', user_id).stream()
            post_ids = [doc.id for doc in posts_query]
            
            batch = self.db.batch() # use batch to delete user and posts all at once
            
            # delete user and associated posts
            batch.delete(user_ref)
            for post_id in post_ids:
                post_ref = self.db.collection('posts').document(post_id)
                batch.delete(post_ref)
            
            batch.commit() # commit batch
            
            # log action
            if admin_id:
                self.log_admin_action(admin_id, 'USER_DELETED', {
                    'user_id': user_id,
                    'username': user_data.get('username', ''),
                    'email': user_data.get('email', ''),
                    'posts_deleted': len(post_ids)
                })
            
            return {
                'success': True,
                'posts_deleted': len(post_ids)
            }
        except Exception as e:
            print(f'Error in delete_user: {e}')
            raise e
    
    def suspend_user(self, user_id, suspended=True, admin_id=None):
        '''Suspend or unsuspend a user account'''
        try:
            user_ref = self.db.collection('users').document(user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                raise Exception('User not found')
            
            user_data = user_doc.to_dict()
            user_ref.update({
                'suspended': suspended
            })
            
            if admin_id:
                action_type = 'USER_SUSPENDED' if suspended else 'USER_UNSUSPENDED'
                self.log_admin_action(admin_id, action_type, {
                    'user_id': user_id,
                    'username': user_data.get('username', ''),
                    'email': user_data.get('email', '')
                })
            
            return True
        except Exception as e:
            print(f'Error in suspend_user: {e}')
            raise e
    
    # Post Management methods
    
    def get_all_posts(self, limit=50, start_after=None):
        '''Get all posts with a specific limit'''
        try:
            query = (
                self.db.collection('posts')
                .order_by('createdAt', direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            
            if start_after: # if a post is provided to start after
                last_doc = self.db.collection('posts').document(start_after).get()
                if last_doc.exists:
                    query = query.start_after(last_doc)
            
            posts = []
            for doc in query.stream():
                post_data = doc.to_dict()
                post_data['id'] = doc.id
                
                # convert timestamp to str
                if 'createdAt' in post_data and post_data['createdAt']:
                    post_data['createdAt'] = post_data['createdAt'].isoformat()
                
                # count comments and likes
                post_data['commentCount'] = len(post_data.get('comments', []))
                post_data['likeCount'] = len(post_data.get('likes', []))
                posts.append(post_data)
            
            return {
                'posts': posts,
                'last_post': posts[-1]['id'] if posts else None
            }
        except Exception as e:
            print(f'Error in suspend_user: {e}')
            raise e
    
    def delete_post(self, post_id, admin_id=None):
        '''Delete a specified post'''
        try:
            post_ref = self.db.collection('posts').document(post_id)
            post_doc = post_ref.get()
            
            if not post_doc.exists:
                raise Exception('Post not found')
            
            post_data = post_doc.to_dict()
            
            post_ref.delete() # delete post
            
            if admin_id:
                self.log_admin_action(admin_id, 'POST_DELETED', {
                    'post_id': post_id,
                    'user_id': post_data.get('userId'),
                    'content_preview': post_data.get('content', '')[:50] + '...' if len(post_data.get('content', '')) > 50 else post_data.get('content', '')
                })
            
            return True
        except Exception as e:
            print(f'Error in delete_post: {e}')
            raise e
    
    def update_post_content(self, post_id, new_content, admin_id=None):
        '''Update a post's content'''
        try:
            post_ref = self.db.collection('posts').document(post_id)
            post_doc = post_ref.get()
            
            if not post_doc.exists:
                raise Exception('Post not found')
            
            old_content = post_doc.to_dict().get('content', '') # keep record for logging purpose
            
            # update post
            post_ref.update({
                'content': new_content,
                'editedAt': firestore.SERVER_TIMESTAMP,
                'editedByAdmin': True
            })
            
            # log action if we have the admin id
            if admin_id:
                self.log_admin_action(admin_id, 'POST_EDITED', {
                    'post_id': post_id,
                    'old_content_preview': old_content[:50] + '...' if len(old_content) > 50 else old_content,
                    'new_content_preview': new_content[:50] + '...' if len(new_content) > 50 else new_content
                })
            
            return True
        except Exception as e:
            print(f'Error in update_post_content: {e}')
            raise e
    
    def delete_comment(self, post_id, comment_id, admin_id=None):
        '''Delete a comment from a post'''
        try:
            post_ref = self.db.collection('posts').document(post_id)
            post_doc = post_ref.get()
            
            if not post_doc.exists:
                raise Exception('Post not found')
            
            post_data = post_doc.to_dict()
            comments = post_data.get('comments', [])
            
            # finding comment to delete
            comment_to_delete = None
            new_comments = []
            
            for comment in comments:
                if comment.get('id') == comment_id:
                    comment_to_delete = comment
                else:
                    new_comments.append(comment)
            
            if not comment_to_delete:
                raise Exception('Comment not found')
            
            post_ref.update({
                'comments': new_comments
            })
            
            if admin_id:
                self.log_admin_action(admin_id, 'COMMENT_DELETED', {
                    'post_id': post_id,
                    'comment_id': comment_id,
                    'user_id': comment_to_delete.get('userId'),
                    'content_preview': comment_to_delete.get('content', '')[:50] + '...' if len(comment_to_delete.get('content', '')) > 50 else comment_to_delete.get('content', '')
                })
            
            return True
        except Exception as e:
            print(f'Error in delete_comment: {e}')
            raise e

    # Analytics methods

    def get_analytics_summary(self, days=30): # Can be refactored
        '''Get summary analytics for the dashboard'''
        try:
            end_date = datetime.datetime.now()
            start_date = end_date - datetime.timedelta(days=days)
            
            # count users
            users_query = self.db.collection('users').stream()
            users_count = len(list(users_query))
            
            # count new users in period
            new_users_query = (
                self.db.collection('users')
                .where('createdAt', '>=', start_date)
                .stream()
            )
            new_users = len(list(new_users_query))
            
            # count total posts
            posts_query = self.db.collection('posts').stream()
            posts_count = len(list(posts_query))
            
            # count new posts in period
            new_posts_query = (
                self.db.collection('posts')
                .where('createdAt', '>=', start_date)
                .stream()
            )
            new_posts = len(list(new_posts_query))
            
            # count total comments
            total_comments = 0
            all_posts_query = self.db.collection('posts').stream()
            for post in all_posts_query:
                post_data = post.to_dict()
                total_comments += len(post_data.get('comments', []))
            
            # count new comments in period
            new_comments = 0
            all_posts_query = (
                self.db.collection('posts')
                .stream()
            )
            
            for post in all_posts_query:
                post_data = post.to_dict()
                for comment in post_data.get('comments', []):
                    comment_date = comment.get('createdAt', None)
                    if comment_date:
                        try:
                            comment_datetime = datetime.datetime.fromisoformat(comment_date.replace('Z', '+00:00'))
                            if comment_datetime >= start_date:
                                new_comments += 1
                        except (ValueError, TypeError):
                            pass # skip comments with invalid dates
            
            
            return {
                'total_users': users_count,
                'new_users': new_users,
                'total_posts': posts_count,
                'new_posts': new_posts,
                'total_comments': total_comments,
                'new_comments': new_comments,
                'period_days': days
            }
        except Exception as e:
            print(f'Error in get_analytics_summary: {e}')
            raise e
    
    # NOT USABLE
    # def get_task_analytics(self):
    #     '''Get analytics about tasks usage'''
    #     try:
    #         tasks_query = self.db.collection('tasks').stream() # get all tasks and then analyse categories
            
    #         # count tasks by category
    #         categories = dict()
    #         for doc in tasks_query:
    #             task = doc.to_dict()
    #             category = task.get('category', 'General')
    #             categories[category] = categories.get(category, 0) + 1
            
    #         # Get completion rate
    #         total_user_tasks_query = self.db.collection('user_tasks').stream()
    #         total_user_tasks_count = len(list(total_user_tasks_query))
            
    #         completed_user_tasks_query = (
    #             self.db.collection('user_tasks')
    #             .where('completed', '==', True)
    #             .stream()
    #         )
    #         completed_user_tasks_count = len(list(completed_user_tasks_query))
            
    #         completion_rate = 0
    #         if total_user_tasks_count > 0:
    #             completion_rate = (completed_user_tasks_count / total_user_tasks_count) * 100
            
    #         return {
    #             'categories': [{'name': k, 'count': v} for k, v in categories.items()],
    #             'completion_rate': completion_rate,
    #             'total_tasks_assigned': total_user_tasks_count,
    #             'tasks_completed': completed_user_tasks_count
    #         }
    #     except Exception as e:
    #         print(f'Error in get_task_analytics: {e}')
    #         raise e
    
    # def get_screentime_analytics(self): # ! This method uses a lot of db logic which might not follow the db structure, TO CHANGE to match associated structure
    #     '''Get analytics about screentime usage'''
    #     try:
    #         # get all screentime records
    #         screentime_query = self.db.collection('screentime').stream()
    #         screentime_records = [doc.to_dict() for doc in screentime_query]
            
    #         # calculate average daily screentime
    #         total_time = 0
    #         record_count = 0
            
    #         for record in screentime_records:
    #             total_time += record.get('duration', 0)
    #             record_count += 1
            
    #         avg_screentime = 0
    #         if record_count > 0:
    #             avg_screentime = total_time / record_count
            
    #         # calculate screentime by day of the week # ! Start of an intended feature of seeing screentime by day, unlikely to work with current structure
    #         days_of_week = {
    #         0: 'Monday',
    #         1: 'Tuesday',
    #         2: 'Wednesday',
    #         3: 'Thursday',
    #         4: 'Friday',
    #         5: 'Saturday',
    #         6: 'Sunday'
    #         }
            
    #         screentime_by_day = {day: 0 for day in days_of_week.values()}
    #         counts_by_day = {day: 0 for day in days_of_week.values()}
            
    #         for record in screentime_records:
    #             if 'timestamp' in record and record['timestamp']:
    #                 timestamp = record['timestamp']
    #                 if isinstance(timestamp, str):
    #                     timestamp = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    #                 day_name = days_of_week[timestamp.weekday()]
    #                 screentime_by_day[day_name] += record.get('duration', 0)
    #                 counts_by_day[day_name] += 1
            
    #         # calculate average by day
    #         avg_by_day = dict()
    #         for day in days_of_week.values():
    #             if counts_by_day[day] > 0:
    #                 avg_by_day[day] = screentime_by_day[day] / counts_by_day[day]
    #             else:
    #                 avg_by_day[day] = 0
            
    #         return {
    #             'average_daily_screentime': avg_screentime,
    #             'screentime_by_day': [{'day': day, 'average': average} for day, average in avg_by_day.items()]
    #         }
    #     except Exception as e:
    #         print(f'Error in get_screentime_analytics: {e}')
    #         raise e
    
    # Admin logs methods
    
    def log_admin_action(self, admin_id, action_type, details=None):
        '''Log an action taken/performed by an admin'''
        try:
            log_ref = self.db.collection('admin_logs').document()
            
            log_data = {
                'admin_id': admin_id,
                'action_type': action_type,
                'details': details or dict(),
                'timestamp': firestore.SERVER_TIMESTAMP,
                'ip_address': None # to get from the request in the actual route handler
            }
            
            log_ref.set(log_data)
            return log_ref.id
        except Exception as e:
            print(f'Error in log_admin_actions: {e}')
            raise e
    
    def get_admin_logs(self, limit=100):
        '''Get admin activity logs'''
        try:
            logs = []
            logs_query = (
                self.db.collection('admin_logs')
                .order_by('timestamp', direction=firestore.Query.DESCENDING)
                .limit(limit)
                .stream()
            )
            
            for doc in logs_query:
                log_data = doc.to_dict()
                log_data['id'] = doc.id
                
                if 'timestamp' in log_data and log_data['timestamp']: # convert time stamp to string if it exists
                    log_data['timestamp'] = log_data['timestamp'].isoformat()
                logs.append(log_data)
            
            return logs
        except Exception as e:
            print(f'Error in get_admins_logs: {e}')
            raise e
    
    # Community features
    
    def create_community_task(self, title, category, reward_minutes, deadline, admin_id=None):
        '''
        Create a new community task.
        Args: 
            title (str): Task title
            category (str): Task category
            reward_minutes (int): Reward_time in minutes
            deadline (datetime): Task deadline as Python datetime object
        Returns:
            dict: Created task data
        '''
        try: 
            
            community_task_query = self.db.collection('community_tasks').where('title', '==', title).limit(1).stream()
            if list(community_task_query):
                raise Exception('Community task with this title already exists')
            
            task_ref = self.db.collection('community_tasks').document()
            task_id = task_ref.id
            
            task_data = {
                'id': task_id,
                'title': title,
                'category': category,
                'reward_minutes': reward_minutes,
                'deadline': deadline,
                'created_at': firestore.SERVER_TIMESTAMP,
                'participants': [],
                'completed_by': [],
                'created_by': admin_id
            }
            
            task_ref.set(task_data)

            if admin_id:
                self.log_admin_action(admin_id, 'COMMUNITY_TASK_CREATED', {
                    'task_id': task_data['id'],
                    'title': task_data['title'],
                    'category': task_data['category'],
                    'reward_minutes': task_data['reward_minutes'],
                    'deadline': task_data['deadline'].isoformat()
                })
            
            response_data = task_data.copy()
            response_data.pop('created_at')
            if isinstance(response_data['deadline'], datetime.datetime):
                response_data['deadline'] = response_data['deadline'].isoformat()
            
            return response_data
        except Exception as e:
            print(f'Error in create_community_task: {e}')
            raise e
    
    def delete_community_task(self, task_id, admin_id=None):
        '''
        Delete a community task.
        Args:
            task_id (str): The id of the task to be deleted
        Returns:
            True: The task was successfully deleted
        '''
        try:
            community_task_ref = self.db.collection('community_tasks').document(task_id)
            community_task_doc = community_task_ref.get()
            
            if not community_task_doc.exists:
                raise Exception('Community task not found')
            
            community_task_data = community_task_doc.to_dict()
            
            # get metadata on the task deleted
            task_title = community_task_data.get('title', '')
            num_participants = len(community_task_data.get('participants', []))
            num_completed = len(community_task_data.get('completed_by', []))
            created_by = community_task_data.get('created_by', '')
            
            community_task_ref.delete()
            
            if admin_id:
                self.log_admin_action(admin_id, 'COMMUNITY_TASK_DELETED', {
                    'task_id': task_id,
                    'title': task_title,
                    'participants_count': num_participants,
                    'completed_count': num_completed,
                    'created_by': created_by
                })
            
            return True
        except Exception as e:
            print(f'Error in delete_community_task: {e}')
            raise e
    
    def get_community_tasks(self, limit=50, start_after=None):
        '''Get all community tasks with basic info'''
        try:
            query = (
                self.db.collection('community_tasks')
                .order_by('created_at', direction=firestore.Query.DESCENDING)
                .limit(limit)
            )
            
            if start_after:
                last_doc = self.db.collection('community_tasks').document(start_after).get()
                if last_doc.exists:
                    query = query.start_after(last_doc)
            
            tasks = []
            for doc in query.stream():
                task_data = doc.to_dict()
                task_data['id'] = doc.id
                
                if 'created_at' in task_data and task_data['created_at']:
                    task_data['created_at'] = task_data['created_at'].isoformat()
                if 'deadline' in task_data and task_data['deadline']:
                    if isinstance(task_data['deadline'], datetime.datetime):
                        task_data['deadline'] = task_data['deadline'].isoformat()
                
                task_data['participants_count'] = len(task_data.get('participants', []))
                task_data['completed_count'] = len(task_data.get('completed_by', []))
                
                tasks.append(task_data)

            return {
                'tasks': tasks,
                'last_task': tasks[-1]['id'] if tasks else None
            }
        except Exception as e:
            print(f'Error in get_community_tasks: {e}')
            raise e
    
    def get_community_task(self, task_id):
        '''Get details of a specific community task'''
        try:
            task_doc = self.db.collection('community_tasks').document(task_id).get()
            
            if not task_doc.exists:
                raise Exception('Community task not found')
            
            task_data = task_doc.to_dict()
            task_data['id'] = task_doc.id
            
            if 'created_at' in task_data and task_data['created_at']:
                    task_data['created_at'] = task_data['created_at'].isoformat()
            if 'deadline' in task_data and task_data['deadline']:
                if isinstance(task_data['deadline'], datetime.datetime):
                    task_data['deadline'] = task_data['deadline'].isoformat()
            
            participants = []
            if task_data.get('participants'):
                for participant_id in task_data['participants']:
                    user_doc = self.db.collection('users').document(participant_id).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        participants.append({
                            'id': participant_id,
                            'username': user_data.get('username', ''),
                            'email': user_data.get('email', '')
                        })
            
            completed_by = []
            if task_data.get('completed_by'):
                for participant_id in task_data['completed_by']:
                    user_doc = self.db.collection('users').document(participant_id).get()
                    if user_doc.exists:
                        user_data = user_doc.to_dict()
                        completed_by.append({
                            'id': participant_id,
                            'username': user_data.get('username', ''),
                            'email': user_data.get('email', '')
                        })
            
            task_data['participants'] = participants
            task_data['completed_by'] = completed_by
            
            return task_data
        except Exception as e:
            print(f'Error in get_community_task: {e}')
            raise e
    
    
    def create_community_task_category(self, category_name, category_type, description, admin_id=None):
        '''
        Create a new community task category.
        Args:
            category_name (str): The name of the category
            category_type (str): The type of category (e.g. social, sports, academic, etc)
            description (str): A brief description of the category.
        Returns:
            dict: Created category data
        '''
        try:
            
            category_query = self.db.collection('categories').where('category_name', '==', category_name).limit(1).stream()
            if list(category_query):
                raise Exception('Category with this name already exists')
            
            category_ref = self.db.collection('categories').document()
            category_id = category_ref.id
            
            category_data = {
                'id': category_id,
                'category_name': category_name,
                'category_type': category_type,
                'description': description,
                'created_at': firestore.SERVER_TIMESTAMP
            }
            category_ref.set(category_data)
            self.log_admin_action(admin_id, 'COMMUNITY_TASK_CATEGORY_CREATED', {
                'category': category_name
            })
            
            return {
                'category_name': category_name,
                'category_type' : category_type,
                'description': description
            }
        except Exception as e:
            print(f'Error in create_community_task_category: {e}')
            raise e
    
    def delete_community_task_category(self, category_id, admin_id=None):
        '''
        Delete a community task category
        Args:
            category_id (str): The id of the category to be deleted
        Returns:
            True: The task was successfully deleted
        '''
        try:
            community_task_category_ref = self.db.collection('categories').document(category_id)
            community_task_category_doc = community_task_category_ref.get()
            
            if not community_task_category_doc.exists:
                raise Exception('Community task category not found')
            
            community_task_category_data = community_task_category_doc.to_dict()
            
            community_task_category_ref.delete()
            
            if admin_id:
                self.log_admin_action(admin_id, 'COMMUNITY_TASK_CATEGORY_DELETED', {
                    'category_id': category_id,
                    'category_name': community_task_category_data.get('category_name', '')
                })
            
            return True
        except Exception as  e:
            print(f'Error in delete_community_task_category: {e}')
            raise e