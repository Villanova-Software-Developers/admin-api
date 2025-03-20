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
        # Check if admin with this email alr exists
        admins_ref = self.db.child('admins')
        admins = admins_ref.get() or {}
        
        for admin_id, main in admins.items():
            if admins.get('email') == email:
                raise Exception('Admin with this email already exists')
        
        admin_id = str(uuid.uuid4()) # create new admin user
        
        hashed_password = hashlib.sha256(password.encode()).hexdigest() # hashes the password, to change in prod for more secure hashing
        
        admin_data = {
            'id': admin_id,
            'email': email,
            'password': hashed_password, # to change in prod
            'name': name,
            'created_at': datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        admins_ref.child(admin_id).set(admin_data)
        
        admin_data.pop('password')
        return admin_data