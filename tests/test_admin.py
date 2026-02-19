"""Tests for admin blueprint routes."""
import json
from app import db
from app.models import (
    Experiment, Risk, Method, Participant,
    Session as ExpSession, MethodSession, AssessmentResult, InteractionEvent,
)
from app.methods import get_default_config


class TestAdminLogin:

    def test_login_page_renders(self, client):
        resp = client.get('/admin/login')
        assert resp.status_code == 200
        assert b'password' in resp.data.lower()

    def test_login_success(self, client):
        resp = client.post('/admin/login', data={'password': 'testpass123'},
                           follow_redirects=True)
        assert resp.status_code == 200

    def test_login_failure(self, client):
        resp = client.post('/admin/login', data={'password': 'wrong'},
                           follow_redirects=True)
        assert b'Invalid password' in resp.data

    def test_admin_required_redirect(self, client):
        resp = client.get('/admin/')
        assert resp.status_code == 302
        assert '/admin/login' in resp.headers['Location']

    def test_logout(self, admin_session):
        resp = admin_session.get('/admin/logout', follow_redirects=True)
        assert resp.status_code == 200
        # After logout, dashboard should redirect to login
        resp2 = admin_session.get('/admin/')
        assert resp2.status_code == 302


class TestAdminDashboard:

    def test_dashboard_renders(self, admin_session, sample_experiment):
        resp = admin_session.get('/admin/')
        assert resp.status_code == 200
        assert b'Test Experiment' in resp.data

    def test_dashboard_shows_stats(self, admin_session, sample_session):
        resp = admin_session.get('/admin/')
        assert resp.status_code == 200
        # Should show experiment stats (participants, sessions)
        assert b'Test Experiment' in resp.data


