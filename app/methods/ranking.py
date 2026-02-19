from datetime import datetime
from app.methods.base import BaseMethod


class RankingMethod(BaseMethod):
    """Direct ranking via drag & drop."""

    def default_config(self):
        return {
            'mode': 'overall',  # overall or per_parameter
            'parameters': [],  # only used if mode=per_parameter
        }

    def get_template(self):
        return 'methods/ranking.html'

    def process_response(self, form_data, method_session, risks):
        from app.models import AssessmentResult
        from app import db

        config = method_session.method.get_config()
        mode = config.get('mode', 'overall')
        parameters = config.get('parameters', [])

        if mode == 'per_parameter' and parameters:
            params_to_process = parameters
        else:
            params_to_process = ['overall']

        for param in params_to_process:
            order_key = f'order_{param}'
            order_str = form_data.get(order_key, '')
            if not order_str:
                return {
                    'complete': False,
                    'error': 'Please rank all risks before submitting.',
                    'context': self.get_context(method_session, risks),
                }

            risk_ids = [int(x) for x in order_str.split(',') if x.strip()]
            for rank, risk_id in enumerate(risk_ids, 1):
                result = AssessmentResult(
                    method_session_id=method_session.id,
                    risk_id=risk_id,
                )
                result.set_result_data({
                    'rank': rank,
                    'parameter': param,
                    'timestamp': datetime.utcnow().isoformat(),
                })
                db.session.add(result)

        method_session.status = 'completed'
        method_session.completed_at = datetime.utcnow()
        db.session.commit()

        return {'complete': True, 'context': {}}

    def get_context(self, method_session, risks):
        config = method_session.method.get_config()
        mode = config.get('mode', 'overall')
        parameters = config.get('parameters', [])
        if mode == 'per_parameter' and parameters:
            params_to_process = parameters
        else:
            params_to_process = ['overall']
        return {
            'risks': risks,
            'mode': mode,
            'parameters': params_to_process,
        }

    def get_results_summary(self, method_session, risks):
        from app.models import AssessmentResult
        results = AssessmentResult.query.filter_by(method_session_id=method_session.id).all()

        summary = []
        for r in results:
            data = r.get_result_data()
            risk = next((ri for ri in risks if ri.id == r.risk_id), None)
            summary.append({
                'risk': risk.name if risk else f'Risk {r.risk_id}',
                'risk_id': r.risk_id,
                'rank': data.get('rank', 0),
                'parameter': data.get('parameter', 'overall'),
            })
        summary.sort(key=lambda x: (x['parameter'], x['rank']))
        return {'type': 'ranking', 'results': summary}
