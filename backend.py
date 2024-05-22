from flask import Flask, request, render_template, redirect, url_for
from uranus import Uranus
from waitress import serve
from flask_sqlalchemy import SQLAlchemy
import json

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Definicja modelu danych
class PrioritizedItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(256), nullable=False)

def load_values_from_json(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data['values']

file_path = 'config.json'
values = load_values_from_json(file_path)

global u
u = Uranus(['impact', 'probability'], values)

@app.route('/novelty_risk')
def novelty_risk():
    a, b, c = u.next_to_process()
    if a is None or b is None or c is None:
        # Zapis do bazy danych
        for item in u.prioritized_list():
            new_item = PrioritizedItem(content=item)
            db.session.add(new_item)
        db.session.commit()
        return render_template('all_done.html', prioritized_list=u.prioritized_list())
    return render_template('novelty_risk.html', a=a, b=b, c=c, p_names=u.p_names, e_names=u.e_names)
    
@app.route('/')
def index():
    return render_template('instruct.html')
    
@app.route('/classic_risk')
def classic_risk():
    return render_template('instruct.html')

@app.route('/set_priority', methods=['POST'])
def set_priority():
    choice = request.form['choice']
    if choice == '1':
        u.set_priority(0)
    elif choice == '2':
        u.set_priority(1)
    return redirect(url_for('novelty_risk'))

@app.route('/reset')
def reset(): 
    u = Uranus(['impact', 'probability'], values)
    a, b, c = u.next_to_process()
    return redirect(url_for('index')) 


if __name__ == "__main__":
    db.create_all()  # Tworzy tabelę w bazie danych przy pierwszym uruchomieniu
    serve(app, host="0.0.0.0", port=8080)
