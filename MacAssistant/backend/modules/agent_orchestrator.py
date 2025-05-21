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
            self.logger.log_error(f"Plan with ID {plan_id} not found (returned None by get_plan)")
            print(f"DEBUG: Plan with ID {plan_id} not found (returned None by get_plan)")
            # Emitting status update for UI consistency if plan_id was expected to be valid
            self._emit_status_update(plan_id, { # Use plan_id even if plan is None, so UI knows which request failed
                'event': 'plan_execution_failed',
                'status': 'error', # Explicitly set status
                'steps': [], # No steps to show
                'reason': f"Plan with ID {plan_id} could not be retrieved or loaded."
            })
            return

        # Check if the retrieved plan object itself indicates an error state from generation/parsing
        if plan.get('status') == 'error' or 'error' in plan:
            self.logger.log_error(f"Attempted to execute an invalid or error-state plan with ID {plan_id}. Error: {plan.get('error', 'Unknown error in plan data')}")
            self._emit_status_update(plan_id, {
                'event': 'plan_execution_failed',
                'status': 'error',
                'steps': plan.get('steps', []), # Show steps if available, even in error
                'reason': f"Plan data is invalid or indicates a previous error: {plan.get('error', 'Unknown error in plan data')}"
            })
            return
        
        # Debug output for plan details
        print(f"DEBUG: Plan details: {plan}")
        
        # Update plan status
        plan['status'] = 'executing'
        self.active_plans[plan_id] = plan
        
        # Begin execution of the first step
        self._execute_step(plan_id, 0)

    # --- _execute_step Refactoring Helpers ---
    def _prepare_step_command(self, plan_id, step_index, step):
        """
        Prepares the command for the current step.
        Returns the command string, or None if preparation fails and error handled.
        """
        command = step.get('command')
        if command: # Command already exists in the plan
            print(f"DEBUG: Using command from plan: '{command}'")
            return command

        description = step.get('description', "No description provided.")
        if step.get('is_observe', False): # Observation step, create placeholder command
            print(f"DEBUG: Step is observation: '{description}'")
            command = f"echo 'Observation step: {description}'" 
            step['command'] = command # Store placeholder command back into the step
            return command
        
        # Command is missing for a non-observation step. This is an issue with plan generation.
        self.logger.log_error(f"Command missing for non-observation step in plan {plan_id}, step {step_index}: {description}.")
        self._handle_step_execution_error(plan_id, step_index, f"Command missing for critical non-observation step: {description}")
        return None # Indicate failure to prepare command

    def _check_command_safety_and_proceed(self, plan_id, step_index, step, command):
        """
        Checks command safety and then either calls _execute_command_internal 
        or handles the unsafe command scenario.
        """
        if not self.safety_checker.is_safe(command):
            self.logger.log_error(f"Unsafe command detected: {command}")
            step['status'] = 'blocked' # Update step status
            self._emit_status_update(plan_id, {
                'event': 'unsafe_command_blocked',
                'command': command,
                'step_description': step.get('description', 'N/A')
            })
            # Execution stops here for this step; user intervention is required.
            return
        
        # If safe, proceed to internal execution logic
        self._execute_command_internal(plan_id, step_index, command)
    
    def _execute_step(self, plan_id, step_index):
        """Execute a single step in a plan using helper methods."""
        print(f"DEBUG: Executing step {step_index} of plan {plan_id}")
        try:
            plan = self.active_plans.get(plan_id)
            if not plan:
                self.logger.log_error(f"Plan with ID {plan_id} not found for _execute_step")
                self._emit_status_update(plan_id, {
                    'event': 'plan_execution_error', 'status': 'error',
                    'reason': f"Active plan {plan_id} disappeared during execution."
                })
                return
            
            if step_index >= len(plan.get('steps', [])):
                print(f"DEBUG: All steps completed for plan {plan_id}")
                self._complete_plan(plan_id)
                return
            
            step = plan['steps'][step_index]
            if not isinstance(step, dict):
                self.logger.log_error(f"Step {step_index} in plan {plan_id} is not a valid dictionary. Step data: {step}")
                self._handle_step_execution_error(plan_id, step_index, "Invalid step data encountered.")
                return

            print(f"DEBUG: Current step details: {step}")
            step['status'] = 'executing' # Mark step as executing
            self._emit_status_update(plan_id) # Emit early status update
            
            command = self._prepare_step_command(plan_id, step_index, step)
            if command is None: # Error already handled by _prepare_step_command
                return 
            
            print(f"DEBUG: Final command to execute: '{command}'")
            self._check_command_safety_and_proceed(plan_id, step_index, step, command)

        except KeyError as e:
            self.logger.log_error(f"Missing key in plan/step data during _execute_step for plan {plan_id}, step {step_index}: {str(e)}")
            self._handle_step_execution_error(plan_id, step_index, f"Data integrity issue: missing key {str(e)}")
        except TypeError as e:
            self.logger.log_error(f"Type error in plan/step data during _execute_step for plan {plan_id}, step {step_index}: {str(e)}")
            self._handle_step_execution_error(plan_id, step_index, f"Data integrity issue: type error {str(e)}")
        except Exception as e:
            self.logger.log_critical(f"Unexpected critical error in _execute_step for plan {plan_id}, step {step_index}: {str(e)}")
            self._handle_step_execution_error(plan_id, step_index, f"Unexpected critical error: {str(e)}")

    # --- _execute_command_internal Refactoring Helpers ---
    def _handle_pending_user_confirmation(self, plan_id, step_index, step, command):
        """
        Manages logic for steps requiring user confirmation.
        Returns True if confirmation is pending, False otherwise.
        """
        # Check if the step itself needs confirmation or if the entire plan requires it.
        plan = self.active_plans.get(plan_id, {}) # Get plan or empty dict if not found
        if step.get('needs_user_confirmation', False) or plan.get('human_confirmation_required', False):
            command_id = f"{plan_id}_{step_index}"
            self.pending_commands[command_id] = {
                'plan_id': plan_id, 'step_index': step_index, 'command': command
            }
            step['status'] = 'awaiting_confirmation'
            self._emit_status_update(plan_id, {
                'event': 'user_confirmation_required', 'command_id': command_id,
                'step_index': step_index, 'command': command, 
                'description': step.get('description', 'N/A')
            })
            return True # Confirmation is pending
        return False # No confirmation needed

    def _perform_and_log_execution(self, command):
        """Wraps command execution and its try-except block."""
        try:
            success, stdout, stderr = self.execution_engine.execute(command)
        except Exception as e:
            self.logger.log_error(f"Exception during command execution: {command}. Error: {str(e)}")
            return False, "", f"Command execution failed with an internal error: {str(e)}"
        return success, stdout, stderr

    def _verify_step_execution_with_llm(self, step, command, success, stdout, stderr):
        """
        Calls LLM for verification and handles its response.
        Returns (verification_result_dict, llm_verified_success_bool).
        """
        verification_result = self.llm_integration.verify_execution_result(
            step.get('description', 'N/A'), command, stdout, stderr, success
        )
        
        llm_verified_success = success # Default to raw command success
        if 'error' in verification_result: # LLM verification itself had an error
            self.logger.log_error(f"LLM verification failed for command '{command}': {verification_result['error']}")
            # Fallback to raw command success; error from verification_result is logged.
        else: # LLM verification successful, use its opinion
            llm_verified_success = verification_result.get('success', success)
            
        return verification_result, llm_verified_success

    def _process_successful_step(self, plan_id, step_index, step, stdout, stderr, verification_result):
        """Handles all actions for a successfully completed step."""
        plan = self.active_plans.get(plan_id)
        if not plan: return 

        step.update({
            'status': 'completed', 'stdout': stdout, 'stderr': stderr, 
            'verification': verification_result
        })
        self.logger.log_command_success(plan_id, step_index, stdout, stderr)
        
        if 'step_results' not in plan: plan['step_results'] = {}
        plan['step_results'][str(step.get('number'))] = {
            'status': 'completed', 'stdout': stdout, 'stderr': stderr, 
            'verification': verification_result
        }
        
        self._emit_status_update(plan_id, {
            'event': 'step_completed', 'step_index': step_index,
            'stdout': stdout, 'stderr': stderr, 'verification': verification_result
        })
        self._emit_status_update(plan_id, {
            'event': 'step_completed_feedback', 'step_index': step_index,
            'description': step.get('description', 'N/A'), 'stdout': stdout,
            'explanation': verification_result.get('explanation', '') if 'error' not in verification_result else 'Could not get LLM explanation.',
            'continue_automatically': not active_config.HUMAN_VALIDATION_REQUIRED
        })

        self._summarize_and_update_plan(plan_id, step_index)
        
        if active_config.HUMAN_VALIDATION_REQUIRED: return
        if step.get('is_observe', False):
            self._emit_status_update(plan_id, {
                'event': 'observation_required', 'step_index': step_index,
                'description': step.get('description', 'N/A'), 'stdout': stdout
            })
            return
        self._execute_step(plan_id, step_index + 1)

    def _process_failed_step(self, plan_id, step_index, step, stdout, stderr, verification_result):
        """Handles all actions for a failed step."""
        plan = self.active_plans.get(plan_id)
        if not plan: return

        step.update({
            'status': 'failed', 'stdout': stdout, 'stderr': stderr,
            'verification': verification_result
        })
        self.logger.log_command_failure(plan_id, step_index, stdout, stderr)

        if 'step_results' not in plan: plan['step_results'] = {}
        plan['step_results'][str(step.get('number'))] = {
            'status': 'failed', 'stdout': stdout, 'stderr': stderr,
            'verification': verification_result
        }
        
        self._emit_status_update(plan_id, {
            'event': 'step_failed', 'step_index': step_index,
            'stdout': stdout, 'stderr': stderr, 'verification': verification_result
        })
        self._emit_status_update(plan_id, {
            'event': 'step_failure_options', 'step_index': step_index,
            'verification': verification_result,
            'suggestion': verification_result.get('suggestion', '') if 'error' not in verification_result else 'Could not get LLM suggestion.'
        })
    
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
        """Internal method to execute a command using helper methods."""
        plan = self.active_plans.get(plan_id)
        if not plan:
            self.logger.log_error(f"Plan with ID {plan_id} not found for _execute_command_internal")
            return
        
        # Ensure step is valid before proceeding
        if not (0 <= step_index < len(plan.get('steps', [])) and isinstance(plan['steps'][step_index], dict)):
            self.logger.log_error(f"Invalid step at index {step_index} for plan {plan_id} in _execute_command_internal.")
            self._handle_step_execution_error(plan_id, step_index, "Invalid step data encountered before command execution.")
            return
        step = plan['steps'][step_index]

        print(f"DEBUG: Executing step: {step.get('description', 'N/A')}")
        print(f"DEBUG: Generated command: {command}")
        self.logger.log_command_execution(plan_id, step_index, command)
        
        if self._handle_pending_user_confirmation(plan_id, step_index, step, command):
            return # Execution pauses if confirmation is pending

        success, stdout, stderr = self._perform_and_log_execution(command)
        
        # If _perform_and_log_execution itself led to an internal error, 'success' will be False
        # and 'stderr' will contain the internal error message.
        # The step status might have been set to 'failed' already if an exception occurred there.
        # This check is to ensure we handle it correctly if the step status was set by the exception.
        if not success and "Command execution failed with an internal error" in stderr:
            # The _perform_and_log_execution already logged the core error.
            # We need to ensure the step reflects this failure and the orchestrator stops or processes failure.
            step['status'] = 'failed' # Ensure it's marked
            # The verification_result will be based on this failure.
            # Fall through to _verify_step_execution_with_llm, which will get success=False.
            pass


        print(f"DEBUG: Command execution success: {success}")
        print(f"DEBUG: stdout: {stdout}")
        print(f"DEBUG: stderr: {stderr}")
        
        verification_result, llm_verified_success = self._verify_step_execution_with_llm(step, command, success, stdout, stderr)
        
        if llm_verified_success:
            self._process_successful_step(plan_id, step_index, step, stdout, stderr, verification_result)
        else:
            # Preserve original stderr from command execution if LLM verification failed internally
            effective_stderr = stderr
            if 'error' in verification_result and not stderr: # If command had no stderr, but verification failed
                effective_stderr = f"LLM Verification Error: {verification_result.get('error', 'Unknown verification error')}"
            self._process_failed_step(plan_id, step_index, step, stdout, effective_stderr, verification_result)
    
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
        summary_text, updated_steps_list = self.llm_integration.summarize_progress_and_update_plan(steps_so_far, step_results, remaining_steps)

        # Check if summarize_progress_and_update_plan itself had an issue (e.g. returned its own error structure)
        # Assuming it returns a tuple (summary_string, steps_list_or_error_dict)
        # For now, the current llm_integration.summarize_progress_and_update_plan returns (summary_text, steps_list)
        # where summary_text can indicate an error.
        if "Could not parse summary" in summary_text and not updated_steps_list: # Heuristic for error
             self.logger.log_error(f"Failed to summarize and update plan {plan_id}. LLM summary: {summary_text}")
             # Potentially emit an event that summarization failed, but don't alter the plan.
             self._emit_status_update(plan_id, {
                'event': 'progress_summarization_failed',
                'summary': summary_text
             })
             return

        # Store the summary in the plan if you like
        plan['progress_summary'] = summary_text

        # If updated_steps is not None and not an error indicator, it means the LLM is giving new instructions
        if updated_steps_list: # updated_steps_list should be a list of step dicts
            # Overwrite the plan’s next steps
            new_plan_steps = plan['steps'][:completed_step_index + 1] + updated_steps_list
            plan['steps'] = new_plan_steps

        # Optionally emit a status update so the UI can see the new plan
        self._emit_status_update(plan_id, {
            'event': 'progress_summarized',
            'summary': summary_text,
            'updated_steps': updated_steps_list # Send the actual list received
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
        revised_plan_data = self.llm_integration.revise_plan(plan_id, feedback, step_results)
        
        if 'error' in revised_plan_data or not revised_plan_data.get('id'):
            self.logger.log_error(f"Plan revision failed for plan {plan_id}. Error: {revised_plan_data.get('error', 'Unknown revision error')}")
            # Restore original plan status if it was 'revising'
            plan['status'] = 'execution_halted_awaiting_revision_failure' # Or some other appropriate status
            self._emit_status_update(plan_id, {
                'event': 'plan_revision_failed',
                'original_plan_id': plan_id,
                'error': revised_plan_data.get('error', 'Unknown revision error')
            })
            return None # Indicate revision failure

        # Remove the old plan from active plans
        # (Only if the new plan ID is different, though revise_plan typically creates a new ID)
        if plan_id in self.active_plans: # Check if it wasn't already removed or replaced
             del self.active_plans[plan_id]
        
        # Add the revised plan
        self.active_plans[revised_plan_data['id']] = revised_plan_data
        
        # Include the revision summary in the update
        revision_summary = revised_plan_data.get('revision_summary', 'Plan was revised')
        
        # Emit status update
        self._emit_status_update(revised_plan_data['id'], {
            'event': 'plan_revised',
            'original_plan_id': plan_id,
            'revised_plan_id': revised_plan_data['id'],
            'is_auto_revision': auto_revision,
            'revision_summary': revision_summary
        })
        
        return revised_plan_data
    
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
    
    def _handle_step_execution_error(self, plan_id, step_index, error_message):
        """Helper to manage step failure due to internal errors."""
        plan = self.active_plans.get(plan_id)
        if plan and 0 <= step_index < len(plan.get('steps',[])):
            step = plan['steps'][step_index]
            if isinstance(step, dict): # Ensure step is a dict before updating
                step['status'] = 'failed'
                step['stderr'] = error_message
        
        self.logger.log_error(f"Step execution error for plan {plan_id}, step {step_index}: {error_message}")
        self._emit_status_update(plan_id, {
            'event': 'step_failed', # Use existing event if suitable
            'status': 'error', # Indicate plan might be in error
            'step_index': step_index,
            'reason': error_message,
            'stderr': error_message # Make it clear in UI
        })
        # Consider if plan status should also be 'error' or 'execution_halted'
        if plan:
            plan['status'] = 'error' # Mark plan as errored
            self._emit_status_update(plan_id) # Emit overall plan status update


    def _emit_status_update(self, plan_id, additional_data=None):
        """
        Emit a status update for the given plan.
        
        Args:
            plan_id (str): The ID of the plan
            additional_data (dict, optional): Additional data to include in the update
        """
        # Get the plan
        plan = self.active_plans.get(plan_id)
        
        update_data = {
            'plan_id': plan_id,
            'timestamp': time.time()
        }

        if not plan:
            # If plan is not found (e.g., after an error leading to its removal, or if plan_id is stale)
            # still send a minimal update if additional_data specifies an event.
            update_data['status'] = 'error'
            update_data['reason'] = f"Plan with ID {plan_id} not found or no longer active."
            update_data['steps'] = []
            if additional_data:
                update_data.update(additional_data)
            else: # If no additional data, there's not much to send other than plan not found.
                 # This case might be hit if _emit_status_update is called with a bad plan_id and no extra info.
                return # Or log an error: self.logger.log_warning(f"Attempted to emit status for non-existent plan {plan_id}")
        else:
            # Plan exists, prepare full update data
            update_data['status'] = plan.get('status', 'unknown') # Use .get for safety
            update_data['steps'] = plan.get('steps', []) # Use .get for safety
        
            if additional_data:
                update_data.update(additional_data)
        
        try:
            # Emit the update
            emit('execution_update', update_data, namespace='/', broadcast=True)
        except Exception as e:
            self.logger.log_error(f"Failed to emit SocketIO status update for plan {plan_id}: {str(e)}")

    