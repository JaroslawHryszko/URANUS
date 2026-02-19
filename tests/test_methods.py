"""Tests for all risk assessment method handlers."""
import json
import uuid
from datetime import datetime
from unittest.mock import patch, MagicMock
from app import db
from app.models import (
    Experiment, Risk, Method, Participant,
    Session as ExpSession, MethodSession, AssessmentResult,
)
from app.methods import get_method_handler, get_default_config, METHOD_REGISTRY, METHOD_TYPE_LABELS
from app.methods.matrix import MatrixMethod
from app.methods.ranking import RankingMethod
from app.methods.budget import BudgetMethod
from app.methods.categorization import CategorizationMethod
from app.methods.uranus_method import UranusMethod


def _create_test_env(db_session, method_type, config=None, num_risks=3):
    """Helper: create experiment + method + session + method_session."""
    exp = Experiment(name='Test', is_active=True)
    db_session.add(exp)
    db_session.flush()

    risks = []
    for i in range(num_risks):
        r = Risk(experiment_id=exp.id, name=f'Risk {chr(65+i)}', order=i)
        db_session.add(r)
        risks.append(r)
    db_session.flush()

    if config is None:
        config = get_default_config(method_type)
    m = Method(
        experiment_id=exp.id, method_type=method_type,
        display_name=f'{method_type} Test', config=json.dumps(config),
        is_active=True, order=0,
    )
    db_session.add(m)
    db_session.flush()

    p = Participant(experiment_id=exp.id, uuid=str(uuid.uuid4()), name='Tester')
    db_session.add(p)
    db_session.flush()

    s = ExpSession(participant_id=p.id, experiment_id=exp.id)
    db_session.add(s)
    db_session.flush()

    ms = MethodSession(session_id=s.id, method_id=m.id, order=0, status='in_progress',
                       started_at=datetime.utcnow())
    db_session.add(ms)
    db_session.commit()

    return exp, risks, m, ms


# ========== Registry Tests ==========

class TestMethodRegistry:

    def test_all_types_registered(self, app, db):
        for t in ['uranus', 'matrix', 'ranking', 'budget', 'categorization']:
            assert t in METHOD_REGISTRY

    def test_get_method_handler(self, app, db):
        handler = get_method_handler('matrix')
        assert isinstance(handler, MatrixMethod)

    def test_get_method_handler_invalid(self, app, db):
        import pytest
        with pytest.raises(ValueError):
            get_method_handler('nonexistent')

    def test_default_configs(self, app, db):
        for t in METHOD_REGISTRY:
            cfg = get_default_config(t)
            assert isinstance(cfg, dict)

    def test_method_type_labels(self, app, db):
        for t in METHOD_REGISTRY:
            assert t in METHOD_TYPE_LABELS


# ========== Matrix Method ==========

class TestMatrixMethod:

    def test_default_config(self, app, db):
        handler = MatrixMethod()
        cfg = handler.default_config()
        assert 'criteria' in cfg
        assert len(cfg['criteria']) == 2  # probability, impact

    def test_get_template(self, app, db):
        handler = MatrixMethod()
        assert handler.get_template() == 'methods/matrix.html'

    def test_process_response_product(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'matrix')
            handler = MatrixMethod()
            form = {}
            for r in risks:
                form[f'probability_{r.id}'] = '3'
                form[f'impact_{r.id}'] = '4'

            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            assert ms.status == 'completed'

            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) == 3
            for ar in ars:
                data = ar.get_result_data()
                assert data['priority'] == 12  # 3 * 4

    def test_process_response_weighted_sum(self, app, db):
        with app.app_context():
            config = {
                'criteria': [
                    {'name': 'prob', 'display_name': 'Prob', 'scale_min': 1, 'scale_max': 5, 'labels': {}},
                    {'name': 'imp', 'display_name': 'Imp', 'scale_min': 1, 'scale_max': 5, 'labels': {}},
                ],
                'aggregation': 'weighted_sum',
                'weights': {'prob': 2, 'imp': 3},
            }
            exp, risks, method, ms = _create_test_env(db.session, 'matrix', config=config)
            handler = MatrixMethod()
            form = {}
            for r in risks:
                form[f'prob_{r.id}'] = '3'
                form[f'imp_{r.id}'] = '4'

            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            for ar in ars:
                data = ar.get_result_data()
                assert data['priority'] == 18  # 3*2 + 4*3

    def test_process_response_missing_field(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'matrix')
            handler = MatrixMethod()
            form = {}
            # Only fill probability, not impact
            for r in risks:
                form[f'probability_{r.id}'] = '3'

            result = handler.process_response(form, ms, risks)
            assert result['complete'] is False
            assert 'error' in result

    def test_get_context(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'matrix')
            handler = MatrixMethod()
            ctx = handler.get_context(ms, risks)
            assert 'criteria' in ctx
            assert 'risks' in ctx

    def test_get_results_summary(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'matrix')
            handler = MatrixMethod()
            # First complete the method
            form = {}
            for r in risks:
                form[f'probability_{r.id}'] = '3'
                form[f'impact_{r.id}'] = '4'
            handler.process_response(form, ms, risks)

            summary = handler.get_results_summary(ms, risks)
            assert summary['type'] == 'matrix'
            assert len(summary['results']) == 3


