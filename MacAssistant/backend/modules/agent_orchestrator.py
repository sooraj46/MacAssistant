"""
Agent Orchestrator Module
Manages the execution of plans, including handling acceptance, rejection, 
and revisions of plans, as well as the execution of individual commands.
"""

import time
from flask_socketio import emit
from config import active_config

class AgentOrchestrator:
    """Class for orchestrating plan execution."""
    
    def __init__(self, llm_integration, command_generator, safety_checker, execution_engine, logger):
        """
        Initialize the Agent Orchestrator.
        
        Args:
            llm_integration: LLM Integration module instance
            command_generator: Command Generator module instance
            safety_checker: Safety Checker module instance
            execution_engine: Execution Engine module instance
            logger: Logger module instance
        """
        self.llm_integration = llm_integration
        self.command_generator = command_generator
        self.safety_checker = safety_checker
        self.execution_engine = execution_engine
        self.logger = logger
        
        # Store active plans and their state
        self.active_plans = {}
        self.pending_commands = {}
        
    def execute_plan(self, plan_id):
        """
        Begin executing a plan.
        
        Args:
            plan_id (str): The ID of the plan to execute
        """
        # Get the plan
        plan = self.llm_integration.plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Update plan status
        plan['status'] = 'executing'
        self.active_plans[plan_id] = plan
        
        # Begin execution of the first step
        self._execute_step(plan_id, 0)
    
    def _execute_step(self, plan_id, step_index):
        """
        Execute a single step in a plan.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the step to execute
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Check if all steps are complete
        if step_index >= len(plan['steps']):
            self._complete_plan(plan_id)
            return
        
        # Get the current step
        step = plan['steps'][step_index]
        
        # Update step status
        step['status'] = 'executing'
        self._emit_status_update(plan_id)
        
        # Generate command for the step
        command = self.command_generator.generate_command(step['description'])
        step['command'] = command
        
        # Check if command is risky
        is_risky = step['is_risky'] or self.safety_checker.is_risky(command)
        
        if is_risky:
            # Store command for confirmation
            command_id = f"{plan_id}_{step_index}"
            self.pending_commands[command_id] = {
                'plan_id': plan_id,
                'step_index': step_index,
                'command': command
            }
            
            # Mark step as awaiting confirmation
            step['status'] = 'awaiting_confirmation'
            self._emit_status_update(plan_id, {
                'event': 'risky_command',
                'command_id': command_id,
                'command': command,
                'step_description': step['description']
            })
        else:
            # Execute command directly
            self._execute_command_internal(plan_id, step_index, command)
    
    def execute_command(self, command_id):
        """
        Execute a previously pending command after user confirmation.
        
        Args:
            command_id (str): The ID of the command to execute
        """
        # Get the pending command
        command_info = self.pending_commands.get(command_id)
        if not command_info:
            self.logger.log_error(f"Command with ID {command_id} not found")
            return
        
        # Execute the command
        self._execute_command_internal(
            command_info['plan_id'],
            command_info['step_index'],
            command_info['command']
        )
        
        # Remove from pending commands
        del self.pending_commands[command_id]
    
    def skip_command(self, command_id):
        """
        Skip a previously pending command after user rejection.
        
        Args:
            command_id (str): The ID of the command to skip
        """
        # Get the pending command
        command_info = self.pending_commands.get(command_id)
        if not command_info:
            self.logger.log_error(f"Command with ID {command_id} not found")
            return
        
        # Get the plan and step
        plan_id = command_info['plan_id']
        step_index = command_info['step_index']
        
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Mark the step as skipped
        plan['steps'][step_index]['status'] = 'skipped'
        self._emit_status_update(plan_id)
        
        # Remove from pending commands
        del self.pending_commands[command_id]
        
        # Move to the next step
        self._execute_step(plan_id, step_index + 1)
    
    def _execute_command_internal(self, plan_id, step_index, command):
        """
        Internal method to execute a command.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the step
            command (str): The command to execute
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Get the step
        step = plan['steps'][step_index]
        
        # Log the command execution
        self.logger.log_command_execution(plan_id, step_index, command)
        
        # Execute the command
        success, stdout, stderr = self.execution_engine.execute(command)
        
        # Update step status based on execution result
        if success:
            step['status'] = 'completed'
            step['stdout'] = stdout
            step['stderr'] = stderr
            
            # Log success
            self.logger.log_command_success(plan_id, step_index, stdout, stderr)
            
            # Emit status update
            self._emit_status_update(plan_id, {
                'event': 'step_completed',
                'step_index': step_index,
                'stdout': stdout,
                'stderr': stderr
            })
            
            # Move to the next step
            self._execute_step(plan_id, step_index + 1)
        else:
            step['status'] = 'failed'
            step['stdout'] = stdout
            step['stderr'] = stderr
            
            # Log failure
            self.logger.log_command_failure(plan_id, step_index, stdout, stderr)
            
            # Emit status update
            self._emit_status_update(plan_id, {
                'event': 'step_failed',
                'step_index': step_index,
                'stdout': stdout,
                'stderr': stderr
            })
    
    def request_revision(self, plan_id, feedback):
        """
        Request a revision of a plan.
        
        Args:
            plan_id (str): The ID of the plan to revise
            feedback (str): Feedback for the revision
            
        Returns:
            dict: The revised plan
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return None
        
        # Mark the plan as being revised
        plan['status'] = 'revising'
        self._emit_status_update(plan_id)
        
        # Request a revised plan
        revised_plan = self.llm_integration.revise_plan(plan_id, feedback)
        
        # Remove the old plan from active plans
        del self.active_plans[plan_id]
        
        # Add the revised plan
        self.active_plans[revised_plan['id']] = revised_plan
        
        # Emit status update
        self._emit_status_update(revised_plan['id'], {
            'event': 'plan_revised',
            'original_plan_id': plan_id,
            'revised_plan_id': revised_plan['id']
        })
        
        return revised_plan
    
    def abort_plan(self, plan_id):
        """
        Abort a plan execution.
        
        Args:
            plan_id (str): The ID of the plan to abort
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Mark the plan as aborted
        plan['status'] = 'aborted'
        
        # Log the abort
        self.logger.log_plan_abort(plan_id)
        
        # Emit status update
        self._emit_status_update(plan_id, {
            'event': 'plan_aborted'
        })
        
        # Remove from active plans
        del self.active_plans[plan_id]
    
    def _complete_plan(self, plan_id):
        """
        Mark a plan as completed.
        
        Args:
            plan_id (str): The ID of the plan
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Mark the plan as completed
        plan['status'] = 'completed'
        
        # Log the completion
        self.logger.log_plan_completion(plan_id)
        
        # Emit status update
        self._emit_status_update(plan_id, {
            'event': 'plan_completed'
        })
        
        # Remove from active plans
        del self.active_plans[plan_id]
    
    def _emit_status_update(self, plan_id, additional_data=None):
        """
        Emit a status update for the given plan.
        
        Args:
            plan_id (str): The ID of the plan
            additional_data (dict, optional): Additional data to include in the update
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            return
        
        # Prepare update data
        update_data = {
            'plan_id': plan_id,
            'status': plan['status'],
            'steps': plan['steps'],
            'timestamp': time.time()
        }
        
        # Add additional data if provided
        if additional_data:
            update_data.update(additional_data)
        
        # Emit the update
        emit('execution_update', update_data)