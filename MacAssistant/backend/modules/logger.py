"""
Logger Module
Handles logging of system events, user actions, and command executions.
"""

import os
import json
import time
import logging
from datetime import datetime
from config import active_config

class Logger:
    """Class for logging system events."""
    
    def __init__(self):
        """Initialize the Logger."""
        # Create log directory if it doesn't exist
        self.log_dir = active_config.LOG_DIR
        os.makedirs(self.log_dir, exist_ok=True)
        
        # Set up Python logging
        self.log_level = getattr(logging, active_config.LOG_LEVEL)
        self.logger = logging.getLogger('macassistant')
        self.logger.setLevel(self.log_level)
        
        # File handler for Python logging
        log_file = os.path.join(self.log_dir, 'macassistant.log')
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(self.log_level)
        
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        
        # Add handler to logger
        self.logger.addHandler(file_handler)
        
        # Event log file
        self.event_log_file = os.path.join(self.log_dir, 'events.jsonl')
    
    def _log_event(self, event_type, data):
        """
        Log an event to the event log file.
        
        Args:
            event_type (str): The type of event
            data (dict): Event data
        """
        # Create event object
        event = {
            'timestamp': datetime.now().isoformat(),
            'type': event_type,
            'data': data
        }
        
        # Write to event log file
        with open(self.event_log_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
        
        # Also log to Python logger
        self.logger.info(f"{event_type}: {json.dumps(data)}")
    
    def log_request(self, request):
        """
        Log a user request.
        
        Args:
            request (str): The user's request
        """
        self._log_event('user_request', {'request': request})
    
    def log_plan(self, plan):
        """
        Log a generated plan.
        
        Args:
            plan (dict): The generated plan
        """
        self._log_event('plan_generated', {'plan': plan})
    
    def log_plan_acceptance(self, plan_id):
        """
        Log acceptance of a plan.
        
        Args:
            plan_id (str): The ID of the plan
        """
        self._log_event('plan_accepted', {'plan_id': plan_id})
    
    def log_plan_rejection(self, plan_id, feedback=None):
        """
        Log rejection of a plan.
        
        Args:
            plan_id (str): The ID of the plan
            feedback (str, optional): User feedback for rejection
        """
        data = {'plan_id': plan_id}
        if feedback:
            data['feedback'] = feedback
        self._log_event('plan_rejected', data)
    
    def log_plan_completion(self, plan_id):
        """
        Log completion of a plan.
        
        Args:
            plan_id (str): The ID of the plan
        """
        self._log_event('plan_completed', {'plan_id': plan_id})
    
    def log_plan_abort(self, plan_id):
        """
        Log abortion of a plan.
        
        Args:
            plan_id (str): The ID of the plan
        """
        self._log_event('plan_aborted', {'plan_id': plan_id})
    
    def log_command_execution(self, plan_id, step_index, command):
        """
        Log execution of a command.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the step
            command (str): The command being executed
        """
        self._log_event('command_executed', {
            'plan_id': plan_id,
            'step_index': step_index,
            'command': command
        })
    
    def log_command_success(self, plan_id, step_index, stdout, stderr):
        """
        Log successful execution of a command.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the step
            stdout (str): Standard output from the command
            stderr (str): Standard error from the command
        """
        self._log_event('command_succeeded', {
            'plan_id': plan_id,
            'step_index': step_index,
            'stdout': stdout,
            'stderr': stderr
        })
    
    def log_command_failure(self, plan_id, step_index, stdout, stderr):
        """
        Log failed execution of a command.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the step
            stdout (str): Standard output from the command
            stderr (str): Standard error from the command
        """
        self._log_event('command_failed', {
            'plan_id': plan_id,
            'step_index': step_index,
            'stdout': stdout,
            'stderr': stderr
        })
    
    def log_command_confirmation(self, command_id, confirmed):
        """
        Log confirmation or rejection of a risky command.
        
        Args:
            command_id (str): The ID of the command
            confirmed (bool): Whether the command was confirmed
        """
        self._log_event('command_confirmation', {
            'command_id': command_id,
            'confirmed': confirmed
        })
    
    def log_error(self, message):
        """
        Log an error message.
        
        Args:
            message (str): The error message
        """
        self._log_event('error', {'message': message})
        self.logger.error(message)
    
    def get_logs(self, log_type='all', start_date=None, end_date=None):
        """
        Get logs for a given type and date range.
        
        Args:
            log_type (str): The type of logs to get ('all' or a specific type)
            start_date (str): The start date for the logs (ISO format)
            end_date (str): The end date for the logs (ISO format)
            
        Returns:
            list: A list of log events
        """
        logs = []
        
        try:
            with open(self.event_log_file, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        
                        # Filter by type
                        if log_type != 'all' and event['type'] != log_type:
                            continue
                        
                        # Filter by date range
                        if start_date or end_date:
                            event_date = datetime.fromisoformat(event['timestamp'])
                            
                            if start_date:
                                start = datetime.fromisoformat(start_date)
                                if event_date < start:
                                    continue
                            
                            if end_date:
                                end = datetime.fromisoformat(end_date)
                                if event_date > end:
                                    continue
                        
                        logs.append(event)
                    except json.JSONDecodeError:
                        continue
        except FileNotFoundError:
            self.logger.warning(f"Log file {self.event_log_file} not found")
        
        return logs