from flask import request, render_template, redirect, url_for, session, send_file, flash, jsonify
from flask_socketio import emit
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
from app import db, socketio
from app.models import User, Scan
from app.predict import predict_image, generate_heatmap
from app.utils import generate_explanation, generate_pdf_report, generate_csv
import os

def init_routes(app):
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

    def role_required(*roles):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    return redirect(url_for('login'))
                user = User.query.get(session['user_id'])
                if user.role not in roles:
                    flash('Access denied')
                    return redirect(url_for('dashboard'))
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            user = User.query.filter_by(username=username).first()
            if user and check_password_hash(user.password, password):
                session['user_id'] = user.id
                return redirect(url_for('dashboard'))
            flash('Invalid username or password')
        print("Template directory:", app.template_folder)  # Debug
        try:
            return render_template('login.html')
        except Exception as e:
            print(f"Template error: {e}")  # Debug
            raise

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            role = request.form['role']
            print("Registering user:", username, role)  # Debug
            if role not in ['patient', 'doctor', 'researcher']:
                flash('Invalid role selected')
                return redirect(url_for('register'))
            if User.query.filter_by(username=username).first():
                flash('Username already exists')
                return redirect(url_for('register'))
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            new_user = User(username=username, password=hashed_password, role=role)
            db.session.add(new_user)
            db.session.commit()
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        return render_template('register.html')

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        scans = Scan.query.filter_by(user_id=user.id).order_by(Scan.date.desc()).all()
        valid_classes = ['AMD', 'CNV', 'CSR', 'DME', 'DR', 'DRUSEN', 'MH', 'NORMAL']
        prediction_counts = {cls: 0 for cls in valid_classes}
        for scan in scans:
            if scan.prediction in valid_classes:
                prediction_counts[scan.prediction] += 1
        print("Server-side Prediction Counts:", prediction_counts)  # Debug
        return render_template('dashboard.html', user=user, scans=scans, prediction_counts=prediction_counts)

    @app.route('/upload', methods=['GET', 'POST'])
    def upload():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file part')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No selected file')
                return redirect(request.url)
            if file and allowed_file(file.filename) and file.content_type in ['image/png', 'image/jpeg']:
                socketio.emit('progress', {'status': 'Uploading image...'}, namespace='/upload')
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)

                socketio.emit('progress', {'status': 'Processing image...'}, namespace='/upload')
                predicted_class, confidence = predict_image(file_path)

                # Generate a brief status message (same for all roles)
                status_message = f"The scan shows signs of {predicted_class} with {confidence:.2f}% confidence."

                socketio.emit('progress', {'status': 'Prediction complete!'}, namespace='/upload')
                new_scan = Scan(
                    user_id=session['user_id'],
                    image_path=file_path,
                    prediction=predicted_class,
                    confidence=confidence,
                    explanation=status_message  # Set brief status message
                )
                db.session.add(new_scan)
                db.session.commit()

                # Generate PDF report after saving the scan
                pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f'report_{new_scan.id}.pdf')
                try:
                    generate_pdf_report(new_scan, pdf_path)
                except Exception as e:
                    flash(f'Failed to generate PDF report: {str(e)}')
                    print(f"PDF generation error in upload: {e}")

                flash('Upload successful! Check the dashboard to ask questions about this scan.')
                return redirect(url_for('dashboard'))
        return render_template('upload.html', user=user)

    @app.route('/history')
    def history():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        scans = Scan.query.filter_by(user_id=session['user_id']).order_by(Scan.date.desc()).all()
        return render_template('history.html', user=user, scans=scans)

    @app.route('/heatmap/<int:scan_id>')
    def generate_heatmap_route(scan_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        scan = Scan.query.get_or_404(scan_id)
        if scan.user_id != session['user_id']:
            flash('Unauthorized access')
            return redirect(url_for('dashboard'))
        try:
            heatmap_path = generate_heatmap(scan.image_path, scan_id)
            return send_file(heatmap_path)
        except Exception as e:
            flash(f'Failed to generate heatmap: {str(e)}')
            return redirect(url_for('dashboard'))

    @app.route('/download_report/<int:scan_id>')
    def download_report(scan_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        scan = Scan.query.get_or_404(scan_id)
        if scan.user_id != session['user_id']:
            flash('Unauthorized access')
            return redirect(url_for('dashboard'))
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], f'report_{scan_id}.pdf')
        # Ensure the PDF exists; if not, generate it
        if not os.path.exists(pdf_path):
            try:
                generate_pdf_report(scan, pdf_path)
            except Exception as e:
                flash(f'Failed to generate PDF report: {str(e)}')
                return redirect(url_for('dashboard'))
        return send_file(pdf_path, as_attachment=True)

    @app.route('/ask_question/<int:scan_id>', methods=['POST'])
    def ask_question(scan_id):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        scan = Scan.query.get_or_404(scan_id)
        if scan.user_id != session['user_id']:
            flash('Unauthorized access')
            return redirect(url_for('dashboard'))
        user = User.query.get(session['user_id'])
        question = request.form['question']
        # Instruct the LLM to answer only the specific question
        prompt = f"Answer only the following question about the diagnosis '{scan.prediction}': {question}. Do not provide any additional information beyond what is asked."
        response = generate_explanation(scan.prediction, prompt, user.role)
        scan.explanation = f"{scan.explanation or ''}\n\nQuestion: {question}\nAnswer: {response}"
        db.session.commit()
        flash('Question answered! Check the dashboard for the response.')
        return redirect(url_for('dashboard'))

    @app.route('/export_history')
    def export_history():
        if 'user_id' not in session:
            return redirect(url_for('login'))
        scans = Scan.query.filter_by(user_id=session['user_id']).all()
        output = generate_csv(scans)
        return send_file(output, mimetype='text/csv', as_attachment=True, download_name='history.csv')

    @app.route('/logout')
    def logout():
        session.pop('user_id', None)
        flash('Logged out successfully')
        return redirect(url_for('login'))

    @app.route('/debug_static')
    def debug_static():
        static_path = app.static_folder
        css_exists = os.path.exists(os.path.join(static_path, 'css', 'styles.css'))
        js_exists = os.path.exists(os.path.join(static_path, 'js', 'scripts.js'))
        return jsonify({
            "static_folder": static_path,
            "styles.css_exists": css_exists,
            "scripts.js_exists": js_exists
        })