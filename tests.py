import unittest
import os
import tempfile
import json
from datetime import datetime, timedelta
from flask import session
from backend import app, db, User, ClassicResults, NoveltyResults, CustomError, Uranus

class NeptuneTestCase(unittest.TestCase):
    def setUp(self):
        """Set up test environment before each test."""
        # Create a temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()
        
        # Create all tables
        with app.app_context():
            db.create_all()
            
            # Create test user
            test_user = User(user_id='test-user-id', name='Test User')
            db.session.add(test_user)
            db.session.commit()
            
        # Load config for test values
        with open('config.json', 'r') as config_file:
            self.config = json.load(config_file)
            self.risks = self.config['risks']

    def tearDown(self):
        """Clean up after each test."""
        # Close and remove the temporary database
        os.close(self.db_fd)
        os.unlink(self.db_path)
        
    def test_home_page(self):
        """Test that the home page loads correctly."""
        response = self.app.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'URANUS Research Project', response.data)
        
    def test_classic_risk_page_get(self):
        """Test that the classic risk assessment page loads correctly."""
        response = self.app.get('/classic_risk')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Classic Risk Assessment (FMEA Style)', response.data)
        self.assertIn(b'Legend', response.data)
        self.assertIn(b'1 = Lowest', response.data)
        self.assertIn(b'5 = Highest', response.data)
        
        # Check that all risks from config are displayed
        for risk in self.risks:
            self.assertIn(risk.encode(), response.data)
            
        # Check that form has select fields for both probability and impact
        self.assertIn(b'select name="probability_', response.data)
        self.assertIn(b'select name="impact_', response.data)
            
    def test_classic_risk_validation_empty_fields(self):
        """Test validation for empty fields in classic risk form."""
        with app.test_client() as client:
            # Create a session with a user_id
            with client.session_transaction() as sess:
                sess['user_id'] = 'test-user-id'
                
            # Submit form with missing fields
            form_data = {}
            response = client.post('/classic_risk', data=form_data, follow_redirects=True)
            
            # Check that validation error is displayed
            self.assertIn(b'Please fill in all fields', response.data)
            
            # Check that no data was saved to the database
            with app.app_context():
                results = ClassicResults.query.all()
                self.assertEqual(len(results), 0)
    
    def test_classic_risk_submit_complete(self):
        """Test submitting complete data for classic risk assessment."""
        with app.test_client() as client:
            # Create a session with a user_id
            with client.session_transaction() as sess:
                sess['user_id'] = 'test-user-id'
                
            # Prepare form data with all fields filled
            form_data = {}
            for risk in self.risks:
                form_data[f'probability_{risk}'] = '3'
                form_data[f'impact_{risk}'] = '4'
                
            # Submit the form
            response = client.post('/classic_risk', data=form_data, follow_redirects=True)
            
            # Check that submission was successful
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'all_done', response.data)
            
            # Check that data was saved to the database
            with app.app_context():
                results = ClassicResults.query.all()
                self.assertEqual(len(results), len(self.risks))
                
                # Check that the calculations are correct (probability * impact)
                for result in results:
                    self.assertEqual(result.probability, 3)
                    self.assertEqual(result.impact, 4)
                    self.assertEqual(result.priority, 12)  # 3 * 4 = 12
                    
                # Check that start_time and end_time were recorded
                for result in results:
                    self.assertIsNotNone(result.start_time)
                    self.assertIsNotNone(result.end_time)
                    
    def test_novelty_risk_page(self):
        """Test that the novelty risk assessment page loads correctly."""
        response = self.app.get('/novelty_risk')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Comparison-based Risk Assessment', response.data)
        
    def test_novelty_risk_submission(self):
        """Test the submission of novelty risk assessment."""
        with app.test_client() as client:
            # Create a session with a user_id
            with client.session_transaction() as sess:
                sess['user_id'] = 'test-user-id'
                
            # Get initial values from the page
            response = client.get('/novelty_risk')
            
            # Extract form values (this is simplified - in a real test you would parse the HTML)
            # For testing, we'll make assumptions about the initial values
            form_data = {
                'a': '0',
                'b': '1',
                'c': '0',
                'choice': '0'  # Choose option A
            }
            
            # Submit the form
            response = client.post('/novelty_risk', data=form_data, follow_redirects=True)
            
            # Check that submission was processed
            self.assertEqual(response.status_code, 200)
            
            # Check that data was saved to the database
            with app.app_context():
                results = NoveltyResults.query.all()
                self.assertGreater(len(results), 0)
                
                # Check that the latest result matches our submission
                latest = results[-1]
                self.assertEqual(latest.risk_a_id, 0)
                self.assertEqual(latest.risk_b_id, 1)
                self.assertEqual(latest.chosen_risk, 'A')
                
                # Check that start_time and end_time were recorded
                self.assertIsNotNone(latest.start_time)
                self.assertIsNotNone(latest.end_time)
                
    def test_flash_messages_in_template(self):
        """Test that flash messages are properly displayed in the template."""
        with app.test_client() as client:
            # Access a page that should trigger a flash message
            with client.session_transaction() as sess:
                sess['user_id'] = 'test-user-id'
                
            # Submit an incomplete form to trigger validation error
            form_data = {}  # Empty form data
            response = client.post('/classic_risk', data=form_data, follow_redirects=True)
            
            # Check that the flash message is in the response
            self.assertIn(b'Please fill in all fields', response.data)
            self.assertIn(b'alert-danger', response.data)
            
    def test_uranus_custom_error_handling(self):
        """Test that CustomError exceptions from Uranus are properly handled."""
        # Create a test Uranus instance
        u = Uranus(['impact', 'probability'], ['Risk 1', 'Risk 2'])
        
        # Test that a CustomError is raised when next_range is empty
        u.next_elem = 0
        u.next_parameter = 0
        u.next_range = []
        
        with self.assertRaises(CustomError):
            u.set_priority(0)
            
if __name__ == '__main__':
    unittest.main()