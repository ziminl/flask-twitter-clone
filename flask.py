import os
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import sqlite3

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def get_db_connection():
    conn = sqlite3.connect('twitter_clone.db')
    conn.row_factory = sqlite3.Row
    return conn

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    conn = get_db_connection()
    tweets = conn.execute("SELECT t.*, u.username FROM tweets t JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC").fetchall()
    conn.close()
    return render_template('index.html', tweets=tweets)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, email)).fetchone()

        if user:
            conn.close()
            flash('Username or email already taken.', 'error')
        else:
            hashed_password = generate_password_hash(password, method='sha256')
            conn.execute("INSERT INTO users (username, password, email) VALUES (?, ?, ?)", (username, hashed_password, email))
            conn.commit()
            conn.close()

            flash('Registration successful. Please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            flash('Logged in successfully.', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    current_user_id = session.get('user_id')
    if current_user_id:
        conn = get_db_connection()

        if request.method == 'POST':
            name = request.form['name']
            bio = request.form['bio']
            avatar = request.files['avatar']

            if avatar and allowed_file(avatar.filename):
                filename = secure_filename(avatar.filename)
                avatar.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                conn.execute("UPDATE users SET name = ?, bio = ?, avatar_url = ? WHERE id = ?", (name, bio, filename, current_user_id))
            else:
                conn.execute("UPDATE users SET name = ?, bio = ? WHERE id = ?", (name, bio, current_user_id))

            conn.commit()

        user = conn.execute("SELECT * FROM users WHERE id = ?", (current_user_id,)).fetchone()
        tweets = conn.execute("SELECT * FROM tweets WHERE user_id = ? ORDER BY created_at DESC", (current_user_id,)).fetchall()

        conn.close()
        return render_template('profile.html', user=user, tweets=tweets)
    else:
        flash('Please log in to access your profile.', 'error')
        return redirect(url_for('login'))

@app.route('/timeline')
def timeline():
    current_user_id = session.get('user_id')
    if current_user_id:
        conn = get_db_connection()
        tweets = conn.execute("SELECT t.*, u.username FROM tweets t JOIN users u ON t.user_id = u.id WHERE t.user_id = ? OR t.user_id IN (SELECT following_id FROM follows WHERE user_id = ?) ORDER BY t.created_at DESC", (current_user_id, current_user_id)).fetchall()
        conn.close()
        return render_template('timeline.html', tweets=tweets)
    else:
        flash('Please log in to view your timeline.', 'error')
        return redirect(url_for('login'))

@app.route('/public_feed')
def public_feed():
    conn = get_db_connection()
    tweets = conn.execute("SELECT t.*, u.username FROM tweets t JOIN users u ON t.user_id = u.id WHERE t.is_private = 0 ORDER BY t.created_at DESC").fetchall()
    conn.close()
    return render_template('public_feed.html', tweets=tweets)

@app.route('/follow/<int:user_id>')
def follow(user_id):
    current_user_id = session.get('user_id')
    if current_user_id:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()

        if user:
            follow = conn.execute("SELECT * FROM follows WHERE user_id = ? AND following_id = ?", (current_user_id, user_id)).fetchone()

            if follow:
                conn.execute("DELETE FROM follows WHERE user_id = ? AND following_id = ?", (current_user_id, user_id))
                conn.commit()

                conn.close()
                flash('You have unfollowed this user.', 'success')
            else:
                conn.execute("INSERT INTO follows (user_id, following_id) VALUES (?, ?)", (current_user_id, user_id))
                conn.commit()

                conn.close()
                flash('You are now following this user.', 'success')
        else:
            conn.close()
            flash('The user you are trying to follow does not exist.', 'error')

        return redirect(url_for('profile'))
    else:
        flash('Please log in to follow users.', 'error')
        return redirect(url_for('login'))

@app.route('/like/<int:tweet_id>')
def like(tweet_id):
    current_user_id = session.get('user_id')
    if current_user_id:
        conn = get_db_connection()
        tweet = conn.execute("SELECT * FROM tweets WHERE id = ? AND (user_id = ? OR is_private = 0 OR user_id IN (SELECT following_id FROM follows WHERE user_id = ?))", (tweet_id, current_user_id, current_user_id)).fetchone()

        if tweet:
            like = conn.execute("SELECT * FROM likes WHERE user_id = ? AND tweet_id = ?", (current_user_id, tweet_id)).fetchone()

            if like:
                conn.execute("DELETE FROM likes WHERE user_id = ? AND tweet_id = ?", (current_user_id, tweet_id))
                conn.commit()

                conn.close()
                flash('You have unliked this tweet.', 'success')
            else:
                conn.execute("INSERT INTO likes (user_id, tweet_id) VALUES (?, ?)", (current_user_id, tweet_id))
                conn.commit()

                conn.close()
                flash('You have liked this tweet.', 'success')
        else:
            conn.close()
            flash('The tweet you are trying to like does not exist or is not visible to you.', 'error')

        return redirect(url_for('index'))
    else:
        flash('Please log in to like tweets.', 'error')
        return redirect(url_for('login'))

@app.route('/retweet/<int:tweet_id>')
def retweet(tweet_id):
    current_user_id = session.get('user_id')
    if current_user_id:
        conn = get_db_connection()
        tweet = conn.execute("SELECT * FROM tweets WHERE id = ? AND (user_id = ? OR is_private = 0 OR user_id IN (SELECT following_id FROM follows WHERE user_id = ?))", (tweet_id, current_user_id, current_user_id)).fetchone()

        if tweet:
            retweet = conn.execute("SELECT * FROM retweets WHERE user_id = ? AND tweet_id = ?", (current_user_id, tweet_id)).fetchone()

            if retweet:
                conn.execute("DELETE FROM retweets WHERE user_id = ? AND tweet_id = ?", (current_user_id, tweet_id))
                conn.commit()

                conn.close()
                flash('You have unretweeted this tweet.', 'success')
            else:
                conn.execute("INSERT INTO retweets (user_id, tweet_id) VALUES (?, ?)", (current_user_id, tweet_id))
                conn.commit()

                conn.close()
                flash('You have retweeted this tweet.', 'success')
        else:
            conn.close()
            flash('The tweet you are trying to retweet does not exist or is not visible to you.', 'error')

        return redirect(url_for('index'))
    else:
        flash('Please log in to retweet tweets.', 'error')
        return redirect(url_for('login'))

@app.route('/post_tweet', methods=['POST'])
def post_tweet():
    current_user_id = session.get('user_id')
    if current_user_id:
        tweet_text = request.form['tweet_text']
        is_private = request.form.get('is_private', 0)

        conn = get_db_connection()
        conn.execute("INSERT INTO tweets (user_id, tweet_text, is_private) VALUES (?, ?, ?)", (current_user_id, tweet_text, is_private))
        conn.commit()

        conn.close()
        flash('Tweet posted successfully.', 'success')
    else:
        flash('Please log in to post tweets.', 'error')

    return redirect(url_for('index'))

@app.route('/delete_tweet/<int:tweet_id>')
def delete_tweet(tweet_id):
    current_user_id = session.get('user_id')
    if current_user_id:
        conn = get_db_connection()
        tweet = conn.execute("SELECT * FROM tweets WHERE id = ? AND user_id = ?", (tweet_id, current_user_id)).fetchone()

        if tweet:
            conn.execute("DELETE FROM tweets WHERE id = ?", (tweet_id,))
            conn.commit()

            conn.close()
            flash('Tweet deleted successfully.', 'success')
        else:
            conn.close()
            flash('You are not authorized to delete this tweet.', 'error')

        return redirect(url_for('index'))
    else:
        flash('Please log in to delete tweets.', 'error')
        return redirect(url_for('login'))

@app.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        search_query = request.form['search_query']
    else:
        search_query = request.args.get('q', '')

    conn = get_db_connection()
    users = conn.execute("SELECT * FROM users WHERE username LIKE ?", ('%' + search_query + '%',)).fetchall()
    tweets = conn.execute("SELECT t.*, u.username FROM tweets t JOIN users u ON t.user_id = u.id WHERE t.tweet_text LIKE ? ORDER BY t.created_at DESC", ('%' + search_query + '%',)).fetchall()

    conn.close()
    return render_template('search_results.html', users=users, tweets=tweets, search_query=search_query)

@app.route('/explore')
def explore():
    conn = get_db_connection()
    trending_topics = conn.execute("SELECT topic FROM trending_topics ORDER BY tweet_count DESC LIMIT 10").fetchall()
    popular_users = conn.execute("SELECT u.*, COUNT(f.id) AS follower_count FROM users u LEFT JOIN follows f ON u.id = f.following_id GROUP BY u.id ORDER BY follower_count DESC LIMIT 10").fetchall()
    conn.close()
    return render_template('explore.html', trending_topics=trending_topics, popular_users=popular_users)

if __name__ == '__main__':
    conn = sqlite3.connect('twitter_clone.db')
    with app.open_resource('schema.sql', mode='r') as f:
        conn.executescript(f.read())
    conn.close()

    app.run(debug=True)
