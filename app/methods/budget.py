from datetime import datetime
from app.methods.base import BaseMethod


class BudgetMethod(BaseMethod):
    """Budget allocation risk assessment method."""

    def default_config(self):
        return {
            'total_points': 100,
            'mode': 'overall',  # overall or per_parameter
            'parameters': [],  # only used if mode=per_parameter
        }

    def get_template(self):
        return 'methods/budget.html'

    def process_response(self, form_data, method_session, risks):
        from app.models import AssessmentResult
        from app import db

        config = method_session.method.get_config()
        total_points = config.get('total_points', 100)
        mode = config.get('mode', 'overall')
        parameters = config.get('parameters', [])

        if mode == 'per_parameter' and parameters:
            params_to_process = parameters
        else:
            params_to_process = ['overall']

        for param in params_to_process:
            allocated_sum = 0
            allocations = {}
            for risk in risks:
                key = f"points_{param}_{risk.id}"
                val = form_data.get(key, '0')
                try:
                    points = int(val)
                except (ValueError, TypeError):
                    points = 0
                if points < 0:
                    return {
                        'complete': False,
                        'error': 'Points cannot be negative.',
                        'context': self.get_context(method_session, risks),
                    }
                allocations[risk.id] = points
                allocated_sum += points

            if allocated_sum != total_points:
                return {
                    'complete': False,
                    'error': f'Total points must equal {total_points}. Currently: {allocated_sum}.',
                    'context': self.get_context(method_session, risks),
                }

            for risk in risks:
                result = AssessmentResult(
                    method_session_id=method_session.id,
                    risk_id=risk.id,
                )
                result.set_result_data({
                    'points': allocations[risk.id],
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
        total_points = config.get('total_points', 100)
        mode = config.get('mode', 'overall')
        parameters = config.get('parameters', [])
        if mode == 'per_parameter' and parameters:
            params_to_process = parameters
        else:
            params_to_process = ['overall']
        return {
            'risks': risks,
            'total_points': total_points,
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
                'points': data.get('points', 0),
                'parameter': data.get('parameter', 'overall'),
            })
        summary.sort(key=lambda x: (x['parameter'], -x['points']))
        return {'type': 'budget', 'results': summary}
