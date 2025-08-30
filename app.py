# app.py - Main Flask Application for Footwear E-commerce
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
#from werkzeug.utils import secure_filename
import sqlite3
import os
import uuid

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production
app.config['UPLOAD_FOLDER'] = 'static/images'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Database initialization
def init_db():
    conn = sqlite3.connect('footwear_store.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        is_admin INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Products table
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        brand TEXT NOT NULL,
        category TEXT NOT NULL,
        size TEXT NOT NULL,
        color TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL,
        description TEXT,
        image_url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # Cart table
    c.execute('''CREATE TABLE IF NOT EXISTS cart (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )''')
    
    # Orders table
    c.execute('''CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        total_amount REAL NOT NULL,
        status TEXT DEFAULT 'pending',
        shipping_address TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    # Order items table
    c.execute('''CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER,
        product_id INTEGER,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    )''')
    
    # Create admin user if doesn't exist
    c.execute("SELECT * FROM users WHERE username = 'admin'")
    if not c.fetchone():
        admin_password = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, email, password_hash, is_admin) VALUES (?, ?, ?, ?)",
                 ('admin', 'admin@footwear.com', admin_password, 1))
    
    # Add sample products if table is empty
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        sample_products = [
            ('Nike Air Max 270', 'Nike', 'Running', '9', 'Black', 129.99, 50, 'Comfortable running shoes with air cushioning'),
            ('Adidas Ultraboost 22', 'Adidas', 'Running', '10', 'White', 189.99, 30, 'Premium running shoes with boost technology'),
            ('Converse Chuck Taylor', 'Converse', 'Casual', '8', 'Red', 59.99, 75, 'Classic high-top sneakers'),
            ('Vans Old Skool', 'Vans', 'Casual', '9', 'Black/White', 69.99, 60, 'Iconic skate shoes with waffle sole'),
            ('Dr. Martens 1460', 'Dr. Martens', 'Boots', '10', 'Black', 169.99, 25, 'Classic leather boots with air-cushioned sole'),
            ('Timberland Premium Boot', 'Timberland', 'Boots', '11', 'Wheat', 199.99, 35, 'Waterproof leather boots')
        ]
        c.executemany("INSERT INTO products (name, brand, category, size, color, price, stock, description) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sample_products)
    
    conn.commit()
    conn.close()

# Database helper functions
def get_db_connection():
    conn = sqlite3.connect('footwear_store.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_username(username):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

def get_products(category=None, search=None):
    conn = get_db_connection()
    query = 'SELECT * FROM products WHERE stock > 0'
    params = []
    
    if category:
        query += ' AND category = ?'
        params.append(category)
    
    if search:
        query += ' AND (name LIKE ? OR brand LIKE ? OR description LIKE ?)'
        search_term = f'%{search}%'
        params.extend([search_term, search_term, search_term])
    
    query += ' ORDER BY created_at DESC'
    products = conn.execute(query, params).fetchall()
    conn.close()
    return products

def get_product_by_id(product_id):
    conn = get_db_connection()
    product = conn.execute('SELECT * FROM products WHERE id = ?', (product_id,)).fetchone()
    conn.close()
    return product

def get_cart_items(user_id):
    conn = get_db_connection()
    items = conn.execute('''
        SELECT c.*, p.name, p.brand, p.price, p.image_url, (c.quantity * p.price) as subtotal
        FROM cart c
        JOIN products p ON c.product_id = p.id
        WHERE c.user_id = ?
    ''', (user_id,)).fetchall()
    conn.close()
    return items

# Routes
@app.route('/')
def index():
    products = get_products()
    categories = ['Running', 'Casual', 'Boots', 'Formal', 'Sports']
    return render_template('index.html', products=products, categories=categories)

@app.route('/category/<category>')
def category_products(category):
    products = get_products(category=category)
    categories = ['Running', 'Casual', 'Boots', 'Formal', 'Sports']
    return render_template('category.html', products=products, category=category, categories=categories)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    products = get_products(search=query)
    return render_template('search_results.html', products=products, query=query)

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = get_product_by_id(product_id)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('index'))
    return render_template('product_detail.html', product=product)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        
        # Check if user exists
        existing_user = conn.execute('SELECT id FROM users WHERE username = ? OR email = ?', (username, email)).fetchone()
        if existing_user:
            flash('Username or email already exists', 'error')
            conn.close()
            return render_template('register.html')
        
        # Create new user
        password_hash = generate_password_hash(password)
        conn.execute('INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, password_hash))
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = get_user_by_username(username)
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            flash(f'Welcome back, {username}!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    if 'user_id' not in session:
        flash('Please log in to add items to cart', 'error')
        return redirect(url_for('login'))
    
    product = get_product_by_id(product_id)
    if not product:
        flash('Product not found', 'error')
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    
    # Check if item already in cart
    existing_item = conn.execute('SELECT * FROM cart WHERE user_id = ? AND product_id = ?',
                                (session['user_id'], product_id)).fetchone()
    
    if existing_item:
        # Update quantity
        new_quantity = existing_item['quantity'] + 1
        if new_quantity <= product['stock']:
            conn.execute('UPDATE cart SET quantity = ? WHERE user_id = ? AND product_id = ?',
                        (new_quantity, session['user_id'], product_id))
            flash('Cart updated successfully', 'success')
        else:
            flash('Not enough stock available', 'error')
    else:
        # Add new item
        conn.execute('INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, ?)',
                    (session['user_id'], product_id, 1))
        flash('Item added to cart', 'success')
    
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))

@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash('Please log in to view cart', 'error')
        return redirect(url_for('login'))
    
    items = get_cart_items(session['user_id'])
    total = sum(item['subtotal'] for item in items)
    return render_template('cart.html', items=items, total=total)

@app.route('/update_cart', methods=['POST'])
def update_cart():
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    cart_id = request.json.get('cart_id')
    quantity = request.json.get('quantity')
    
    if quantity < 1:
        return jsonify({'success': False, 'message': 'Invalid quantity'})
    
    conn = get_db_connection()
    conn.execute('UPDATE cart SET quantity = ? WHERE id = ? AND user_id = ?',
                (quantity, cart_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/remove_from_cart/<int:cart_id>')
def remove_from_cart(cart_id):
    if 'user_id' not in session:
        flash('Please log in', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    conn.execute('DELETE FROM cart WHERE id = ? AND user_id = ?', (cart_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Item removed from cart', 'success')
    return redirect(url_for('cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash('Please log in to checkout', 'error')
        return redirect(url_for('login'))
    
    items = get_cart_items(session['user_id'])
    if not items:
        flash('Your cart is empty', 'error')
        return redirect(url_for('cart'))
    
    total = sum(item['subtotal'] for item in items)
    
    if request.method == 'POST':
        shipping_address = request.form['shipping_address']
        
        conn = get_db_connection()
        
        # Create order
        order_id = str(uuid.uuid4())
        conn.execute('INSERT INTO orders (user_id, total_amount, shipping_address) VALUES (?, ?, ?)',
                    (session['user_id'], total, shipping_address))
        
        order_id = conn.lastrowid
        
        # Add order items and update stock
        for item in items:
            conn.execute('INSERT INTO order_items (order_id, product_id, quantity, price) VALUES (?, ?, ?, ?)',
                        (order_id, item['product_id'], item['quantity'], item['price']))
            conn.execute('UPDATE products SET stock = stock - ? WHERE id = ?',
                        (item['quantity'], item['product_id']))
        
        # Clear cart
        conn.execute('DELETE FROM cart WHERE user_id = ?', (session['user_id'],))
        
        conn.commit()
        conn.close()
        
        flash('Order placed successfully!', 'success')
        return redirect(url_for('order_confirmation', order_id=order_id))
    
    return render_template('checkout.html', items=items, total=total)

@app.route('/order_confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'user_id' not in session:
        flash('Please log in', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = ? AND user_id = ?',
                        (order_id, session['user_id'])).fetchone()
    
    if not order:
        flash('Order not found', 'error')
        return redirect(url_for('index'))
    
    order_items = conn.execute('''
        SELECT oi.*, p.name, p.brand
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    
    conn.close()
    
    return render_template('order_confirmation.html', order=order, items=order_items)

@app.route('/admin')
def admin_dashboard():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Admin access required', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    
    # Get statistics
    total_products = conn.execute('SELECT COUNT(*) as count FROM products').fetchone()['count']
    total_orders = conn.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count']
    total_users = conn.execute('SELECT COUNT(*) as count FROM users WHERE is_admin = 0').fetchone()['count']
    total_revenue = conn.execute('SELECT SUM(total_amount) as revenue FROM orders').fetchone()['revenue'] or 0
    
    # Recent orders
    recent_orders = conn.execute('''
        SELECT o.*, u.username
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.created_at DESC
        LIMIT 5
    ''').fetchall()
    
    conn.close()
    
    stats = {
        'total_products': total_products,
        'total_orders': total_orders,
        'total_users': total_users,
        'total_revenue': total_revenue
    }
    
    return render_template('admin_dashboard.html', stats=stats, recent_orders=recent_orders)

@app.route('/admin/products')
def admin_products():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Admin access required', 'error')
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    products = conn.execute('SELECT * FROM products ORDER BY created_at DESC').fetchall()
    conn.close()
    
    return render_template('admin_products.html', products=products)

@app.route('/admin/add_product', methods=['GET', 'POST'])
def admin_add_product():
    if 'user_id' not in session or not session.get('is_admin'):
        flash('Admin access required', 'error')
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        name = request.form['name']
        brand = request.form['brand']
        category = request.form['category']
        size = request.form['size']
        color = request.form['color']
        price = float(request.form['price'])
        stock = int(request.form['stock'])
        description = request.form['description']
        
        conn = get_db_connection()
        conn.execute('''INSERT INTO products 
                        (name, brand, category, size, color, price, stock, description) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                    (name, brand, category, size, color, price, stock, description))
        conn.commit()
        conn.close()
        
        flash('Product added successfully!', 'success')
        return redirect(url_for('admin_products'))
    
    categories = ['Running', 'Casual', 'Boots', 'Formal', 'Sports']
    return render_template('admin_add_product.html', categories=categories)

if __name__ == '__main__':
    init_db()
    app.run(debug=True)