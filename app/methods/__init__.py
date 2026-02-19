from app.methods.uranus_method import UranusMethod
from app.methods.matrix import MatrixMethod
from app.methods.ranking import RankingMethod
from app.methods.budget import BudgetMethod
from app.methods.categorization import CategorizationMethod

METHOD_REGISTRY = {
    'uranus': UranusMethod,
    'matrix': MatrixMethod,
    'ranking': RankingMethod,
    'budget': BudgetMethod,
    'categorization': CategorizationMethod,
}

METHOD_TYPE_LABELS = {
    'uranus': 'Pairwise Comparison (Uranus)',
    'matrix': 'Matrix / FMEA',
    'ranking': 'Direct Ranking (Drag & Drop)',
    'budget': 'Budget Allocation',
    'categorization': 'Categorization',
}


def get_method_handler(method_type):
    cls = METHOD_REGISTRY.get(method_type)
    if cls is None:
        raise ValueError(f"Unknown method type: {method_type}")
    return cls()


def get_default_config(method_type):
    handler = get_method_handler(method_type)
    return handler.default_config()
