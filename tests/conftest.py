"""Pytest configuration and fixtures for Neptune v3.0 test suite."""
import pytest
import json
import uuid
from datetime import datetime, timedelta

from app import create_app, db as _db
from app.models import (
    Experiment, Risk, Method, Participant,
    Session as ExpSession, MethodSession, AssessmentResult, InteractionEvent,
)


class TestConfig:
    """Test configuration — in-memory SQLite, secure cookies off."""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key-neptune'
    ADMIN_PASSWORD = 'testpass123'
    SESSION_COOKIE_SAMESITE = 'Lax'
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = False
    SERVER_NAME = 'localhost'


@pytest.fixture(scope='session')
def app():
    """Create application for the test session."""
    _app = create_app(config_class=TestConfig)
    yield _app


@pytest.fixture(scope='function')
def db(app):
    """Create fresh database tables for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app, db):
    """Flask test client."""
    return app.test_client()


@pytest.fixture
def admin_session(client):
    """Helper: log in as admin, return client."""
    client.post('/admin/login', data={'password': 'testpass123'})
    return client


@pytest.fixture
def sample_experiment(db):
    """Create a sample experiment with risks and methods."""
    exp = Experiment(
        name='Test Experiment',
        description='A test experiment',
        welcome_text='<p>Welcome!</p>',
        instructions='<p>Instructions here</p>',
        is_active=True,
        demographics_enabled=True,
        method_assignment_mode='fixed',
    )
    db.session.add(exp)
    db.session.flush()

    # Add risks
    risks = []
    for i, name in enumerate(['Risk A', 'Risk B', 'Risk C']):
        r = Risk(experiment_id=exp.id, name=name, description=f'Desc {name}', order=i)
        db.session.add(r)
        risks.append(r)
    db.session.flush()

    # Add methods
    methods = []
    for mtype, dname in [('matrix', 'Matrix Method'), ('ranking', 'Ranking Method')]:
        from app.methods import get_default_config
        m = Method(
            experiment_id=exp.id,
            method_type=mtype,
            display_name=dname,
            config=json.dumps(get_default_config(mtype)),
            order=len(methods),
            is_active=True,
        )
        db.session.add(m)
        methods.append(m)
    db.session.flush()

    db.session.commit()
    return exp


@pytest.fixture
def sample_session(db, sample_experiment):
    """Create a participant and session for the sample experiment."""
    exp = sample_experiment
    p = Participant(
        experiment_id=exp.id,
        uuid=str(uuid.uuid4()),
        name='Test User',
        email='test@example.com',
    )
    db.session.add(p)
    db.session.flush()

    s = ExpSession(
        participant_id=p.id,
        experiment_id=exp.id,
        user_agent='TestAgent/1.0',
        ip_address='127.0.0.1',
    )
    db.session.add(s)
    db.session.flush()

    # Create method sessions
    methods = Method.query.filter_by(experiment_id=exp.id).order_by(Method.order).all()
    for i, m in enumerate(methods):
        ms = MethodSession(
            session_id=s.id,
            method_id=m.id,
            order=i,
            status='pending',
        )
        db.session.add(ms)

    db.session.commit()
    return s
