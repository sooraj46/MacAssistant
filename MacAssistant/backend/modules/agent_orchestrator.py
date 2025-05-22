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
        plan = self.llm_integration.get_plan(plan_id)
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
        
        # Check command safety explicitly
        if not self.safety_checker.is_safe(command):
            self.logger.log_error(f"Unsafe command detected: {command}")
            step['status'] = 'blocked'
            self._emit_status_update(plan_id, {
                'event': 'unsafe_command_blocked',
                'command': command,
                'step_description': step['description']
            })
            return
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
        
        # Before executing, check if this needs human validation first
        if step.get('needs_user_confirmation', False) or plan.get('human_confirmation_required', False):
            # Store command information for later execution
            command_id = f"{plan_id}_{step_index}"
            self.pending_commands[command_id] = {
                'plan_id': plan_id,
                'step_index': step_index,
                'command': command
            }
            
            # Update step status
            step['status'] = 'awaiting_confirmation'
            
            # Emit status update to prompt for confirmation
            self._emit_status_update(plan_id, {
                'event': 'user_confirmation_required',
                'command_id': command_id,
                'step_index': step_index,
                'command': command,
                'description': step['description']
            })
            return
        
        # Execute the command
        success, stdout, stderr = self.execution_engine.execute(command)
        
        # Debug - Print command execution results
        print(f"DEBUG: Command execution success: {success}")
        print(f"DEBUG: stdout: {stdout}")
        print(f"DEBUG: stderr: {stderr}")
        
        # Use LLM to verify the result
        verification = self.llm_integration.verify_execution_result(
            step['description'],
            command,
            stdout,
            stderr,
            success
        )
        
        # Store verification result with step
        step['verification'] = verification
        
        # Update step status based on LLM verification (not just return code)
        llm_success = verification.get('success', success)
        
        if llm_success:
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
                'stderr': stderr,
                'verification': verification
            }
            
            # Emit status update with verification
            self._emit_status_update(plan_id, {
                'event': 'step_completed',
                'step_index': step_index,
                'stdout': stdout,
                'stderr': stderr,
                'verification': verification
            })
            
            # Always show the result to the user and ask to continue
            # This makes the system more conversational and human-in-loop
            self._emit_status_update(plan_id, {
                'event': 'step_completed_feedback',
                'step_index': step_index,
                'description': step['description'],
                'stdout': stdout,
                'explanation': verification.get('explanation', ''),
                'continue_automatically': not active_config.HUMAN_VALIDATION_REQUIRED
            })

            self._summarize_and_update_plan(plan_id, step_index)
            
            # If human validation is required globally, don't auto-continue
            if active_config.HUMAN_VALIDATION_REQUIRED:
                return
                
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
                'stderr': stderr,
                'verification': verification
            }
            
            # Emit status update with verification and suggestion
            self._emit_status_update(plan_id, {
                'event': 'step_failed',
                'step_index': step_index,
                'stdout': stdout,
                'stderr': stderr,
                'verification': verification
            })
            
            # Don't auto-repair, ask the user first
            self._emit_status_update(plan_id, {
                'event': 'step_failure_options',
                'step_index': step_index,
                'verification': verification,
                'suggestion': verification.get('suggestion', '')
            })
    
    def _summarize_and_update_plan(self, plan_id, completed_step_index):
        """
        Summarize progress so far and update the plan/next steps
        based on the LLM response.
        """
        plan = self.active_plans.get(plan_id)
        if not plan:
            return
        
        # Gather partial context
        steps_so_far = plan['steps'][:completed_step_index + 1]
        step_results = plan.get('step_results', {})

        # Possibly gather the steps that remain
        remaining_steps = plan['steps'][completed_step_index + 1:]

        # Call a new method in llm_integration that returns a summary + updated steps
        # Something like: summary, updated_steps = self.llm_integration.summarize_progress_and_update_plan(steps_so_far, step_results, remaining_steps)
        summary, updated_steps = self.llm_integration.summarize_progress_and_update_plan(steps_so_far, step_results, remaining_steps)

        # Store the summary in the plan if you like
        plan['progress_summary'] = summary

        # If updated_steps is not None, it means the LLM is giving new instructions for the next steps
        if updated_steps:
            # Overwrite the plan’s next steps
            # e.g., if updated_steps is a full steps list, replace everything from completed_step_index + 1 onward
            new_plan_steps = plan['steps'][:completed_step_index + 1] + updated_steps
            plan['steps'] = new_plan_steps

        # Optionally emit a status update so the UI can see the new plan
        self._emit_status_update(plan_id, {
            'event': 'progress_summarized',
            'summary': summary,
            'updated_steps': updated_steps
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
    
    def abort_execution(self, plan_id):
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
        self.logger.log_info(f"plan_aborted: {{'plan_id': '{plan_id}'}}")
        
        # Emit status update
        self._emit_status_update(plan_id, {
            'event': 'plan_aborted'
        })
        
        # Remove from active plans
        del self.active_plans[plan_id]
    
    def continue_execution(self, plan_id, skip_failed_step=False):
        """
        Continue executing a plan after a failure or interruption.
        
        Args:
            plan_id (str): The ID of the plan to continue
            skip_failed_step (bool): Whether to skip the failed step and continue with the next step
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
        
        # Find the failed or interrupted step
        current_step_index = None
        for i, step in enumerate(plan['steps']):
            if step['status'] in ['failed', 'executing', 'awaiting_confirmation']:
                current_step_index = i
                break
                
        if current_step_index is None:
            self.logger.log_error(f"No failed or interrupted step found in plan {plan_id}")
            return
        
        # Log the continuation
        self.logger.log_info(f"plan_continued: {{'plan_id': '{plan_id}', 'skip_failed_step': {skip_failed_step}}}")
        
        # Mark the step as skipped if needed
        if skip_failed_step:
            plan['steps'][current_step_index]['status'] = 'skipped'
            current_step_index += 1  # Move to the next step
        
        # Update plan status
        plan['status'] = 'executing'
        
        # Emit status update
        self._emit_status_update(plan_id, {
            'event': 'plan_continued',
            'skip_failed_step': skip_failed_step
        })
        
        # Continue execution
        self._execute_step(plan_id, current_step_index)
    
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
        
    def step_feedback_completed(self, plan_id, step_index, feedback=None, continue_execution=True):
        """
        Handle user feedback on a completed step and determine whether to continue execution.
        
        Args:
            plan_id (str): The ID of the plan
            step_index (int): The index of the step
            feedback (str, optional): Any user feedback on the step execution
            continue_execution (bool): Whether to continue with the next step
        """
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            return
            
        # Get the step
        step = plan['steps'][step_index]
            
        # If feedback was provided, store it
        if feedback:
            step['user_feedback'] = feedback
            
            # Store in step results for later revisions if needed
            if 'step_results' in plan:
                if str(step['number']) in plan['step_results']:
                    plan['step_results'][str(step['number'])]['user_feedback'] = feedback
        
        # Log the feedback
        self.logger.log_info(f"step_feedback: {{'plan_id': '{plan_id}', 'step_index': {step_index}, 'feedback': '{feedback}'}}")
                    
        # Emit status update
        self._emit_status_update(plan_id, {
            'event': 'step_feedback_received',
            'step_index': step_index,
            'feedback': feedback,
            'continue_execution': continue_execution
        })
        
        # Continue to the next step if requested
        if continue_execution:
            self._execute_step(plan_id, step_index + 1)
        else:
            # Pause execution until user decides to continue or revise
            plan['status'] = 'paused'
            self._emit_status_update(plan_id, {
                'event': 'plan_paused',
                'step_index': step_index,
                'reason': 'User requested pause after step feedback'
            })
    
    def user_confirmation_response(self, command_id, approved, feedback=None):
        """
        Handle user response to a command that required confirmation.
        
        Args:
            command_id (str): The ID of the command
            approved (bool): Whether the user approved the command
            feedback (str, optional): Any user feedback
        """
        # Get the pending command
        command_info = self.pending_commands.get(command_id)
        if not command_info:
            self.logger.log_error(f"Command with ID {command_id} not found")
            return
            
        # Get plan and step
        plan_id = command_info['plan_id']
        step_index = command_info['step_index']
        command = command_info['command']
        
        # Get the plan
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found")
            del self.pending_commands[command_id]
            return
            
        # Get the step
        step = plan['steps'][step_index]
        
        if approved:
            # Execute the command now that it's approved
            del self.pending_commands[command_id]
            self._execute_command_internal(plan_id, step_index, command)
        else:
            # Command was rejected
            step['status'] = 'skipped'
            step['user_feedback'] = feedback if feedback else "Command rejected by user"
            
            # Log the rejection
            self.logger.log_info(f"command_rejected: {{'plan_id': '{plan_id}', 'step_index': {step_index}, 'command': '{command}', 'feedback': '{feedback}'}}")
            
            # Emit status update
            self._emit_status_update(plan_id, {
                'event': 'command_rejected',
                'step_index': step_index,
                'command': command,
                'feedback': feedback
            })
            
            # Remove from pending commands
            del self.pending_commands[command_id]
            
            # Ask for next step - either revise plan or continue
            self._emit_status_update(plan_id, {
                'event': 'command_rejection_options',
                'step_index': step_index,
                'feedback': feedback
            })
    
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
        if 'event' not in update_data:
            update_data['event'] = 'execution_update'
        emit('execution_update', update_data, namespace='/', broadcast=True)

    