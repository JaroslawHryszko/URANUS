"""Tests for experiment (participant flow) blueprint."""
import json
import uuid
from app import db
from app.models import (
    Experiment, Risk, Method, Participant,
    Session as ExpSession, MethodSession,
)
from app.methods import get_default_config


class TestIndex:

    def test_index_redirects_single_experiment(self, client, sample_experiment):
        resp = client.get('/')
        assert resp.status_code == 302
        assert f'/experiment/{sample_experiment.id}' in resp.headers['Location']

    def test_index_lists_multiple_experiments(self, client, db):
        with client.application.app_context():
            for i in range(3):
                exp = Experiment(name=f'Exp {i}', is_active=True)
                db.session.add(exp)
            db.session.commit()
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'Exp 0' in resp.data


class TestWelcome:

    def test_welcome_page(self, client, sample_experiment):
        resp = client.get(f'/experiment/{sample_experiment.id}')
        assert resp.status_code == 200
        assert b'Welcome' in resp.data or b'welcome' in resp.data.lower()

    def test_welcome_inactive_experiment(self, client, db):
        with client.application.app_context():
            exp = Experiment(name='Inactive', is_active=False)
            db.session.add(exp)
            db.session.commit()
            exp_id = exp.id
        resp = client.get(f'/experiment/{exp_id}')
        assert resp.status_code == 404

    def test_welcome_nonexistent_experiment(self, client, db):
        resp = client.get('/experiment/9999')
        assert resp.status_code == 404


class TestStartExperiment:

    def test_start_creates_participant_and_session(self, client, sample_experiment):
        exp_id = sample_experiment.id
        resp = client.post(f'/experiment/{exp_id}/start',
                           data={'name': 'Alice'}, follow_redirects=False)
        assert resp.status_code == 302
        with client.application.app_context():
            p = Participant.query.filter_by(name='Alice', experiment_id=exp_id).first()
            assert p is not None
            s = ExpSession.query.filter_by(participant_id=p.id).first()
            assert s is not None
            # Method sessions should be created
            ms_count = MethodSession.query.filter_by(session_id=s.id).count()
            assert ms_count == 2  # matrix + ranking

    def test_start_without_name_flashes_error(self, client, sample_experiment):
        resp = client.post(f'/experiment/{sample_experiment.id}/start',
                           data={'name': ''}, follow_redirects=True)
        assert resp.status_code == 200
        assert b'Please enter your name' in resp.data

    def test_start_same_name_reuses_participant(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Bob'})
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Bob'})
        with client.application.app_context():
            count = Participant.query.filter_by(name='Bob', experiment_id=exp_id).count()
            assert count == 1

    def test_start_redirects_to_demographics(self, client, sample_experiment):
        exp_id = sample_experiment.id
        resp = client.post(f'/experiment/{exp_id}/start',
                           data={'name': 'Demo'}, follow_redirects=False)
        assert resp.status_code == 302
        assert 'demographics' in resp.headers['Location']


class TestDemographics:

    def test_demographics_form_renders(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Charlie'})
        resp = client.get(f'/experiment/{exp_id}/demographics')
        assert resp.status_code == 200

    def test_demographics_submit(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Charlie'})
        resp = client.post(f'/experiment/{exp_id}/demographics', data={
            'email': 'charlie@test.com',
            'experience': '3-5',
        }, follow_redirects=False)
        assert resp.status_code == 302

    def test_demographics_without_session_redirects(self, client, sample_experiment):
        resp = client.get(f'/experiment/{sample_experiment.id}/demographics')
        assert resp.status_code == 302
        assert 'welcome' in resp.headers['Location'] or f'experiment/{sample_experiment.id}' in resp.headers['Location']


class TestInstructions:

    def test_instructions_renders(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Donna'})
        client.post(f'/experiment/{exp_id}/demographics', data={'email': ''})
        resp = client.get(f'/experiment/{exp_id}/instructions')
        assert resp.status_code == 200

    def test_instructions_without_session(self, client, sample_experiment):
        resp = client.get(f'/experiment/{sample_experiment.id}/instructions')
        assert resp.status_code == 302


class TestMethodFlow:

    def test_run_method_starts_first_method(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Eve'})
        client.post(f'/experiment/{exp_id}/demographics', data={'email': ''})
        resp = client.get(f'/experiment/{exp_id}/run', follow_redirects=False)
        assert resp.status_code == 302
        assert 'method' in resp.headers['Location']

    def test_method_page_renders(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Frank'})
        client.post(f'/experiment/{exp_id}/demographics', data={'email': ''})
        # Follow redirect chain to method page
        resp = client.get(f'/experiment/{exp_id}/run', follow_redirects=True)
        assert resp.status_code == 200

    def test_between_methods_page(self, client, sample_experiment):
        exp_id = sample_experiment.id
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Grace'})
        client.post(f'/experiment/{exp_id}/demographics', data={'email': ''})
        resp = client.get(f'/experiment/{exp_id}/between')
        assert resp.status_code == 200

    def test_complete_page(self, client, sample_experiment):
        exp_id = sample_experiment.id
        resp = client.get(f'/experiment/{exp_id}/complete')
        assert resp.status_code == 200


class TestMethodChoice:

    def test_method_choice_renders(self, client, db):
        """For participant_choice mode, method selection page should render."""
        with client.application.app_context():
            exp = Experiment(
                name='Choice Exp', is_active=True,
                demographics_enabled=False,
                method_assignment_mode='participant_choice',
            )
            db.session.add(exp)
            db.session.flush()
            Risk(experiment_id=exp.id, name='R1', order=0)
            m = Method(experiment_id=exp.id, method_type='matrix',
                       display_name='M', config=json.dumps(get_default_config('matrix')),
                       is_active=True, order=0)
            db.session.add(m)
            db.session.commit()
            exp_id = exp.id

        client.post(f'/experiment/{exp_id}/start', data={'name': 'Harry'})
        resp = client.get(f'/experiment/{exp_id}/method_choice')
        assert resp.status_code == 200
