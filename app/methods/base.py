from abc import ABC, abstractmethod


class BaseMethod(ABC):
    """Base class for all risk assessment methods."""

    @abstractmethod
    def default_config(self):
        """Return default configuration dict for this method type."""
        pass

    @abstractmethod
    def get_template(self):
        """Return the Jinja2 template name for this method."""
        pass

    @abstractmethod
    def process_response(self, form_data, method_session, risks):
        """
        Process form submission data.

        Args:
            form_data: request.form dict
            method_session: MethodSession instance
            risks: list of Risk instances

        Returns:
            dict with keys:
                'complete': bool - whether the method is finished
                'results': list of AssessmentResult data dicts (to save)
                'context': dict - extra template context for next render
        """
        pass

    @abstractmethod
    def get_context(self, method_session, risks):
        """
        Get template context for rendering.

        Args:
            method_session: MethodSession instance
            risks: list of Risk instances

        Returns:
            dict of template variables
        """
        pass

    @abstractmethod
    def get_results_summary(self, method_session, risks):
        """
        Get a summary of results for admin display.

        Args:
            method_session: MethodSession instance
            risks: list of Risk instances

        Returns:
            list of dicts with risk results
        """
        pass