# ========== Ranking Method ==========

class TestRankingMethod:

    def test_default_config(self, app, db):
        handler = RankingMethod()
        cfg = handler.default_config()
        assert cfg['mode'] == 'overall'

    def test_process_response_overall(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'ranking')
            handler = RankingMethod()
            risk_ids = ','.join(str(r.id) for r in risks)
            form = {'order_overall': risk_ids}
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) == 3
            ranks = sorted([ar.get_result_data()['rank'] for ar in ars])
            assert ranks == [1, 2, 3]

    def test_process_response_per_parameter(self, app, db):
        with app.app_context():
            config = {'mode': 'per_parameter', 'parameters': ['impact', 'probability']}
            exp, risks, method, ms = _create_test_env(db.session, 'ranking', config=config)
            handler = RankingMethod()
            risk_ids = ','.join(str(r.id) for r in risks)
            form = {
                'order_impact': risk_ids,
                'order_probability': risk_ids,
            }
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) == 6  # 3 risks * 2 parameters

    def test_process_response_empty_order(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'ranking')
            handler = RankingMethod()
            form = {'order_overall': ''}
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is False
            assert 'error' in result

    def test_get_context(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'ranking')
            handler = RankingMethod()
            ctx = handler.get_context(ms, risks)
            assert 'risks' in ctx
            assert ctx['mode'] == 'overall'

    def test_get_results_summary(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'ranking')
            handler = RankingMethod()
            risk_ids = ','.join(str(r.id) for r in risks)
            handler.process_response({'order_overall': risk_ids}, ms, risks)
            summary = handler.get_results_summary(ms, risks)
            assert summary['type'] == 'ranking'
            assert len(summary['results']) == 3


# ========== Budget Method ==========

class TestBudgetMethod:

    def test_default_config(self, app, db):
        handler = BudgetMethod()
        cfg = handler.default_config()
        assert cfg['total_points'] == 100

    def test_process_response_valid(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'budget')
            handler = BudgetMethod()
            # Allocate 100 points across 3 risks
            form = {}
            points = [40, 35, 25]
            for i, r in enumerate(risks):
                form[f'points_overall_{r.id}'] = str(points[i])
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) == 3
            total = sum(ar.get_result_data()['points'] for ar in ars)
            assert total == 100

    def test_process_response_wrong_sum(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'budget')
            handler = BudgetMethod()
            form = {}
            for r in risks:
                form[f'points_overall_{r.id}'] = '20'  # sum = 60, not 100
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is False
            assert 'error' in result
            assert '100' in result['error']

    def test_process_response_negative_points(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'budget')
            handler = BudgetMethod()
            form = {f'points_overall_{risks[0].id}': '-10',
                    f'points_overall_{risks[1].id}': '60',
                    f'points_overall_{risks[2].id}': '50'}
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is False
            assert 'error' in result

    def test_process_response_per_parameter(self, app, db):
        with app.app_context():
            config = {'total_points': 50, 'mode': 'per_parameter',
                      'parameters': ['impact']}
            exp, risks, method, ms = _create_test_env(db.session, 'budget', config=config)
            handler = BudgetMethod()
            form = {f'points_impact_{risks[0].id}': '20',
                    f'points_impact_{risks[1].id}': '15',
                    f'points_impact_{risks[2].id}': '15'}
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True

    def test_get_context(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'budget')
            handler = BudgetMethod()
            ctx = handler.get_context(ms, risks)
            assert ctx['total_points'] == 100

    def test_get_results_summary(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'budget')
            handler = BudgetMethod()
            form = {f'points_overall_{risks[0].id}': '50',
                    f'points_overall_{risks[1].id}': '30',
                    f'points_overall_{risks[2].id}': '20'}
            handler.process_response(form, ms, risks)
            summary = handler.get_results_summary(ms, risks)
            assert summary['type'] == 'budget'
            assert len(summary['results']) == 3
            # Should be sorted by points descending
            assert summary['results'][0]['points'] == 50


# ========== Categorization Method ==========

