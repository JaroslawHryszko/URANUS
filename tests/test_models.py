"""Tests for SQLAlchemy models."""
import json
import uuid
from datetime import datetime, timedelta
from app import db
from app.models import (
    Experiment, Risk, Method, Participant,
    Session as ExpSession, MethodSession, AssessmentResult, InteractionEvent,
)


class TestExperimentModel:

    def test_create_experiment(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test', description='desc')
            db.session.add(exp)
            db.session.commit()
            assert exp.id is not None
            assert exp.name == 'Test'
            assert exp.is_active is True  # default
            assert exp.is_template is False

    def test_method_order_json(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            exp.set_method_order([3, 1, 2])
            db.session.commit()
            assert exp.get_method_order() == [3, 1, 2]

    def test_method_order_invalid_json(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test', method_order='not-json')
            db.session.add(exp)
            db.session.commit()
            assert exp.get_method_order() == []

    def test_demographics_fields_json(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            fields = [{'name': 'age', 'type': 'number'}]
            exp.set_demographics_fields(fields)
            db.session.commit()
            assert exp.get_demographics_fields() == fields

    def test_get_active_methods(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            m1 = Method(experiment_id=exp.id, method_type='matrix', display_name='Active',
                        is_active=True, config='{}')
            m2 = Method(experiment_id=exp.id, method_type='ranking', display_name='Inactive',
                        is_active=False, config='{}')
            db.session.add_all([m1, m2])
            db.session.commit()
            active = exp.get_active_methods()
            assert len(active) == 1
            assert active[0].display_name == 'Active'

    def test_experiment_cascade_delete(self, app, db):
        with app.app_context():
            exp = Experiment(name='Cascade Test')
            db.session.add(exp)
            db.session.flush()
            risk = Risk(experiment_id=exp.id, name='R1')
            method = Method(experiment_id=exp.id, method_type='matrix', display_name='M', config='{}')
            db.session.add_all([risk, method])
            db.session.commit()
            db.session.delete(exp)
            db.session.commit()
            assert Risk.query.count() == 0
            assert Method.query.count() == 0


class TestRiskModel:

    def test_create_risk(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            risk = Risk(experiment_id=exp.id, name='Risk X', description='Risky!', order=0)
            db.session.add(risk)
            db.session.commit()
            assert risk.id is not None
            assert risk.name == 'Risk X'


class TestMethodModel:

    def test_get_set_config(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            m = Method(experiment_id=exp.id, method_type='budget', display_name='Budget', config='{}')
            db.session.add(m)
            db.session.flush()
            cfg = {'total_points': 200, 'mode': 'overall'}
            m.set_config(cfg)
            db.session.commit()
            assert m.get_config() == cfg

    def test_config_invalid_json(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            m = Method(experiment_id=exp.id, method_type='matrix', display_name='M', config='broken')
            db.session.add(m)
            db.session.commit()
            assert m.get_config() == {}


class TestParticipantModel:

    def test_demographics(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Jan')
            db.session.add(p)
            db.session.flush()
            p.set_demographics({'age': 30, 'experience': '5-10'})
            db.session.commit()
            assert p.get_demographics() == {'age': 30, 'experience': '5-10'}


class TestSessionModel:

    def test_session_relationships(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Jan')
            db.session.add(p)
            db.session.flush()
            s = ExpSession(participant_id=p.id, experiment_id=exp.id)
            db.session.add(s)
            db.session.commit()
            assert s.started_at is not None
            assert s.completed_at is None


class TestMethodSessionModel:

    def test_uranus_state(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            m = Method(experiment_id=exp.id, method_type='uranus', display_name='U', config='{}')
            db.session.add(m)
            db.session.flush()
            p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Jan')
            db.session.add(p)
            db.session.flush()
            s = ExpSession(participant_id=p.id, experiment_id=exp.id)
            db.session.add(s)
            db.session.flush()
            ms = MethodSession(session_id=s.id, method_id=m.id, order=0)
            db.session.add(ms)
            db.session.flush()
            state = {'prioritized': [[0, 1], []], 'next_elem': 2}
            ms.set_uranus_state(state)
            db.session.commit()
            recovered = ms.get_uranus_state()
            assert recovered['prioritized'] == [[0, 1], []]
            assert recovered['next_elem'] == 2

    def test_uranus_state_none(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            m = Method(experiment_id=exp.id, method_type='uranus', display_name='U', config='{}')
            db.session.add(m)
            db.session.flush()
            p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Jan')
            db.session.add(p)
            db.session.flush()
            s = ExpSession(participant_id=p.id, experiment_id=exp.id)
            db.session.add(s)
            db.session.flush()
            ms = MethodSession(session_id=s.id, method_id=m.id, order=0)
            db.session.add(ms)
            db.session.commit()
            assert ms.get_uranus_state() is None


class TestAssessmentResultModel:

    def test_result_data_json(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            m = Method(experiment_id=exp.id, method_type='matrix', display_name='M', config='{}')
            db.session.add(m)
            db.session.flush()
            p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Jan')
            db.session.add(p)
            db.session.flush()
            s = ExpSession(participant_id=p.id, experiment_id=exp.id)
            db.session.add(s)
            db.session.flush()
            ms = MethodSession(session_id=s.id, method_id=m.id, order=0)
            db.session.add(ms)
            db.session.flush()
            r = Risk(experiment_id=exp.id, name='R1')
            db.session.add(r)
            db.session.flush()
            ar = AssessmentResult(method_session_id=ms.id, risk_id=r.id)
            ar.set_result_data({'priority': 12, 'criteria': {'impact': 3, 'probability': 4}})
            db.session.add(ar)
            db.session.commit()
            assert ar.get_result_data()['priority'] == 12


class TestInteractionEventModel:

    def test_event_data_json(self, app, db):
        with app.app_context():
            exp = Experiment(name='Test')
            db.session.add(exp)
            db.session.flush()
            p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Jan')
            db.session.add(p)
            db.session.flush()
            s = ExpSession(participant_id=p.id, experiment_id=exp.id)
            db.session.add(s)
            db.session.flush()
            evt = InteractionEvent(
                session_id=s.id, timestamp=1500.5, event_type='click',
                element_id='btn1', element_tag='button', page_url='/test',
            )
            evt.set_event_data({'x': 100, 'y': 200})
            db.session.add(evt)
            db.session.commit()
            assert evt.get_event_data() == {'x': 100, 'y': 200}
