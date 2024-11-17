from flask import Flask, request, render_template, redirect, url_for, Response
from uranus import Uranus
from waitress import serve
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json, csv

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

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
    

def load_values_from_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data['values']

file_path = 'config.json'
values = load_values_from_json(file_path)

global u, user_name, start_time
u = Uranus(['impact', 'probability'], values)

user_name = 'Anon'
start_time = datetime.now()

@app.route('/novelty_risk')
def novelty_risk():
    global start_time
    start_time = datetime.now()
    a, b, c = u.next_to_process()
    if a is None or b is None or c is None:
        # ponizszy licznik wskazuje priorytety, nie id ryzyk
        counter = 1
        stop_time = datetime.now()
        for risk in u.prioritized_list():
            new_record = PrioritizedRisks(starttime = start_time, stoptime=stop_time, username=user_name, risk_number=risk, risk_name=values[risk], risk_priority=counter)
            db.session.add(new_record)
            counter += 1
        db.session.commit()
        new_prioritized_list = u.prioritized_list()
        u.reset()
        return render_template('all_done.html', prioritized_list=new_prioritized_list, values=values)
    return render_template('novelty_risk.html', a=a, b=b, c=c, p_names=u.p_names, e_names=u.e_names)
    
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # Odbieranie danych z formularza
        retrieved_user_name = request.form['name']
        if retrieved_user_name == 'zulugula':
            return redirect(url_for('data_display'))
        else:
            global user_name
            user_name = retrieved_user_name
            return redirect(url_for('instruct'))  
    return render_template('introduction.html')

@app.route('/data_display')
def data_display():
    return render_template('data_display.html')

    
@app.route('/instruct')
def instruct():
    return render_template('instruct.html')

def myAss(essment):
    return essment['assessment']

@app.route('/classic_risk', methods=['GET', 'POST'])
def classic_risk():
    global start_time
    start_time = datetime.now()
    if request.method == 'POST':
        updated_values = []
        # Adam liczy swoje ryzyka zaczynajac od zera
        counter = 0
        stop_time = datetime.now()
        for risk in values:
            assessed_probability = request.form.get(f'probability_{risk}', 0)
            assessed_impact = request.form.get(f'impact_{risk}', 0)
            assessed_probability_int = int(assessed_probability)
            assessed_impact_int = int(assessed_impact)
            calculated_assessment = assessed_probability_int * assessed_impact_int
            updated_values.append({'risk': counter, 'assessment': calculated_assessment})
            new_record = ClassicRisks(starttime = start_time, stoptime=stop_time, username=user_name, risk_number=counter, risk_name=risk, impact=assessed_impact_int, probability=assessed_probability_int, risk_priority = calculated_assessment)
            db.session.add(new_record)
            counter += 1
        db.session.commit()
        updated_values.sort(key=myAss, reverse=True)
        new_prioritized_list = []
        for updated_value in updated_values:
            new_prioritized_list.append(updated_value['risk'])
        global u
        u.reset()
        return render_template('all_done.html', prioritized_list=new_prioritized_list, values=values)
    return render_template('classic_risk.html', risks=values)



@app.route('/set_priority', methods=['POST'])
def set_priority():
    choice = request.form['choice']
    if choice == '0':
        u.set_priority(0)
    elif choice == '1':
        u.set_priority(1)
    return redirect(url_for('novelty_risk'))

@app.route('/reset', methods=['GET'])
def reset():
    global u
    u.reset()
    return redirect(url_for('index'))

@app.route('/display_data')
def display_data():
    # Pobieranie wszystkich rekordów z bazy danych
    items = PrioritizedRisks.query.all()
    # Przekazywanie rekordów do szablonu HTML
    return render_template('display_data.html', items=items)
    
@app.route('/display_classic_data')
def display_classic_data():
    # Pobieranie wszystkich rekordów z bazy danych
    items = ClassicRisks.query.all()
    # Przekazywanie rekordów do szablonu HTML
    return render_template('display_classic_data.html', items=items)
    
@app.route('/export/csv')
def export_csv():
    # Pobranie danych
    items = PrioritizedItem.query.all()
    # Utworzenie pliku CSV
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Content', 'Start Time', 'End Time'])  # Nagłówki kolumn
    for item in items:
        cw.writerow([item.id, item.content, item.start_time, item.end_time])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=export.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Tworzy tabelę w bazie danych przy pierwszym uruchomieniu
        serve(app, host="0.0.0.0", port=80)
