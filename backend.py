from flask import Flask, request, render_template, redirect, url_for, Response, session, flash
from uranus import Uranus, CustomError
from waitress import serve
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json, csv
import uuid
import pandas as pd
import bcrypt
import os
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Set default values if environment variables are not set
app.secret_key = os.getenv('SECRET_KEY')
admin_password = os.getenv('ADMIN_PASSWORD')
PASSWORD_HASH = bcrypt.hashpw(admin_password.encode('utf-8'), bcrypt.gensalt())



app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI', 'sqlite:///data.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

global user_name
user_name = "NULL"

@app.context_processor
def inject_globals():
    return {'datetime': datetime, 'enumerate': enumerate, "getattr": getattr}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin'))
        return f(*args, **kwargs)
    return decorated_function


# Definicja modelu danych
class PrioritizedRisks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    starttime = db.Column(db.String(255), nullable=False)
    stoptime = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    risk_number = db.Column(db.Integer, nullable=False)
    risk_name = db.Column(db.Text, nullable=False)
    risk_priority = db.Column(db.Integer, nullable=False)
    
class ClassicRisks(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    starttime = db.Column(db.String(255), nullable=False)
    stoptime = db.Column(db.String(255), nullable=False)
    username = db.Column(db.String(255), nullable=False)
    risk_number = db.Column(db.Integer, nullable=False)
    risk_name = db.Column(db.Text, nullable=False)
    impact = db.Column(db.Integer, nullable=False)
    probability = db.Column(db.Integer, nullable=False)
    risk_priority = db.Column(db.Integer, nullable=False)
   
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ClassicResults(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.user_id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    risk_id = db.Column(db.Integer, nullable=False)
    risk_name = db.Column(db.Text, nullable=False)
    impact = db.Column(db.Integer, nullable=False)
    probability = db.Column(db.Integer, nullable=False)
    priority = db.Column(db.Integer, nullable=False)


class NoveltyResults(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.user_id'), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    risk_a_id = db.Column(db.Integer, nullable=False)
    risk_a_description = db.Column(db.Text, nullable=False)
    risk_b_id = db.Column(db.Integer, nullable=False)
    risk_b_description = db.Column(db.Text, nullable=False)
    chosen_risk = db.Column(db.String(1), nullable=False)
    parameter = db.Column(db.String(255), nullable=False)


def load_values_from_json(file_path, content):
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
        datatoreturn = data[content]
    return datatoreturn

file_path = 'config.json'
values = load_values_from_json(file_path,'risks')

global u, start_time
u = Uranus(['impact', 'probability'], values)

start_time = datetime.now()


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        password = request.form.get('password').encode('utf-8')
        if bcrypt.checkpw(password, PASSWORD_HASH):
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid password.", "danger")
            return render_template('admin_login.html')
    return render_template('admin_login.html')
    

@app.route('/admin/dashboard', methods=['GET', 'POST'])
@admin_required
def admin_dashboard():
    data = []
    table_name = None

    if request.method == 'POST':
        table_name = request.form.get('table')

        if table_name == "ClassicResults":
            data = ClassicResults.query.all()
        elif table_name == "NoveltyResults":
            data = NoveltyResults.query.all()

    return render_template('admin_dashboard.html', table_name=table_name, data=data)

@app.route('/admin/edit_config', methods=['GET', 'POST'])
@admin_required
def edit_config():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin'))

    config_file = 'config.json'

    if request.method == 'POST':
        # Pobierz dane z formularza
        new_values = request.form.get('config_data')
        try:
            # Walidacja poprawnosci JSON
            parsed_json = json.loads(new_values)
            # Zapisz nowy plik config.json
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(parsed_json, f, indent=4)
            flash('Config.json was saved successfully.', 'success')
        except json.JSONDecodeError:
            flash('JSON syntax error!', 'danger')
        return redirect(url_for('edit_config'))

    # Odczytaj aktualne dane z config.json
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    # Konwertuj dane do ladnego formatu JSON
    config_data_pretty = json.dumps(config_data, indent=4, ensure_ascii=False)
    return render_template('edit_config.html', config_data=config_data_pretty)

@app.route('/export/csv/<table_name>')
@admin_required
def export_csv(table_name):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    if table_name == "ClassicResults":
        data = ClassicResults.query.all()
        columns = ["user_id", "start_time", "end_time", "risk_id", "risk_name", "impact", "probability", "priority"]
    elif table_name == "NoveltyResults":
        data = NoveltyResults.query.all()
        columns = ["user_id", "start_time", "end_time", "risk_a_id", "risk_a_description", "risk_b_id", "risk_b_description", "chosen_risk", "parameter"]
    else:
        return "Invalid table name", 400

    csv_data = pd.DataFrame([{col: getattr(row, col) for col in columns} for row in data]).to_csv(index=False)

    response = Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={table_name}-{timestamp}.csv"}
    )
    return response

@app.route('/contact')
def contact():
    return render_template('contact.html')



@app.route('/novelty_risk', methods=['GET', 'POST'])
def novelty_risk():
    global start_time, a, b, c
    print('zaczynam')
    if request.method == 'POST':
        print('odebralem')
        stop_time = datetime.now()
        choice = int(request.form['choice'])
        a = int(request.form['a'])
        b = int(request.form['b'])
        c = int(request.form['c'])
        chosen = "A" if choice == 0 else "B"
        result = NoveltyResults(
            user_id=user_id,
            start_time=start_time,
            end_time=stop_time,
            risk_a_id=a,
            risk_a_description=u.e_names[a],
            risk_b_id=b,
            risk_b_description=u.e_names[b],
            chosen_risk=chosen,
            parameter=u.p_names[c]
        )
        db.session.add(result)
        db.session.commit()
        print(f"Saving to NoveltyResults: user_id={user_id}, risk_a_id={a}, risk_b_id={b}, chosen_risk={chosen}")
        try:
            u.set_priority(choice)
        except CustomError as e:
            flash(str(e), 'danger')
            return render_template('all_done.html', values=values)
        start_time = stop_time
    try:
        a, b, c = u.next_to_process()
        if a is None or b is None or c is None:
            u.reset()
            return render_template('all_done.html', values=values)
        return render_template('novelty_risk.html', a=a, b=b, c=c, p_names=u.p_names, e_names=u.e_names)
    except CustomError as e:
        flash(str(e), 'danger')
        return render_template('all_done.html', values=values)

    
@app.route('/', methods=['GET', 'POST'])
def index():
    welcome_text = load_values_from_json(file_path,'welcome_text')
    if request.method == 'POST':
        retrieved_user_name = request.form['name']

        # Check if the user exists
        user = User.query.filter_by(name=retrieved_user_name).first()
        if not user:
            # Create a new user with a UUID
            user = User(user_id=str(uuid.uuid4()), name=retrieved_user_name)
            db.session.add(user)
            db.session.commit()

        global user_name, user_id
        user_name = user.name
        user_id = user.user_id

        return redirect(url_for('instruct'))
    return render_template('introduction.html', welcome_text=welcome_text, user_name=user_name)

    
@app.route('/instruct')
def instruct():
    instructions = load_values_from_json(file_path,'instructions')
    return render_template('instruct.html', instructions=instructions)


@app.route('/classic_risk', methods=['GET', 'POST'])
def classic_risk():
    global start_time

    if request.method == 'GET':
        # Record the time when the page is displayed
        start_time = datetime.now()

    if request.method == 'POST':
        stop_time = datetime.now()
        
        # Validate that all fields are filled
        missing_fields = False
        for risk in values:
            if not request.form.get(f'probability_{risk}') or not request.form.get(f'impact_{risk}'):
                missing_fields = True
                break
                
        if missing_fields:
            flash('Please fill in all fields for probability and impact', 'danger')
            return render_template('classic_risk.html', risks=values)
        
        # Process the form data if all fields are filled
        for risk in values:
            assessed_probability = int(request.form.get(f'probability_{risk}'))
            assessed_impact = int(request.form.get(f'impact_{risk}'))
            calculated_assessment = assessed_probability * assessed_impact

            # Save the result to the database
            result = ClassicResults(
                user_id=user_id,
                start_time=start_time,
                end_time=stop_time,
                risk_id=values.index(risk),
                risk_name=risk,
                impact=assessed_impact,
                probability=assessed_probability,
                priority=calculated_assessment
            )
            db.session.add(result)

        db.session.commit()

        return render_template('all_done.html', risks=values)

    return render_template('classic_risk.html', risks=values)




@app.route('/reset', methods=['GET'])
def reset():
    global u
    u.reset()
    return redirect(url_for('index'))




if __name__ == "__main__":
    # Load environment variables
    load_dotenv()
    
    # Print environment variables for debugging
    print("Environment variables loaded:")
    print(f"DATABASE_URI: {os.getenv('DATABASE_URI')}")
    print(f"HOST: {os.getenv('HOST')}")
    print(f"PORT: {os.getenv('PORT')}")
    
    # Create database tables if they don't exist
    with app.app_context():       
        db.create_all()  
    
    # Get host and port from environment variables with defaults
    host = os.getenv('HOST', '0.0.0.0')
    port = int(os.getenv('PORT', 5000))
    print(f"Starting server at http://{host}:{port}")
    
    # Determine if we are in development or production mode
    debug_mode = os.getenv('FLASK_ENV') == 'development'
    
    # Use appropriate server
    if debug_mode:
        # Development server with debugging
        app.run(debug=True, host=host, port=port)
    else:
        # Production server with waitress
        try:
            serve(app, host=host, port=port)
        except Exception as e:
            print(f"Error starting server: {e}")
            print("Falling back to Flask development server...")
            app.run(debug=True, host=host, port=port)
