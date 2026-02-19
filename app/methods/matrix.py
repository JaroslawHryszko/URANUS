from datetime import datetime
from app.methods.base import BaseMethod


class MatrixMethod(BaseMethod):
    """Matrix / FMEA risk assessment method."""

    def default_config(self):
        return {
            'criteria': [
                {
                    'name': 'probability',
                    'display_name': 'Probability',
                    'scale_min': 1,
                    'scale_max': 5,
                    'labels': {
                        '1': 'Very Low',
                        '2': 'Low',
                        '3': 'Medium',
                        '4': 'High',
                        '5': 'Very High',
                    }
                },
                {
                    'name': 'impact',
                    'display_name': 'Impact',
                    'scale_min': 1,
                    'scale_max': 5,
                    'labels': {
                        '1': 'Very Low',
                        '2': 'Low',
                        '3': 'Medium',
                        '4': 'High',
                        '5': 'Very High',
                    }
                },
            ],
            'aggregation': 'product',  # product or weighted_sum
            'weights': {},  # only used for weighted_sum
        }

    def get_template(self):
        return 'methods/matrix.html'

    def process_response(self, form_data, method_session, risks):
        from app.models import AssessmentResult
        from app import db

        config = method_session.method.get_config()
        criteria = config.get('criteria', self.default_config()['criteria'])
        aggregation = config.get('aggregation', 'product')
        weights = config.get('weights', {})

        for risk in risks:
            criteria_values = {}
            for criterion in criteria:
                key = f"{criterion['name']}_{risk.id}"
                val = form_data.get(key)
                if val is None or val == '':
                    return {
                        'complete': False,
                        'error': f"Please fill in all fields for all risks.",
                        'context': self.get_context(method_session, risks),
                    }
                criteria_values[criterion['name']] = int(val)

            # Calculate priority
            if aggregation == 'product':
                priority = 1
                for v in criteria_values.values():
                    priority *= v
            else:  # weighted_sum
                priority = 0
                for name, v in criteria_values.items():
                    w = weights.get(name, 1)
                    priority += v * w

            result = AssessmentResult(
                method_session_id=method_session.id,
                risk_id=risk.id,
            )
            result.set_result_data({
                'criteria_values': criteria_values,
                'priority': priority,
                'timestamp': datetime.utcnow().isoformat(),
            })
            db.session.add(result)

        method_session.status = 'completed'
        method_session.completed_at = datetime.utcnow()
        db.session.commit()

        return {
            'complete': True,
            'context': {},
        }

    def get_context(self, method_session, risks):
        config = method_session.method.get_config()
        criteria = config.get('criteria', self.default_config()['criteria'])
        return {
            'criteria': criteria,
            'risks': risks,
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
                'criteria_values': data.get('criteria_values', {}),
                'priority': data.get('priority', 0),
            })
        summary.sort(key=lambda x: x['priority'], reverse=True)
        return {'type': 'matrix', 'results': summary}
