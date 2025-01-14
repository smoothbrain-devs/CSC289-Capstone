from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import sqlite3

app = Flask(__name__)
app.secret_key = 'this-is-a-secret-key'  # Secret key for session management
app.config['UPLOAD_FOLDER'] = 'static/uploads/'  # Directory for uploaded files

# Function to initialize the database with a users table
def init_db():
    """Initialize the database and create a 'users' & 'pets' table if it doesn't exist."""
    with sqlite3.connect('database.db') as conn:
        conn.execute('''
        CREATE TABLE IF NOT EXISTS users
        (username TEXT PRIMARY KEY,
         password TEXT NOT NULL,
         bio TEXT,
         profile_picture TEXT,
         joined_date DATE)
        ''')
        conn.execute('''
        CREATE TABLE IF NOT EXISTS pets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_username TEXT NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            type TEXT,
            profile_picture TEXT,
            FOREIGN KEY (owner_username) REFERENCES users(username)
        )
        ''')

# Initialize the database before the first request
@app.before_request
def before_first_request():
    """Run database initialization before the first request."""
    init_db()

# Context processor to make the username available globally in templates
@app.context_processor
def inject_user():
    """Inject the current logged-in username into all templates."""
    return dict(username=session.get('username'))

# Helper function to fetch user details from the database
def get_user_details(username):
    """Retrieve user details from the database by username.
    Args:
        username (str): The username of the user.
    Returns:
        tuple: A tuple containing user details (username, bio, profile_picture, joined_date).
    """
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT username, bio, profile_picture, joined_date FROM users WHERE username = ?', (username,))
        return c.fetchone()
    
def get_pet_details(username):
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute( 'SELECT * FROM pets WHERE owner_username = ?', (username,))
        return c.fetchall() 
    
@app.route('/add-pet', methods=['POST'])
def add_pet():
    """Handle the form submission to add a new pet."""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    pet_name = request.form['pet_name']
    pet_age = request.form['pet_age']
    pet_type = request.form['pet_type']
    
    print(f"Adding pet: {pet_name}, Age: {pet_age}, Type: {pet_type}")
    
    # Add the pet to the database
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('''
        INSERT INTO pets (owner_username, name, age, type)
        VALUES (?, ?, ?, ?)
        ''', (username, pet_name, pet_age, pet_type))
        conn.commit()
    
    return redirect(url_for('main'))

@app.route('/delete-pet/<int:pet_id>', methods=['POST'])
def delete_pet(pet_id):
    """Delete a pet from the database."""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']  # Ensure the user is authenticated

    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        
        # Ensure the pet belongs to the logged-in user
        c.execute('SELECT * FROM pets WHERE id = ? AND owner_username = ?', (pet_id, username))
        pet = c.fetchone()
        
        if pet:
            c.execute('DELETE FROM pets WHERE id = ?', (pet_id,))
            conn.commit()
            print(f"Deleted pet ID: {pet_id}")
        else:
            print(f"Unauthorized attempt to delete pet ID: {pet_id}")
    
    return redirect(url_for('main'))
# Route to display the main page or login page based on session state
@app.route('/')
def main():
    """Render the main page if logged in, otherwise render the login page."""
    
    if 'username' in session:
        user = get_user_details(session['username'])
        pets = get_pet_details(session['username'])
        return render_template('main.html', user=user, pets=pets)
    return render_template('login.html')

# Route for user login
@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login.
    GET: Render the login page.
    POST: Validate user credentials and log in the user.
    """
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Fetch user from the database
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('SELECT username, password FROM users WHERE username = ?', (username,))
            user = c.fetchone()
            
            # Validate password
            if user and check_password_hash(user[1], password):
                session['username'] = username
                return redirect(url_for('main'))
            message = 'Invalid username or password!'
        
    return render_template('login.html', message=message)

# Route for user logout
@app.route('/logout')
def logout():
    """Log out the user by clearing their session."""
    
    session.pop('username', None)
    return redirect(url_for('login'))

# Route for user registration
@app.route('/registration', methods=['GET', 'POST'])
def registration():
    """Handle user registration.
    GET: Render the registration page.
    POST: Create a new user account.
    """
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        joined_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Set the joined date
        try:
            # Insert new user into the database
            with sqlite3.connect('database.db') as conn:
                conn.execute(
                    'INSERT INTO users (username, password, bio, profile_picture, joined_date) VALUES (?, ?, ?, ?, ?)',
                    (username, password, None, None, joined_date)
                )
                return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            message = 'Username Already Exists'
            
    return render_template('registration.html', message=message)

# Route to display the user's profile
@app.route('/profile')
def profile():
    """Render the user's profile page if logged in."""
    if 'username' not in session:
        return redirect(url_for('login'))
    
    user = get_user_details(session['username'])
    if user:
        return render_template('profile.html', user=user)
    else:
        return "User not found", 404

# Route to edit the user's profile
@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    """Allow users to edit their profile, including bio and profile picture."""
    if 'username' not in session:
        return redirect(url_for('login'))

    user_id = session['username']
    
    # Fetch the current user details
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute('SELECT * FROM users WHERE username = ?', (user_id,))
        user = c.fetchone()
    
    if request.method == 'POST':
        new_bio = request.form['bio']
        file = request.files.get('profile_picture')
        
        # Use the existing profile picture if no new file is uploaded
        filename = user[3] if not file else secure_filename(file.filename)
        
        # Save the uploaded file
        if file:
            file.save(f'{app.config["UPLOAD_FOLDER"]}/{filename}')
        
        # Update user data in the database
        with sqlite3.connect('database.db') as conn:
            c = conn.cursor()
            c.execute('UPDATE users SET bio = ?, profile_picture = ? WHERE username = ?',
                      (new_bio, filename, user_id))
            conn.commit()
        
        return redirect(url_for('profile'))
    
    return render_template('edit_profile.html', user=user)

# Route to display the "About Us" page
@app.route('/about')
def about():
    """Render the About Us page."""
    user = get_user_details(session['username'])
    return render_template('about_us.html', user=user)

# Route to display the schedule page
@app.route('/schedule')
def schedule():
    """Render the schedule page."""
    user = get_user_details(session['username'])
    return render_template('schedule.html', user=user)

# Run the Flask app
if __name__ == '__main__':
    app.run(debug=True)