class TestCategorizationMethod:

    def test_default_config(self, app, db):
        handler = CategorizationMethod()
        cfg = handler.default_config()
        assert 'Critical' in cfg['categories']
        assert len(cfg['categories']) == 5

    def test_process_response_valid(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'categorization')
            handler = CategorizationMethod()
            form = {}
            cats = ['Critical', 'High', 'Low']
            for i, r in enumerate(risks):
                form[f'category_overall_{r.id}'] = cats[i]
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) == 3

    def test_process_response_invalid_category(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'categorization')
            handler = CategorizationMethod()
            form = {}
            for r in risks:
                form[f'category_overall_{r.id}'] = 'INVALID_CATEGORY'
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is False
            assert 'error' in result

    def test_process_response_missing_category(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'categorization')
            handler = CategorizationMethod()
            form = {}
            # Only fill one risk
            form[f'category_overall_{risks[0].id}'] = 'High'
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is False

    def test_process_response_per_parameter(self, app, db):
        with app.app_context():
            config = {
                'categories': ['High', 'Medium', 'Low'],
                'mode': 'per_parameter',
                'parameters': ['impact', 'probability'],
            }
            exp, risks, method, ms = _create_test_env(db.session, 'categorization', config=config)
            handler = CategorizationMethod()
            form = {}
            for param in ['impact', 'probability']:
                for r in risks:
                    form[f'category_{param}_{r.id}'] = 'High'
            result = handler.process_response(form, ms, risks)
            assert result['complete'] is True
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) == 6  # 3 risks * 2 parameters

    def test_get_context(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'categorization')
            handler = CategorizationMethod()
            ctx = handler.get_context(ms, risks)
            assert 'categories' in ctx
            assert 'Critical' in ctx['categories']

    def test_get_results_summary(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'categorization')
            handler = CategorizationMethod()
            form = {}
            for r in risks:
                form[f'category_overall_{r.id}'] = 'Medium'
            handler.process_response(form, ms, risks)
            summary = handler.get_results_summary(ms, risks)
            assert summary['type'] == 'categorization'
            assert len(summary['results']) == 3


# ========== Uranus Method ==========

class TestUranusMethod:

    def test_default_config(self, app, db):
        handler = UranusMethod()
        cfg = handler.default_config()
        assert 'parameters' in cfg
        assert 'impact' in cfg['parameters']

    def test_get_template(self, app, db):
        handler = UranusMethod()
        assert 'uranus' in handler.get_template()

    def test_create_and_serialize(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'uranus')
            handler = UranusMethod()
            u = handler._create_uranus(['impact', 'probability'],
                                       [r.name for r in risks])
            state = handler._serialize_state(u)
            assert 'p_names' in state
            assert 'prioritized' in state
            assert state['p_names'] == ['impact', 'probability']

    def test_restore_state(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'uranus')
            handler = UranusMethod()
            u = handler._create_uranus(['impact', 'probability'],
                                       [r.name for r in risks])
            state = handler._serialize_state(u)
            u2 = handler._restore_state(state, ['impact', 'probability'],
                                        [r.name for r in risks])
            assert u2.p_names == u.p_names
            assert u2.e_names == u.e_names

    def test_get_context_initial(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'uranus')
            handler = UranusMethod()
            ctx = handler.get_context(ms, risks)
            assert 'done' in ctx
            if not ctx['done']:
                assert 'a' in ctx
                assert 'b' in ctx
                assert 'c' in ctx
                assert 'progress' in ctx

    def test_process_response_single_step(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'uranus')
            handler = UranusMethod()
            # Get first comparison
            ctx = handler.get_context(ms, risks)
            if ctx.get('done'):
                return  # Edge case: less than 2 risks

            form = {
                'choice': '0',
                'a': str(ctx['a']),
                'b': str(ctx['b']),
                'c': str(ctx['c']),
            }
            result = handler.process_response(form, ms, risks)
            # Should have saved at least one comparison result
            ars = AssessmentResult.query.filter_by(method_session_id=ms.id).all()
            assert len(ars) >= 1

    def test_full_uranus_flow(self, app, db):
        """Run Uranus to completion with 3 risks."""
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'uranus')
            handler = UranusMethod()

            max_iterations = 100
            for _ in range(max_iterations):
                ctx = handler.get_context(ms, risks)
                if ctx.get('done'):
                    break
                form = {
                    'choice': '0',  # always choose A
                    'a': str(ctx['a']),
                    'b': str(ctx['b']),
                    'c': str(ctx['c']),
                }
                result = handler.process_response(form, ms, risks)
                if result.get('complete'):
                    break

            # Check final state
            assert ms.status == 'completed'
            # Should have final ranking result
            summary = handler.get_results_summary(ms, risks)
            assert summary['type'] == 'ranking'
            assert len(summary['ranking']) == 3

    def test_get_results_summary_in_progress(self, app, db):
        with app.app_context():
            exp, risks, method, ms = _create_test_env(db.session, 'uranus')
            handler = UranusMethod()
            summary = handler.get_results_summary(ms, risks)
            assert summary['type'] == 'in_progress'
