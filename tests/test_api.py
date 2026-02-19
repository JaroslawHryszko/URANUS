"""Tests for API blueprint (tracking and session metadata)."""
import json
import uuid
from app import db
from app.models import (
    Experiment, Risk, Method, Participant,
    Session as ExpSession, MethodSession, InteractionEvent,
)


class TestTrackAPI:

    def _start_session(self, client, exp_id):
        """Helper: start an experiment session to get a cookie."""
        client.post(f'/experiment/{exp_id}/start', data={'name': 'Tracker'})
        client.post(f'/experiment/{exp_id}/demographics', data={'email': ''})

    def test_track_events(self, client, sample_experiment):
        exp_id = sample_experiment.id
        self._start_session(client, exp_id)
        resp = client.post('/api/track', json={
            'events': [
                {
                    'timestamp': 1500.0,
                    'event_type': 'click',
                    'element_id': 'btn1',
                    'element_tag': 'button',
                    'element_class': 'btn-primary',
                    'page_url': '/test',
                    'event_data': {'x': 100, 'y': 200},
                },
                {
                    'timestamp': 2000.0,
                    'event_type': 'scroll',
                    'page_url': '/test',
                    'event_data': {'scrollY': 300},
                },
            ],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'ok'
        assert data['count'] == 2
        with client.application.app_context():
            events = InteractionEvent.query.all()
            assert len(events) == 2
            click_evt = [e for e in events if e.event_type == 'click'][0]
            assert click_evt.element_id == 'btn1'

    def test_track_no_session(self, client, db):
        resp = client.post('/api/track', json={
            'events': [{'timestamp': 1000, 'event_type': 'click'}],
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'no_session'

    def test_track_no_data(self, client, sample_experiment):
        exp_id = sample_experiment.id
        self._start_session(client, exp_id)
        resp = client.post('/api/track', data='not json',
                           content_type='application/json')
        assert resp.status_code == 400

    def test_track_empty_events(self, client, sample_experiment):
        exp_id = sample_experiment.id
        self._start_session(client, exp_id)
        resp = client.post('/api/track', json={'events': []})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['count'] == 0


class TestSessionMetaAPI:

    def _start_session(self, client, exp_id):
        client.post(f'/experiment/{exp_id}/start', data={'name': 'MetaTest'})
        client.post(f'/experiment/{exp_id}/demographics', data={'email': ''})

    def test_session_meta_update(self, client, sample_experiment):
        exp_id = sample_experiment.id
        self._start_session(client, exp_id)
        resp = client.post('/api/session_meta', json={
            'screen_width': 1920,
            'screen_height': 1080,
            'language': 'pl-PL',
            'timezone': 'Europe/Warsaw',
            'is_iframe': True,
        })
        assert resp.status_code == 200
        with client.application.app_context():
            s = ExpSession.query.first()
            assert s.screen_width == 1920
            assert s.language == 'pl-PL'
            assert s.is_iframe is True

    def test_session_meta_no_session(self, client, db):
        resp = client.post('/api/session_meta', json={'screen_width': 800})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['status'] == 'no_session'

    def test_session_meta_no_data(self, client, sample_experiment):
        exp_id = sample_experiment.id
        self._start_session(client, exp_id)
        resp = client.post('/api/session_meta', data='bad',
                           content_type='application/json')
        assert resp.status_code == 400
