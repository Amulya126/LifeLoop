import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "lifeloop_hackathon_secret_key"

def get_db_connection():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row
    
    # Automatically create all required tables if they don't exist
    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            category TEXT NOT NULL,
            scope TEXT NOT NULL,
            location TEXT NOT NULL
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS likes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER,
            user_id INTEGER,
            comment TEXT
        )
    ''')
    conn.commit()
    return conn

# UI Mappings for categories and scopes
CATEGORY_MAPPING = {
    "food": "Food & Nutrition",
    "medical": "Medical Support",
    "education": "Education & Tutoring",
    "general": "General Community Help"
}

SCOPE_MAPPING = {
    "local": "Local (Nearby Community)",
    "city": "City-wide",
    "online": "Online / Virtual"
}

@app.context_processor
def inject_mappings():
    return dict(category_mapping=CATEGORY_MAPPING, scope_mapping=SCOPE_MAPPING)

# --- HOME ROUTE ---
@app.route("/")
def home():
    conn = get_db_connection()
    total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    conn.close()
    return render_template("home.html", total_posts=total_posts)

# --- AUTHENTICATION ROUTES ---
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        if not name or not email or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))
            
        conn = get_db_connection()
        existing = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if existing:
            flash("Email already registered.")
            conn.close()
            return redirect(url_for("register"))
            
        conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
        conn.commit()
        conn.close()
        return redirect(url_for("login"))
        
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ? AND password = ?", (email, password)).fetchone()
        conn.close()
        
        if user:
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid email or password.")
            return redirect(url_for("login"))
            
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("home"))

# --- DASHBOARD & POST CRUD ROUTES ---
@app.route("/dashboard")
def dashboard():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_db_connection()
    posts = conn.execute("SELECT posts.*, users.name AS author FROM posts LEFT JOIN users ON posts.user_id = users.id ORDER BY posts.id DESC").fetchall()
    conn.close()
    return render_template("dashboard.html", posts=posts)
@app.route("/view-posts")
def view_posts():
    return redirect(url_for("dashboard"))

@app.route("/my-posts")
def my_posts():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_db_connection()
    posts = conn.execute("SELECT * FROM posts WHERE user_id = ? ORDER BY id DESC", (session["user_id"],)).fetchall()
    conn.close()
    return render_template("my_posts.html", posts=posts)

@app.route("/create", methods=["GET", "POST"])
def create_post():
    if not session.get("user_id"):
        return redirect(url_for("login"))
        
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category", "general")
        scope = request.form.get("scope", "local")
        location = request.form.get("location", "Community")
        
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO posts (user_id, title, description, category, scope, location) VALUES (?, ?, ?, ?, ?, ?)",
            (session["user_id"], title, description, category, scope, location)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("dashboard"))
        
    return render_template("create_post.html")

@app.route("/post/<int:post_id>")
def post_details(post_id):
    conn = get_db_connection()
    post = conn.execute("""
        SELECT posts.*, users.name AS author 
        FROM posts 
        LEFT JOIN users ON posts.user_id = users.id 
        WHERE posts.id = ?
    """, (post_id,)).fetchone()
    
    if not post:
        conn.close()
        return "Post not found", 404
        
    like_count = conn.execute(
        "SELECT COUNT(*) FROM likes WHERE post_id = ?", (post_id,)
    ).fetchone()[0]

    comments = conn.execute("""
        SELECT comments.*, users.name AS author
        FROM comments
        LEFT JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.id DESC
    """, (post_id,)).fetchall()
    
    conn.close()
    return render_template("post_details.html", post=post, like_count=like_count, comments=comments)
@app.route("/update/<int:post_id>", methods=["GET", "POST"])
def update_post(post_id):
    return edit_post(post_id)
@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    post = conn.execute("SELECT * FROM posts WHERE id = ? AND user_id = ?", (post_id, session["user_id"])).fetchone()
    
    if not post:
        conn.close()
        return "Unauthorized or Post not found", 403
        
    if request.method == "POST":
        title = request.form.get("title")
        description = request.form.get("description")
        category = request.form.get("category")
        scope = request.form.get("scope")
        location = request.form.get("location")
        
        conn.execute(
            "UPDATE posts SET title = ?, description = ?, category = ?, scope = ?, location = ? WHERE id = ?",
            (title, description, category, scope, location, post_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for("my_posts"))
        
    conn.close()
    return render_template("edit_post.html", post=post)

@app.route("/delete/<int:post_id>", methods=["POST"])
def delete_post(post_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    conn.execute("DELETE FROM posts WHERE id = ? AND user_id = ?", (post_id, session["user_id"]))
    conn.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    conn.commit()
    conn.close()
    return redirect(url_for("my_posts"))

# --- LIKES & COMMENTS ROUTES ---
@app.route("/like/<int:post_id>", methods=["POST"])
def like_post(post_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
        
    conn = get_db_connection()
    user_id = session["user_id"]
    
    existing = conn.execute(
        "SELECT * FROM likes WHERE post_id = ? AND user_id = ?", 
        (post_id, user_id)
    ).fetchone()
    
    if existing:
        conn.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?", (post_id, user_id))
    else:
        conn.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)", (post_id, user_id))
        
    conn.commit()
    conn.close()
    return redirect(url_for('post_details', post_id=post_id))

@app.route("/comment/<int:post_id>", methods=["POST"])
def add_comment(post_id):
    if not session.get("user_id"):
        return redirect(url_for("login"))
        
    comment_text = request.form.get("comment")
    if comment_text:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO comments (post_id, user_id, comment) VALUES (?, ?, ?)",
            (post_id, session["user_id"], comment_text)
        )
        conn.commit()
        conn.close()
        
    return redirect(url_for('post_details', post_id=post_id))

# --- MATCHES ROUTE ---
@app.route("/matches")
def matches():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    conn = get_db_connection()
    posts = conn.execute("SELECT * FROM posts ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("matches.html", posts=posts)

if __name__ == "__main__":
    app.run(debug=True)