class TestExperimentCRUD:

    def test_create_experiment(self, admin_session, db):
        resp = admin_session.post('/admin/experiment/new', data={
            'name': 'New Exp',
            'description': 'New desc',
            'welcome_text': '<p>Hello</p>',
            'instructions': '<p>Do this</p>',
            'method_assignment_mode': 'fixed',
            'methods_per_participant': '0',
            'demographics_enabled': 'on',
            'is_active': 'on',
        }, follow_redirects=True)
        assert resp.status_code == 200
        exp = Experiment.query.filter_by(name='New Exp').first()
        assert exp is not None
        assert exp.description == 'New desc'
        assert exp.is_active is True

    def test_edit_experiment(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/edit', data={
            'name': 'Updated Name',
            'description': 'Updated desc',
            'welcome_text': '',
            'instructions': '',
            'method_assignment_mode': 'random',
            'methods_per_participant': '2',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            exp = Experiment.query.get(exp_id)
            assert exp.name == 'Updated Name'
            assert exp.method_assignment_mode == 'random'

    def test_delete_experiment(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/delete',
                                  follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            assert Experiment.query.get(exp_id) is None

    def test_clone_experiment(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/clone',
                                  follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            clones = Experiment.query.filter(Experiment.cloned_from_id == exp_id).all()
            assert len(clones) == 1
            clone = clones[0]
            assert clone.name == 'Test Experiment (copy)'
            assert clone.is_active is False
            # Check risks and methods were cloned
            assert Risk.query.filter_by(experiment_id=clone.id).count() == 3
            assert Method.query.filter_by(experiment_id=clone.id).count() == 2

    def test_toggle_experiment(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        # Experiment starts active
        resp = admin_session.post(f'/admin/experiment/{exp_id}/toggle',
                                  follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            exp = Experiment.query.get(exp_id)
            assert exp.is_active is False

    def test_experiment_form_get(self, admin_session, sample_experiment):
        resp = admin_session.get(f'/admin/experiment/{sample_experiment.id}/edit')
        assert resp.status_code == 200
        assert b'Test Experiment' in resp.data

    def test_new_experiment_form_get(self, admin_session, db):
        resp = admin_session.get('/admin/experiment/new')
        assert resp.status_code == 200


class TestRiskManagement:

    def test_add_risk(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/risks', data={
            'action': 'add',
            'risk_name': 'New Risk',
            'risk_description': 'A new risk',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            risk = Risk.query.filter_by(experiment_id=exp_id, name='New Risk').first()
            assert risk is not None

    def test_delete_risk(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        with admin_session.application.app_context():
            risk = Risk.query.filter_by(experiment_id=exp_id).first()
            risk_id = risk.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/risks', data={
            'action': 'delete',
            'risk_id': str(risk_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            assert Risk.query.get(risk_id) is None

    def test_edit_risk(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        with admin_session.application.app_context():
            risk = Risk.query.filter_by(experiment_id=exp_id).first()
            risk_id = risk.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/risks', data={
            'action': 'edit',
            'risk_id': str(risk_id),
            'risk_name': 'Renamed Risk',
            'risk_description': 'Updated desc',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            risk = Risk.query.get(risk_id)
            assert risk.name == 'Renamed Risk'

    def test_bulk_add_risks(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/risks', data={
            'action': 'bulk_add',
            'risks_bulk': 'Risk X\nRisk Y\nRisk Z',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            assert Risk.query.filter_by(experiment_id=exp_id, name='Risk X').first() is not None
            assert Risk.query.filter_by(experiment_id=exp_id, name='Risk Z').first() is not None

    def test_reorder_risks(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        with admin_session.application.app_context():
            risks = Risk.query.filter_by(experiment_id=exp_id).order_by(Risk.order).all()
            ids = [str(r.id) for r in risks]
        # Reverse order
        resp = admin_session.post(f'/admin/experiment/{exp_id}/risks', data={
            'action': 'reorder',
            'risk_order': ','.join(reversed(ids)),
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_risks_page_renders(self, admin_session, sample_experiment):
        resp = admin_session.get(f'/admin/experiment/{sample_experiment.id}/risks')
        assert resp.status_code == 200
        assert b'Risk A' in resp.data


class TestMethodManagement:

    def test_add_method(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/methods', data={
            'action': 'add',
            'method_type': 'budget',
            'display_name': 'Budget Test',
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            m = Method.query.filter_by(experiment_id=exp_id, display_name='Budget Test').first()
            assert m is not None
            assert m.method_type == 'budget'

    def test_delete_method(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        with admin_session.application.app_context():
            method = Method.query.filter_by(experiment_id=exp_id).first()
            method_id = method.id
        resp = admin_session.post(f'/admin/experiment/{exp_id}/methods', data={
            'action': 'delete',
            'method_id': str(method_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            assert Method.query.get(method_id) is None

    def test_toggle_method(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        with admin_session.application.app_context():
            method = Method.query.filter_by(experiment_id=exp_id).first()
            method_id = method.id
            was_active = method.is_active
        resp = admin_session.post(f'/admin/experiment/{exp_id}/methods', data={
            'action': 'toggle',
            'method_id': str(method_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            method = Method.query.get(method_id)
            assert method.is_active != was_active

    def test_update_method_config(self, admin_session, sample_experiment):
        exp_id = sample_experiment.id
        with admin_session.application.app_context():
            method = Method.query.filter_by(experiment_id=exp_id).first()
            method_id = method.id
        new_config = json.dumps({'criteria': [{'name': 'custom', 'scale_min': 1, 'scale_max': 10}]})
        resp = admin_session.post(f'/admin/experiment/{exp_id}/methods', data={
            'action': 'update_config',
            'method_id': str(method_id),
            'display_name': 'Updated Matrix',
            'method_instructions': 'New instructions',
            'config_json': new_config,
        }, follow_redirects=True)
        assert resp.status_code == 200
        with admin_session.application.app_context():
            method = Method.query.get(method_id)
            assert method.display_name == 'Updated Matrix'
            cfg = method.get_config()
            assert cfg['criteria'][0]['name'] == 'custom'

    def test_methods_page_renders(self, admin_session, sample_experiment):
        resp = admin_session.get(f'/admin/experiment/{sample_experiment.id}/methods')
        assert resp.status_code == 200


class TestParticipantsPage:

    def test_participants_empty(self, admin_session, sample_experiment):
        resp = admin_session.get(f'/admin/experiment/{sample_experiment.id}/participants')
        assert resp.status_code == 200
        assert b'No participants yet' in resp.data

    def test_participants_with_data(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        resp = admin_session.get(f'/admin/experiment/{exp_id}/participants')
        assert resp.status_code == 200
        assert b'Test User' in resp.data


class TestResultsPage:

    def test_results_empty(self, admin_session, sample_experiment):
        resp = admin_session.get(f'/admin/experiment/{sample_experiment.id}/results')
        assert resp.status_code == 200

    def test_results_export_csv_empty(self, admin_session, sample_experiment):
        resp = admin_session.get(
            f'/admin/experiment/{sample_experiment.id}/results/export/csv')
        assert resp.status_code == 200
        assert b'No data' in resp.data

    def test_results_export_json(self, admin_session, sample_experiment):
        resp = admin_session.get(
            f'/admin/experiment/{sample_experiment.id}/results/export/json')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert isinstance(data, list)

    def test_results_export_invalid_format(self, admin_session, sample_experiment):
        resp = admin_session.get(
            f'/admin/experiment/{sample_experiment.id}/results/export/xml')
        assert resp.status_code == 400


class TestInteractionLogs:

    def test_interaction_logs_empty(self, admin_session, sample_experiment):
        resp = admin_session.get(
            f'/admin/experiment/{sample_experiment.id}/interactions')
        assert resp.status_code == 200
        assert b'No interaction events' in resp.data

    def test_interaction_logs_with_events(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        with admin_session.application.app_context():
            evt = InteractionEvent(
                session_id=sample_session.id, timestamp=1000.0,
                event_type='click', element_id='btn', element_tag='button',
                page_url='/test',
            )
            db.session.add(evt)
            db.session.commit()
        resp = admin_session.get(f'/admin/experiment/{exp_id}/interactions')
        assert resp.status_code == 200
        assert b'click' in resp.data

    def test_interaction_logs_filter_by_event_type(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        with admin_session.application.app_context():
            for et in ['click', 'scroll', 'click']:
                evt = InteractionEvent(
                    session_id=sample_session.id, timestamp=1000.0,
                    event_type=et, page_url='/test',
                )
                db.session.add(evt)
            db.session.commit()
        resp = admin_session.get(
            f'/admin/experiment/{exp_id}/interactions?event_type=scroll')
        assert resp.status_code == 200

    def test_interactions_export_csv(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        with admin_session.application.app_context():
            evt = InteractionEvent(
                session_id=sample_session.id, timestamp=1000.0,
                event_type='click', page_url='/test',
            )
            db.session.add(evt)
            db.session.commit()
        resp = admin_session.get(
            f'/admin/experiment/{exp_id}/interactions/export/csv')
        assert resp.status_code == 200
        assert b'event_type' in resp.data  # CSV header

    def test_interactions_export_json(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        resp = admin_session.get(
            f'/admin/experiment/{exp_id}/interactions/export/json')
        assert resp.status_code == 200


class TestAnalytics:

    def test_analytics_page_renders(self, admin_session, sample_experiment):
        resp = admin_session.get(
            f'/admin/experiment/{sample_experiment.id}/analytics')
        assert resp.status_code == 200
        assert b'Analytics' in resp.data

    def test_analytics_with_session_data(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        resp = admin_session.get(f'/admin/experiment/{exp_id}/analytics')
        assert resp.status_code == 200
        assert b'Test User' in resp.data


class TestSessionDetail:

    def test_session_detail_renders(self, admin_session, sample_session):
        exp_id = sample_session.experiment_id
        sess_id = sample_session.id
        resp = admin_session.get(
            f'/admin/experiment/{exp_id}/session/{sess_id}')
        assert resp.status_code == 200
        assert b'Session' in resp.data
        assert b'Test User' in resp.data

    def test_session_detail_wrong_experiment(self, admin_session, sample_session, db):
        """Session from experiment X accessed via experiment Y should 404."""
        with admin_session.application.app_context():
            exp2 = Experiment(name='Other')
            db.session.add(exp2)
            db.session.commit()
            resp = admin_session.get(
                f'/admin/experiment/{exp2.id}/session/{sample_session.id}')
            assert resp.status_code == 404


class TestDocs:

    def test_docs_page_renders(self, admin_session, db):
        resp = admin_session.get('/admin/docs')
        assert resp.status_code == 200
