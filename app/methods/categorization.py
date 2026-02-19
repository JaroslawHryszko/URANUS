from datetime import datetime
from app.methods.base import BaseMethod


class CategorizationMethod(BaseMethod):
    """Categorization / bucketing risk assessment method."""

    def default_config(self):
        return {
            'categories': ['Critical', 'High', 'Medium', 'Low', 'Negligible'],
            'mode': 'overall',  # overall or per_parameter
            'parameters': [],  # only used if mode=per_parameter
        }

    def get_template(self):
        return 'methods/categorization.html'

    def process_response(self, form_data, method_session, risks):
        from app.models import AssessmentResult
        from app import db

        config = method_session.method.get_config()
        categories = config.get('categories', self.default_config()['categories'])
        mode = config.get('mode', 'overall')
        parameters = config.get('parameters', [])

        if mode == 'per_parameter' and parameters:
            params_to_process = parameters
        else:
            params_to_process = ['overall']

        for param in params_to_process:
            for risk in risks:
                key = f"category_{param}_{risk.id}"
                category = form_data.get(key, '')
                if not category or category not in categories:
                    return {
                        'complete': False,
                        'error': 'Please assign a category to all risks.',
                        'context': self.get_context(method_session, risks),
                    }

                result = AssessmentResult(
                    method_session_id=method_session.id,
                    risk_id=risk.id,
                )
                result.set_result_data({
                    'category': category,
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
        categories = config.get('categories', self.default_config()['categories'])
        mode = config.get('mode', 'overall')
        parameters = config.get('parameters', [])
        if mode == 'per_parameter' and parameters:
            params_to_process = parameters
        else:
            params_to_process = ['overall']
        return {
            'risks': risks,
            'categories': categories,
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
                'category': data.get('category', ''),
                'parameter': data.get('parameter', 'overall'),
            })
        summary.sort(key=lambda x: (x['parameter'], x['category']))
        return {'type': 'categorization', 'results': summary}
