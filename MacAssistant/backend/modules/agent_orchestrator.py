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
        # Debug output
        print(f"DEBUG: Beginning execution of plan {plan_id}")
        
        # Get the plan
        plan = self.llm_integration.plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            print(f"DEBUG: Plan with ID {plan_id} not found")
            return
        
        # Debug output for plan details
        print(f"DEBUG: Plan details: {plan}")
        
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
        # Debug output
        print(f"DEBUG: Executing step {step_index} of plan {plan_id}")
        
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            print(f"DEBUG: Plan with ID {plan_id} not found during step execution")
            return
        
        # Check if all steps are complete
        if step_index >= len(plan['steps']):
            print(f"DEBUG: All steps completed for plan {plan_id}")
            self._complete_plan(plan_id)
            return
        
        # Get the current step
        step = plan['steps'][step_index]
        print(f"DEBUG: Current step details: {step}")
        
        # Update step status
        step['status'] = 'executing'
        self._emit_status_update(plan_id)
        
        # Check if we have a command in the step already (from LLM-generated plan)
        if 'command' in step and step['command']:
            command = step['command']
            print(f"DEBUG: Using command from LLM-generated plan: '{command}'")
        else:
            # Generate command from description as fallback
            description = step['description']
            
            # Check if this is an observation step
            is_observe = step.get('is_observe', False) or any(word in description.lower() for word in ["observe", "note", "check the output", "examine"]) and not any(cmd in description.lower() for cmd in ["run", "type", "execute", "create"])
            
            if is_observe:
                print(f"DEBUG: Step appears to be an observation step without command: '{description}'")
                # For observation steps, just echo a confirmation
                command = f"echo 'Step completed: {description}'"
            else:
                # Regular command generation
                print(f"DEBUG: Generating command for description: '{description}'")
                command = self.command_generator.generate_command(description)
                
            step['command'] = command
            
        print(f"DEBUG: Final command to execute: '{command}'")
        
        # Check if command is risky
        is_risky = step.get('is_risky', False) or self.safety_checker.is_risky(command)
        
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
        
        # Debug - Print current step description
        print(f"DEBUG: Executing step: {step['description']}")
        print(f"DEBUG: Generated command: {command}")
        
        # Log the command execution
        self.logger.log_command_execution(plan_id, step_index, command)
        
        # Execute the command
        success, stdout, stderr = self.execution_engine.execute(command)
        
        # Debug - Print command execution results
        print(f"DEBUG: Command execution success: {success}")
        print(f"DEBUG: stdout: {stdout}")
        print(f"DEBUG: stderr: {stderr}")
        
        # Update step status based on execution result
        if success:
            step['status'] = 'completed'
            step['stdout'] = stdout
            step['stderr'] = stderr
            
            # Log success
            self.logger.log_command_success(plan_id, step_index, stdout, stderr)
            
            # Store execution results for possible plan revision
            if not 'step_results' in plan:
                plan['step_results'] = {}
                
            plan['step_results'][str(step['number'])] = {
                'status': 'completed',
                'stdout': stdout,
                'stderr': stderr
            }
            
            # Emit status update
            self._emit_status_update(plan_id, {
                'event': 'step_completed',
                'step_index': step_index,
                'stdout': stdout,
                'stderr': stderr
            })
            
            # Check if we need to pause for user observation
            if step.get('is_observe', False):
                # Emit an event for the UI to display observation prompt
                self._emit_status_update(plan_id, {
                    'event': 'observation_required',
                    'step_index': step_index,
                    'description': step['description'],
                    'stdout': stdout
                })
                # We'll continue when the user confirms observation is done
                return
            
            # Move to the next step
            self._execute_step(plan_id, step_index + 1)
        else:
            step['status'] = 'failed'
            step['stdout'] = stdout
            step['stderr'] = stderr
            
            # Log failure
            self.logger.log_command_failure(plan_id, step_index, stdout, stderr)
            
            # Store execution results for plan revision
            if not 'step_results' in plan:
                plan['step_results'] = {}
                
            plan['step_results'][str(step['number'])] = {
                'status': 'failed',
                'stdout': stdout,
                'stderr': stderr
            }
            
            # Emit status update
            self._emit_status_update(plan_id, {
                'event': 'step_failed',
                'step_index': step_index,
                'stdout': stdout,
                'stderr': stderr
            })
            
            # Try to auto-repair the plan
            self._attempt_plan_revision(plan_id, step_index, stderr)
    
    def _attempt_plan_revision(self, plan_id, step_index, error_message):
        """
        Attempt to automatically revise a plan after a step failure.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the failed step
            error_message (str): The error message
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
            
        # Generate feedback for revision based on the error
        step = plan['steps'][step_index]
        
        feedback = f"Step {step['number']} failed with error: {error_message}. "
        feedback += "Please revise the plan to fix this issue. "
        feedback += f"The failing command was: {step['command']}."
        
        # Emit status update for auto-repair attempt
        self._emit_status_update(plan_id, {
            'event': 'auto_repair_attempt',
            'step_index': step_index,
            'error': error_message
        })
        
        # Try to revise the plan automatically
        try:
            self.request_revision(plan_id, feedback, auto_revision=True)
        except Exception as e:
            self.logger.log_error(f"Auto-repair failed: {str(e)}")
            # Fall back to manual intervention notification
            self._emit_status_update(plan_id, {
                'event': 'auto_repair_failed',
                'step_index': step_index,
                'error': str(e)
            })
    
    def request_revision(self, plan_id, feedback, auto_revision=False):
        """
        Request a revision of a plan.
        
        Args:
            plan_id (str): The ID of the plan to revise
            feedback (str): Feedback for the revision
            auto_revision (bool): Whether this is an automatic revision
            
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
        
        # Request a revised plan with execution results
        step_results = plan.get('step_results', {})
        revised_plan = self.llm_integration.revise_plan(plan_id, feedback, step_results)
        
        # Remove the old plan from active plans
        del self.active_plans[plan_id]
        
        # Add the revised plan
        self.active_plans[revised_plan['id']] = revised_plan
        
        # Include the revision summary in the update
        revision_summary = revised_plan.get('revision_summary', 'Plan was revised')
        
        # Emit status update
        self._emit_status_update(revised_plan['id'], {
            'event': 'plan_revised',
            'original_plan_id': plan_id,
            'revised_plan_id': revised_plan['id'],
            'is_auto_revision': auto_revision,
            'revision_summary': revision_summary
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
        
    def observation_completed(self, plan_id, step_index, feedback=None):
        """
        Handle user confirmation that an observation step has been completed.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the observation step
            feedback (str, optional): Any user feedback on the observation
        """
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
            
        # Get the step
        step = plan['steps'][step_index]
        if not step.get('is_observe', False):
            self.logger.log_warning(f"Step {step_index} in plan {plan_id} is not an observation step")
            
        # If feedback was provided, store it
        if feedback:
            step['feedback'] = feedback
            
            # Store in step results for later revisions if needed
            if 'step_results' in plan:
                if str(step['number']) in plan['step_results']:
                    plan['step_results'][str(step['number'])]['feedback'] = feedback
                    
        # Emit status update
        self._emit_status_update(plan_id, {
            'event': 'observation_completed',
            'step_index': step_index,
            'feedback': feedback
        })
        
        # Continue to the next step
        self._execute_step(plan_id, step_index + 1)
    
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
        emit('execution_update', update_data, namespace='/', broadcast=True)