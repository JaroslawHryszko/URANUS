from datetime import datetime
from app import db
import json


class Experiment(db.Model):
    __tablename__ = 'experiment'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, default='')
    welcome_text = db.Column(db.Text, default='')
    instructions = db.Column(db.Text, default='')
    is_template = db.Column(db.Boolean, default=False)
    cloned_from_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=True)
    method_assignment_mode = db.Column(db.String(50), default='fixed')  # fixed, random, participant_choice
    method_order = db.Column(db.Text, default='[]')  # JSON list of method IDs
    methods_per_participant = db.Column(db.Integer, default=0)  # 0 = all
    demographics_enabled = db.Column(db.Boolean, default=True)
    demographics_fields = db.Column(db.Text, default='[]')  # JSON
    custom_css = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    risks = db.relationship('Risk', backref='experiment', lazy=True, cascade='all, delete-orphan',
                            order_by='Risk.order')
    methods = db.relationship('Method', backref='experiment', lazy=True, cascade='all, delete-orphan',
                              order_by='Method.order')
    participants = db.relationship('Participant', backref='experiment', lazy=True, cascade='all, delete-orphan')
    sessions = db.relationship('Session', backref='experiment', lazy=True, cascade='all, delete-orphan')

    def get_method_order(self):
        try:
            return json.loads(self.method_order or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def set_method_order(self, order_list):
        self.method_order = json.dumps(order_list)

    def get_demographics_fields(self):
        try:
            return json.loads(self.demographics_fields or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def set_demographics_fields(self, fields):
        self.demographics_fields = json.dumps(fields)

    def get_active_methods(self):
        return [m for m in self.methods if m.is_active]


class Risk(db.Model):
    __tablename__ = 'risk'

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    name = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default='')
    order = db.Column(db.Integer, default=0)


class Method(db.Model):
    __tablename__ = 'method'

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    method_type = db.Column(db.String(50), nullable=False)  # uranus, matrix, ranking, budget, categorization
    display_name = db.Column(db.String(255), nullable=False)
    instructions = db.Column(db.Text, default='')
    config = db.Column(db.Text, default='{}')  # JSON
    order = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    method_sessions = db.relationship('MethodSession', backref='method', lazy=True, cascade='all, delete-orphan')

    def get_config(self):
        try:
            return json.loads(self.config or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_config(self, config_dict):
        self.config = json.dumps(config_dict)


class Participant(db.Model):
    __tablename__ = 'participant'

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    uuid = db.Column(db.String(36), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), nullable=True)
    demographics = db.Column(db.Text, default='{}')  # JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    sessions = db.relationship('Session', backref='participant', lazy=True, cascade='all, delete-orphan')

    def get_demographics(self):
        try:
            return json.loads(self.demographics or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_demographics(self, data):
        self.demographics = json.dumps(data)


class Session(db.Model):
    __tablename__ = 'session'

    id = db.Column(db.Integer, primary_key=True)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)
    experiment_id = db.Column(db.Integer, db.ForeignKey('experiment.id'), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime, nullable=True)
    user_agent = db.Column(db.Text, default='')
    screen_width = db.Column(db.Integer, nullable=True)
    screen_height = db.Column(db.Integer, nullable=True)
    language = db.Column(db.String(20), default='')
    timezone = db.Column(db.String(100), default='')
    ip_address = db.Column(db.String(45), default='')
    referrer = db.Column(db.Text, default='')
    is_iframe = db.Column(db.Boolean, default=False)

    method_sessions = db.relationship('MethodSession', backref='session', lazy=True, cascade='all, delete-orphan',
                                      order_by='MethodSession.order')
    interaction_events = db.relationship('InteractionEvent', backref='session', lazy=True,
                                         cascade='all, delete-orphan')


class MethodSession(db.Model):
    __tablename__ = 'method_session'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    method_id = db.Column(db.Integer, db.ForeignKey('method.id'), nullable=False)
    order = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, in_progress, completed, abandoned
    uranus_state = db.Column(db.Text, nullable=True)  # JSON serialized Uranus state

    results = db.relationship('AssessmentResult', backref='method_session', lazy=True, cascade='all, delete-orphan')

    def get_uranus_state(self):
        try:
            return json.loads(self.uranus_state) if self.uranus_state else None
        except (json.JSONDecodeError, TypeError):
            return None

    def set_uranus_state(self, state_dict):
        self.uranus_state = json.dumps(state_dict)


class AssessmentResult(db.Model):
    __tablename__ = 'assessment_result'

    id = db.Column(db.Integer, primary_key=True)
    method_session_id = db.Column(db.Integer, db.ForeignKey('method_session.id'), nullable=False)
    risk_id = db.Column(db.Integer, db.ForeignKey('risk.id'), nullable=True)
    result_data = db.Column(db.Text, default='{}')  # JSON

    def get_result_data(self):
        try:
            return json.loads(self.result_data or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_result_data(self, data):
        self.result_data = json.dumps(data)


class InteractionEvent(db.Model):
    __tablename__ = 'interaction_event'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('session.id'), nullable=False)
    method_session_id = db.Column(db.Integer, db.ForeignKey('method_session.id'), nullable=True)
    timestamp = db.Column(db.Float, nullable=False)  # ms precision from performance.now()
    event_type = db.Column(db.String(50), nullable=False)
    element_id = db.Column(db.String(255), default='')
    element_tag = db.Column(db.String(50), default='')
    element_class = db.Column(db.String(500), default='')
    page_url = db.Column(db.Text, default='')
    event_data = db.Column(db.Text, default='{}')  # JSON

    def get_event_data(self):
        try:
            return json.loads(self.event_data or '{}')
        except (json.JSONDecodeError, TypeError):
            return {}

    def set_event_data(self, data):
        self.event_data = json.dumps(data)
