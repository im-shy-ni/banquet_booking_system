from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector
import os
from werkzeug.utils import secure_filename
from datetime import date

app = Flask(__name__)
app.secret_key = 'banquet_secret_key'
UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)



db = mysql.connector.connect(
    host="shinkansen.proxy.rlwy.net",
    user="root",
    password="rwZuptDZnXzsTgBAfyFJoWwTvKXLQTWK",
    database="railway",
    port=37779
)

cursor = db.cursor(dictionary=True)


@app.route('/')
def index():
    cursor.execute("SELECT * FROM halls WHERE status='available' ORDER BY id DESC LIMIT 6")
    halls = cursor.fetchall()
    return render_template('index.html', halls=halls)


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if password != confirm_password:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        password = generate_password_hash(request.form['password'], method="pbkdf2:sha256")

        cursor.execute("SELECT * FROM users WHERE email=%s", (email,))
        existing_user = cursor.fetchone()

        if existing_user:
            flash('Email already exists')
            return redirect(url_for('register'))

        cursor.execute(
            "INSERT INTO users (name, email, phone, password, role) VALUES (%s, %s, %s, %s, %s)",
            (name, email, phone, password, 'user')
        )
        db.commit()
        flash('Registration successful. Please login.')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=%s AND role='user'", (email,))
        user = cursor.fetchone()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_role'] = user['role']
            flash('Login successful')
            return redirect(url_for('index'))
        else:
            flash('Invalid user credentials')
            return redirect(url_for('login'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully')
    return redirect(url_for('index'))


@app.route('/halls')
def halls():
    search = request.args.get('search')

    if search:
        cursor.execute(
            "SELECT * FROM halls WHERE status='available' AND hall_name LIKE %s",
            ('%' + search + '%',)
        )
    else:
        cursor.execute("SELECT * FROM halls WHERE status='available'")

    halls = cursor.fetchall()
    return render_template('halls.html', halls=halls)


@app.route('/hall/<int:hall_id>')
def hall_details(hall_id):
    cursor.execute("SELECT * FROM halls WHERE id=%s", (hall_id,))
    hall = cursor.fetchone()
    return render_template('hall_details.html', hall=hall)


@app.route('/booking/<int:hall_id>', methods=['GET', 'POST'])
def booking(hall_id):
    if 'user_id' not in session:
        flash('Please login first')
        return redirect(url_for('login'))

    cursor.execute("SELECT * FROM halls WHERE id=%s", (hall_id,))
    hall = cursor.fetchone()

    if not hall:
        flash('Hall not found')
        return redirect(url_for('halls'))

    if request.method == 'POST':
        event_type = request.form['event_type']
        event_date = request.form['event_date']
        guests = request.form['guests']
        message = request.form['message']

        selected_date = date.fromisoformat(event_date)

        if selected_date < date.today():
            flash('Past dates are not allowed for booking')
            return redirect(url_for('booking', hall_id=hall_id))

        if int(guests) > int(hall['capacity']):
            flash('Number of guests exceeds hall capacity')
            return redirect(url_for('booking', hall_id=hall_id))

        cursor.execute("""
            SELECT * FROM bookings
            WHERE hall_id=%s AND event_date=%s AND booking_status='approved'
        """, (hall_id, event_date))
        existing = cursor.fetchone()

        if existing:
            flash('This hall is already booked on this date')
            return redirect(url_for('booking', hall_id=hall_id))

        cursor.execute(
            "INSERT INTO bookings (user_id, hall_id, event_type, event_date, guests, message) VALUES (%s, %s, %s, %s, %s, %s)",
            (session['user_id'], hall_id, event_type, event_date, guests, message)
        )
        db.commit()

        flash('Booking request sent successfully')
        return redirect(url_for('my_bookings'))

    return render_template('booking.html', hall=hall, date_today=date.today())


@app.route('/my-bookings')
def my_bookings():
    if 'user_id' not in session:
        flash('Please login first')
        return redirect(url_for('login'))

    cursor.execute("""
        SELECT bookings.*, halls.hall_name, halls.location
        FROM bookings
        JOIN halls ON bookings.hall_id = halls.id
        WHERE bookings.user_id = %s
        ORDER BY bookings.id DESC
    """, (session['user_id'],))
    bookings = cursor.fetchall()

    return render_template('my_bookings.html', bookings=bookings)


@app.route('/cancel-booking/<int:booking_id>')
def cancel_booking(booking_id):
    if 'user_id' not in session:
        flash('Please login first')
        return redirect(url_for('login'))

    cursor.execute(
        "DELETE FROM bookings WHERE id=%s AND user_id=%s AND booking_status='pending'",
        (booking_id, session['user_id'])
    )
    db.commit()

    flash('Booking cancelled successfully')
    return redirect(url_for('my_bookings'))


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        subject = request.form['subject']
        message = request.form['message']

        cursor.execute(
            "INSERT INTO contact_messages (name, email, subject, message) VALUES (%s, %s, %s, %s)",
            (name, email, subject, message)
        )
        db.commit()
        flash('Message sent successfully')
        return redirect(url_for('contact'))

    return render_template('contact.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cursor.execute("SELECT * FROM users WHERE email=%s AND role='admin'", (email,))
        admin = cursor.fetchone()

        if admin and check_password_hash(admin['password'], password):
            session['admin_id'] = admin['id']
            session['admin_name'] = admin['name']
            session['admin_role'] = admin['role']
            flash('Admin login successful')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid admin credentials')
            return redirect(url_for('admin_login'))

    return render_template('admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("SELECT COUNT(*) AS total_users FROM users WHERE role='user'")
    total_users = cursor.fetchone()['total_users']

    cursor.execute("SELECT COUNT(*) AS total_halls FROM halls")
    total_halls = cursor.fetchone()['total_halls']

    cursor.execute("SELECT COUNT(*) AS total_bookings FROM bookings")
    total_bookings = cursor.fetchone()['total_bookings']

    cursor.execute("SELECT COUNT(*) AS total_messages FROM contact_messages")
    total_messages = cursor.fetchone()['total_messages']

    return render_template(
        'admin_dashboard.html',
        total_users=total_users,
        total_halls=total_halls,
        total_bookings=total_bookings,
        total_messages=total_messages
    )


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    flash('Admin logged out successfully')
    return redirect(url_for('admin_login'))


@app.route('/admin/halls')
def admin_halls():
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("SELECT * FROM halls ORDER BY id DESC")
    halls = cursor.fetchall()
    return render_template('admin_halls.html', halls=halls)


@app.route('/admin/add-hall', methods=['GET', 'POST'])
def add_hall():
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        hall_name = request.form['hall_name']
        location = request.form['location']
        capacity = request.form['capacity']
        price = request.form['price']
        description = request.form['description']
        status = request.form['status']

        file = request.files.get('image')
        filename = None

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute("""
            INSERT INTO halls (hall_name, location, capacity, price, description, image, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (hall_name, location, capacity, price, description, filename, status))
        db.commit()

        flash('Hall added successfully')
        return redirect(url_for('admin_halls'))

    return render_template('add_hall.html')


@app.route('/admin/edit-hall/<int:hall_id>', methods=['GET', 'POST'])
def edit_hall(hall_id):
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("SELECT * FROM halls WHERE id=%s", (hall_id,))
    hall = cursor.fetchone()

    if not hall:
        flash('Hall not found')
        return redirect(url_for('admin_halls'))

    if request.method == 'POST':
        hall_name = request.form['hall_name']
        location = request.form['location']
        capacity = request.form['capacity']
        price = request.form['price']
        description = request.form['description']
        status = request.form['status']

        file = request.files.get('image')
        filename = hall['image']

        if file and file.filename != '':
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        cursor.execute("""
            UPDATE halls
            SET hall_name=%s, location=%s, capacity=%s, price=%s, description=%s, image=%s, status=%s
            WHERE id=%s
        """, (hall_name, location, capacity, price, description, filename, status, hall_id))
        db.commit()

        flash('Hall updated successfully')
        return redirect(url_for('admin_halls'))

    return render_template('edit_hall.html', hall=hall)


@app.route('/admin/delete-hall/<int:hall_id>')
def delete_hall(hall_id):
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("DELETE FROM halls WHERE id=%s", (hall_id,))
    db.commit()

    flash('Hall deleted successfully')
    return redirect(url_for('admin_halls'))


@app.route('/admin/bookings')
def admin_bookings():
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("""
        SELECT bookings.*, users.name AS user_name, users.email AS user_email,
               halls.hall_name, halls.location
        FROM bookings
        JOIN users ON bookings.user_id = users.id
        JOIN halls ON bookings.hall_id = halls.id
        ORDER BY bookings.id DESC
    """)
    bookings = cursor.fetchall()

    return render_template('admin_bookings.html', bookings=bookings)


@app.route('/admin/update-booking-status/<int:booking_id>/<status>')
def update_booking_status(booking_id, status):
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    if status not in ['approved', 'rejected', 'pending']:
        flash('Invalid status')
        return redirect(url_for('admin_bookings'))

    cursor.execute("UPDATE bookings SET booking_status=%s WHERE id=%s", (status, booking_id))
    db.commit()

    flash('Booking status updated successfully')
    return redirect(url_for('admin_bookings'))


@app.route('/admin/users')
def admin_users():
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("SELECT * FROM users WHERE role='user' ORDER BY id DESC")
    users = cursor.fetchall()
    return render_template('admin_users.html', users=users)


@app.route('/admin/messages')
def admin_messages():
    if 'admin_id' not in session:
        flash('Please login as admin')
        return redirect(url_for('admin_login'))

    cursor.execute("SELECT * FROM contact_messages ORDER BY id DESC")
    messages = cursor.fetchall()
    return render_template('admin_messages.html', messages=messages)


if __name__ == '__main__':
    app.run()
