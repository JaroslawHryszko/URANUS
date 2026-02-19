import json
import copy
from datetime import datetime
from app.methods.base import BaseMethod


class UranusMethod(BaseMethod):
    """Wrapper around uranus.py for per-session pairwise comparison."""

    def default_config(self):
        return {
            'parameters': ['impact', 'probability'],
        }

    def get_template(self):
        return 'methods/uranus.html'

    def _create_uranus(self, parameters, risk_names):
        """Create a new Uranus instance. Import here to avoid global state."""
        import sys
        import os
        # Ensure uranus.py is importable
        neptune_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        if neptune_dir not in sys.path:
            sys.path.insert(0, neptune_dir)
        from uranus import Uranus
        u = Uranus(list(parameters), list(risk_names))
        u.set_logging(False)  # Don't write log files from per-session instances
        return u

    def _serialize_state(self, u):
        """Serialize Uranus instance state to JSON-compatible dict."""
        return {
            'p_names': u.p_names,
            'e_names': u.e_names,
            'num_parameters': u.num_parameters,
            'num_elements': u.num_elements,
            'num_comparisons': u.num_comparisons,
            'prioritized': u.prioritized,
            'next_elem': u.next_elem,
            'next_parameter': u.next_parameter,
            'next_range': u.next_range,
            'final_list': u.final_list,
        }

    def _restore_state(self, state, parameters, risk_names):
        """Restore Uranus instance from serialized state."""
        u = self._create_uranus(parameters, risk_names)
        u.p_names = state['p_names']
        u.e_names = state['e_names']
        u.num_parameters = state['num_parameters']
        u.num_elements = state['num_elements']
        u.num_comparisons = state['num_comparisons']
        u.prioritized = state['prioritized']
        u.next_elem = state['next_elem']
        u.next_parameter = state['next_parameter']
        u.next_range = state['next_range']
        u.final_list = state.get('final_list', [])
        return u

    def _get_or_create_uranus(self, method_session, risks):
        """Get existing Uranus instance from session state or create new one."""
        config = method_session.method.get_config()
        parameters = config.get('parameters', ['impact', 'probability'])
        risk_names = [r.name for r in risks]

        state = method_session.get_uranus_state()
        if state:
            return self._restore_state(state, parameters, risk_names)
        else:
            u = self._create_uranus(parameters, risk_names)
            return u

    def process_response(self, form_data, method_session, risks):
        from app.models import AssessmentResult
        from app import db

        u = self._get_or_create_uranus(method_session, risks)

        choice = int(form_data['choice'])
        a = int(form_data['a'])
        b = int(form_data['b'])
        c = int(form_data['c'])

        # Save comparison result
        chosen = "A" if choice == 0 else "B"
        result = AssessmentResult(
            method_session_id=method_session.id,
            risk_id=risks[a].id if a < len(risks) else None,
        )
        result.set_result_data({
            'comparison_step': u.num_comparisons,
            'risk_a_id': risks[a].id if a < len(risks) else None,
            'risk_b_id': risks[b].id if b < len(risks) else None,
            'risk_a_index': a,
            'risk_b_index': b,
            'parameter': u.p_names[c] if c < len(u.p_names) else '',
            'parameter_index': c,
            'chosen': chosen,
            'timestamp': datetime.utcnow().isoformat(),
        })
        db.session.add(result)

        # Apply choice to Uranus
        try:
            u.set_priority(choice)
        except Exception:
            pass

        # Save state
        method_session.set_uranus_state(self._serialize_state(u))

        # Check if done
        if u.is_done():
            method_session.status = 'completed'
            method_session.completed_at = datetime.utcnow()

            # Save final ranking
            final_list = u.prioritized_list()
            if final_list:
                ranking_result = AssessmentResult(
                    method_session_id=method_session.id,
                    risk_id=None,
                )
                ranking_result.set_result_data({
                    'type': 'final_ranking',
                    'ranking': final_list,
                    'prioritized': u.prioritized,
                    'num_comparisons': u.num_comparisons,
                    'timestamp': datetime.utcnow().isoformat(),
                })
                db.session.add(ranking_result)

        db.session.commit()

        return {
            'complete': u.is_done(),
            'context': self.get_context(method_session, risks),
        }

    def get_context(self, method_session, risks):
        u = self._get_or_create_uranus(method_session, risks)

        try:
            a, b, c = u.next_to_process()
        except Exception:
            a, b, c = None, None, None

        # Save state after next_to_process (it may modify internal state)
        method_session.set_uranus_state(self._serialize_state(u))
        from app import db
        db.session.commit()

        if a is None or b is None or c is None:
            return {
                'done': True,
                'progress': 100,
            }

        return {
            'done': False,
            'a': a,
            'b': b,
            'c': c,
            'p_names': u.p_names,
            'e_names': u.e_names,
            'progress': u.progress(),
        }

    def get_results_summary(self, method_session, risks):
        """Get the final ranking from stored results."""
        from app.models import AssessmentResult
        results = AssessmentResult.query.filter_by(method_session_id=method_session.id).all()

        # Find the final_ranking result
        for r in results:
            data = r.get_result_data()
            if data.get('type') == 'final_ranking':
                ranking = data.get('ranking', [])
                risk_names = [risks[i].name if i < len(risks) else f'Risk {i}' for i in ranking]
                return {
                    'type': 'ranking',
                    'ranking': [{'rank': idx + 1, 'risk': name, 'risk_index': ri}
                                for idx, (ri, name) in enumerate(zip(ranking, risk_names))],
                    'num_comparisons': data.get('num_comparisons', 0),
                }

        # Not completed yet - show comparisons made
        comparisons = [r.get_result_data() for r in results if r.get_result_data().get('type') != 'final_ranking']
        return {
            'type': 'in_progress',
            'comparisons_made': len(comparisons),
        }
