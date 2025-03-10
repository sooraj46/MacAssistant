"""
LLM Integration Module
Handles communication with the Gemini LLM API for plan generation and revision.
"""

import asyncio
import os
import json
import logging
import re
import google.genai as genai
import google.genai.types as types # Fixed import
from config import active_config
import tempfile
import shutil

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a single global event loop to be reused
# This prevents Kqueue conflicts on macOS
global_loop = asyncio.new_event_loop()
asyncio.set_event_loop(global_loop)

class LLMIntegration:
    """Class for integrating with Google's Gemini Large Language Model."""
    
    def __init__(self):
        self.api_key = active_config.GEMINI_API_KEY
        self.model = active_config.GEMINI_MODEL
        
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY in configuration.")
        
        self.plans = {}  # In-memory cache of plans
        
        # Create or use plans directory for persistent storage
        self.plans_dir = os.path.join(active_config.LOG_DIR, 'plans')
        os.makedirs(self.plans_dir, exist_ok=True)
        logger.info(f"Using plans directory: {self.plans_dir}")
        
    def generate_plan(self, user_request):
        """
        Generate a plan for a user task using Gemini.
        
        Args:
            user_request (str): The user's request for a task
            
        Returns:
            dict: A plan containing a list of sub-tasks with commands
        """
        # System prompt to instruct the LLM
        system_prompt = """
        You are MacAssistant, an AI that generates executable plans for macOS tasks.

        CAPABILITIES:
        You can generate plans with commands that:
        1. Execute shell commands (ls, grep, find, etc.)
        2. Open applications (using 'open -a AppName')
        3. Manipulate files and directories
        4. Check system information
        5. Work with standard macOS utilities

        INSTRUCTIONS:
        Given a task request, provide a plan with:
        1. A numbered list of steps
        2. For each step, include BOTH a human-readable description AND an executable macOS command
        3. Mark any potentially risky operations with [RISKY] at the beginning of the step
        4. Include verification steps to ensure the task was successful
        5. For steps that require human observation/input, indicate with [OBSERVE] and no command

        FORMAT EACH STEP AS:
        <step number>. <description>
        COMMAND: <shell command or script>

        EXAMPLE PLAN:
        1. Check available disk space
        COMMAND: df -h

        2. Create a new directory for backup files
        COMMAND: mkdir -p ~/backups

        3. [RISKY] Remove old temporary files
        COMMAND: rm -rf ~/tmp/*

        4. [OBSERVE] Verify the backup appears in Finder
        COMMAND: open ~/backups
        """
        
        # Send request to Gemini
        response = self._call_gemini_api(system_prompt, user_request)
        
        # Parse the response to extract the plan with commands
        plan = self._parse_plan_with_commands(response)
        
        # Store the plan
        self._store_plan(plan)
        
        return plan
    
    def revise_plan(self, plan_id, feedback, step_results=None):
        """
        Revise a plan based on user feedback or execution results.
        
        Args:
            plan_id (str): The ID of the plan to revise
            feedback (str): User feedback or execution failure details
            step_results (dict, optional): Results of already executed steps (stdout/stderr)
            
        Returns:
            dict: A revised plan
        """
        # Get the original plan
        original_plan = self.get_plan(plan_id)
        if not original_plan:
            raise ValueError(f"Plan with ID {plan_id} not found")
            
        logger.info(f"Revising plan {plan_id} based on feedback")
        
        # System prompt for plan revision
        system_prompt = """
        You are MacAssistant, an AI that revises executable plans for macOS tasks based on feedback and results.

        CAPABILITIES:
        You can generate plans with commands that:
        1. Execute shell commands (ls, grep, find, etc.)
        2. Open applications (using 'open -a AppName')
        3. Manipulate files and directories
        4. Check system information
        5. Work with standard macOS utilities

        INSTRUCTIONS:
        Given the original plan, execution results, and feedback:
        1. Analyze what went wrong or needs improvement
        2. Create a REVISED plan with numbered steps
        3. For each step, include BOTH a human-readable description AND an executable macOS command
        4. Mark any potentially risky operations with [RISKY] at the beginning of the step
        5. For steps that require human observation, mark with [OBSERVE]
        6. EXPLAIN your changes in a brief summary at the beginning
        
        FORMAT YOUR RESPONSE AS:
        REVISION SUMMARY: <brief explanation of changes made to the plan>
        
        <step number>. <description>
        COMMAND: <shell command or script>
        
        <step number>. <description>
        COMMAND: <shell command or script>
        ...
        """
        
        # Build a detailed user message with plan and results
        user_message = f"ORIGINAL PLAN:\n"
        
        # Format original plan steps with command and any results
        for step in original_plan['steps']:
            status_info = ""
            if step_results and str(step['number']) in step_results:
                result = step_results[str(step['number'])]
                if result.get('stdout'):
                    status_info += f"\nSTDOUT: {result['stdout']}"
                if result.get('stderr'):
                    status_info += f"\nSTDERR: {result['stderr']}"
                if result.get('status'):
                    status_info += f"\nSTATUS: {result['status']}"
                    
            user_message += f"{step['number']}. {step['description']}\n"
            if 'command' in step and step['command']:
                user_message += f"COMMAND: {step['command']}\n"
            if status_info:
                user_message += f"RESULT: {status_info}\n"
            user_message += "\n"
        
        user_message += f"FEEDBACK OR ERROR:\n{feedback}\n\nPlease revise the plan based on this feedback and execution results."
        
        # Send request to Gemini
        response = self._call_gemini_api(system_prompt, user_message)
        logger.info(f"Revised plan response: {response}")
        
        # Parse the response to extract the revised plan
        revised_plan = self._parse_plan_with_commands(response)
        
        # Extract any revision summary
        summary = ""
        if "REVISION SUMMARY:" in response:
            summary_parts = response.split("REVISION SUMMARY:", 1)
            if len(summary_parts) > 1:
                summary_text = summary_parts[1].strip()
                # Take everything up to the first numbered step
                for line in summary_text.split('\n'):
                    if line.strip() and line[0].isdigit() and '.' in line:
                        break
                    summary += line + "\n"
                summary = summary.strip()
                
        # Store the revision summary
        revised_plan['revision_summary'] = summary
                
        # Store the revised plan
        self._store_plan(revised_plan, is_revision=True, original_plan_id=plan_id)
        
        return revised_plan
    
    async def async_call_gemini(self, system_prompt, user_message):
        """
        Call the Gemini API with the given prompts.
        
        Args:
            system_prompt (str): The system prompt
            user_message (str): The user message
            
        Returns:
            str: The response from the API
        """
        try:
            # Combine system prompt and user message for Gemini
            # Gemini doesn't have distinct system/user roles like OpenAI
            combined_prompt = f"{system_prompt}\n\nUser request: {user_message}"
            
            logger.info(f"Sending prompt to Gemini model: {self.model}")

            client = genai.Client(api_key=self.api_key)  # Updated for generativeai

            response = client.models.generate_content(
            model=self.model,
            contents=[types.Part.from_text(text=combined_prompt)],
        )
            
            # Return raw response text
            return response.text
            
        except Exception as e:
            logger.exception(f"Error calling Gemini model: {e}")
            raise Exception(f"API request failed: {str(e)}")
        
    def _call_gemini_api(self, system_prompt, user_message):
        """
        Call the Gemini API with the given prompts synchronously.
        
        Args:
            system_prompt (str): The system prompt
            user_message (str): The user message
            
        Returns:
            str: The response from the API
        """
        # Use the global event loop defined at module level
        # This prevents Kqueue conflicts on macOS by reusing the same loop
        return global_loop.run_until_complete(self.async_call_gemini(system_prompt, user_message))
        
    def verify_execution_result(self, step_description, command, stdout, stderr, success):
        """
        Verify the execution result of a command using the LLM.
        
        Args:
            step_description (str): The description of the step
            command (str): The executed command
            stdout (str): The standard output from the command
            stderr (str): The standard error from the command
            success (bool): Whether the command execution was successful
            
        Returns:
            dict: Analysis result containing success evaluation and explanation
        """
        # System prompt for verification
        system_prompt = """
        You are MacAssistant's verification system. Your job is to analyze command execution results
        and determine if the command achieved its intended purpose.
        
        INSTRUCTIONS:
        1. Analyze the step description, command, stdout, stderr, and return code
        2. Determine if the command succeeded in achieving its purpose
        3. Provide a brief explanation of your reasoning
        4. If the command failed or produced unexpected results, suggest a potential fix
        
        FORMAT YOUR RESPONSE AS JSON:
        {
            "success": true/false,
            "explanation": "Brief explanation of result analysis",
            "suggestion": "Suggested fix or next steps if needed, otherwise empty"
        }
        """
        
        # Build the user message with execution details
        user_message = f"""
        STEP DESCRIPTION: {step_description}
        EXECUTED COMMAND: {command}
        RETURN CODE: {'0 (Success)' if success else 'Non-zero (Failure)'}
        STDOUT: {stdout if stdout else '(No output)'}
        STDERR: {stderr if stderr else '(No error output)'}
        
        Please analyze these results and determine if the command successfully achieved its purpose.
        Return your analysis in the required JSON format.
        """
        
        # Call the LLM for verification
        response = self._call_gemini_api(system_prompt, user_message)
        
        # Parse the JSON response
        try:
            json_match = re.search(r'({[\s\S]*})', response)
            if json_match:
                json_str = json_match.group(1)
                result = json.loads(json_str)
                return result
            else:
                # If no JSON found, create a fallback result
                return {
                    "success": success,  # Fall back to the return code
                    "explanation": "Unable to parse LLM verification response.",
                    "suggestion": "Please check the command output manually."
                }
                
        except Exception as e:
            logger.exception(f"Error parsing verification response: {e}")
            # Return a fallback result based on the command's return code
            return {
                "success": success,
                "explanation": f"Error analyzing results: {str(e)}",
                "suggestion": "Please check the command output manually."
            }
    
    def _parse_plan_with_commands(self, response):
        """
        Parse the LLM response to extract the plan with commands.
        
        Args:
            response (str): The LLM response text
            
        Returns:
            dict: A structured plan with steps and commands
        """
        lines = response.strip().split('\n')
        steps = []
        current_step = None
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Look for numbered steps (1. Step description)
            if line[0].isdigit() and '.' in line:
                # If we were processing a previous step, add it to the list
                if current_step:
                    steps.append(current_step)
                
                step_number, step_text = line.split('.', 1)
                step_text = step_text.strip()
                
                # Check if the step is marked as risky
                is_risky = False
                is_observe = False
                
                if '[RISKY]' in step_text:
                    is_risky = True
                    step_text = step_text.replace('[RISKY]', '').strip()
                
                if '[OBSERVE]' in step_text:
                    is_observe = True
                    step_text = step_text.replace('[OBSERVE]', '').strip()
                
                # Create a new current step
                current_step = {
                    'number': int(step_number),
                    'description': step_text,
                    'is_risky': is_risky,
                    'is_observe': is_observe,
                    'command': '',  # Will be populated when we find the COMMAND: line
                    'status': 'pending'  # Initial status
                }
            
            # Look for command line
            elif line.startswith('COMMAND:') and current_step:
                command = line[8:].strip()  # Remove "COMMAND: " prefix
                
                # Clean up the command - sometimes LLMs include backticks or other formatting
                if command.startswith('`') and command.endswith('`'):
                    command = command[1:-1]
                
                current_step['command'] = command
        
        # Don't forget to add the last step
        if current_step:
            steps.append(current_step)
        
        return {
            'steps': steps,
            'status': 'generated'
        }
        
    def revise_failed_step(self, plan_id, failed_step_index, stdout, stderr):
        """
        Revise a plan when a specific step has failed.
        
        Args:
            plan_id (str): The ID of the plan to revise
            failed_step_index (int): Index of the step that failed
            stdout (str): Standard output from the failed command
            stderr (str): Standard error from the failed command
            
        Returns:
            dict: A revised plan
        """
        # Get the original plan
        original_plan = self.get_plan(plan_id)
        if not original_plan:
            raise ValueError(f"Plan with ID {plan_id} not found")
            
        # Get the failed step
        failed_step = original_plan['steps'][failed_step_index]
        
        # System prompt for plan revision after step failure
        system_prompt = """
        You are MacAssistant, an AI that revises executable plans for macOS tasks when a step fails.

        CAPABILITIES:
        You can generate plans with commands that:
        1. Execute shell commands (ls, grep, find, etc.)
        2. Open applications (using 'open -a AppName')
        3. Manipulate files and directories
        4. Check system information
        5. Work with standard macOS utilities

        INSTRUCTIONS:
        Given the original plan and the failed step details:
        1. Analyze the error and determine what went wrong
        2. Create a REVISED plan that addresses the failure
        3. You can modify the failed step, add more steps before/after it, or completely change the approach
        4. For each step, include BOTH a human-readable description AND an executable macOS command
        5. Mark any potentially risky operations with [RISKY] at the beginning of the step
        6. For steps that require human observation, mark with [OBSERVE]
        7. EXPLAIN your changes in a brief summary at the beginning
        
        FORMAT YOUR RESPONSE AS:
        REVISION SUMMARY: <brief explanation of changes made to the plan>
        
        <step number>. <description>
        COMMAND: <shell command or script>
        
        <step number>. <description>
        COMMAND: <shell command or script>
        ...
        """
        
        # Build a detailed user message with plan and error details
        user_message = "ORIGINAL PLAN:\n"
        
        # Format original plan steps
        for i, step in enumerate(original_plan['steps']):
            prefix = ""
            if i == failed_step_index:
                prefix = "FAILED STEP: "
            
            user_message += f"{prefix}{step['number']}. {step['description']}\n"
            if 'command' in step and step['command']:
                user_message += f"COMMAND: {step['command']}\n"
            
            # Add failure details for the failed step
            if i == failed_step_index:
                user_message += "FAILURE DETAILS:\n"
                if stdout:
                    user_message += f"STDOUT: {stdout}\n"
                if stderr:
                    user_message += f"STDERR: {stderr}\n"
            
            user_message += "\n"
        
        user_message += "Please revise the plan to address the issue with the failed step. The revision should solve the problem and allow the task to be completed successfully."
        
        # Send request to Gemini
        response = self._call_gemini_api(system_prompt, user_message)
        logger.info(f"Revised plan response for failed step: {response}")
        
        # Parse the response to extract the revised plan
        revised_plan = self._parse_plan_with_commands(response)
        
        # Extract any revision summary
        summary = ""
        if "REVISION SUMMARY:" in response:
            summary_parts = response.split("REVISION SUMMARY:", 1)
            if len(summary_parts) > 1:
                summary_text = summary_parts[1].strip()
                # Take everything up to the first numbered step
                for line in summary_text.split('\n'):
                    if line.strip() and line[0].isdigit() and '.' in line:
                        break
                    summary += line + "\n"
                summary = summary.strip()
                
        # Store the revision summary
        revised_plan['revision_summary'] = summary
                
        # Store the revised plan
        self._store_plan(revised_plan, is_revision=True, original_plan_id=plan_id)
        
        return revised_plan
        
    def _store_plan(self, plan, is_revision=False, original_plan_id=None):
        """
        Store a plan both in memory and on disk.
        
        Args:
            plan (dict): The plan to store
            is_revision (bool): Whether this is a revised plan
            original_plan_id (str): The ID of the original plan if this is a revision
            
        Returns:
            str: The plan ID
        """
        # Create a unique ID for the plan
        plan_id = str(hash(json.dumps(plan)))
        plan['id'] = plan_id
        
        # If this is a revision, store the original plan ID
        if is_revision and original_plan_id:
            plan['original_plan_id'] = original_plan_id
        
        # Store in memory cache
        self.plans[plan_id] = plan
        
        # Store to disk
        self._save_plan_to_disk(plan_id, plan)
        
        logger.info(f"{'Revised p' if is_revision else 'P'}lan stored with ID: {plan_id}")
        return plan_id
    
    def _save_plan_to_disk(self, plan_id, plan):
        """
        Save a plan to disk for persistence.
        
        Args:
            plan_id (str): The ID of the plan
            plan (dict): The plan to save
        """
        try:
            plan_path = os.path.join(self.plans_dir, f"{plan_id}.json")
            
            # Write to a temporary file first, then rename for atomicity
            with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
                json.dump(plan, temp_file, indent=2)
                
            # Move temporary file to final location
            shutil.move(temp_file.name, plan_path)
            logger.debug(f"Plan saved to {plan_path}")
            
        except Exception as e:
            logger.error(f"Error saving plan to disk: {e}")
            # Continue execution even if saving fails
    
    def get_plan(self, plan_id):
        """
        Get a plan by ID, checking both memory cache and disk storage.
        
        Args:
            plan_id (str): The ID of the plan to get
            
        Returns:
            dict: The plan, or None if not found
        """
        # Check memory cache first
        plan = self.plans.get(plan_id)
        if plan:
            logger.debug(f"Plan {plan_id} found in memory cache")
            return plan
            
        # If not in memory, try to load from disk
        try:
            plan_path = os.path.join(self.plans_dir, f"{plan_id}.json")
            if os.path.exists(plan_path):
                with open(plan_path, 'r') as f:
                    plan = json.load(f)
                # Update memory cache
                self.plans[plan_id] = plan
                logger.debug(f"Plan {plan_id} loaded from disk")
                return plan
        except Exception as e:
            logger.error(f"Error loading plan from disk: {e}")
            
        # Not found
        logger.warning(f"Plan {plan_id} not found in memory or on disk")
        return None
    
    def summarize_progress_and_update_plan(self, steps_so_far, step_results, remaining_steps):
        """
        1) Summarize the completed steps (including their stdout/stderr).
        2) Potentially update the remaining steps.
        Returns (summary_text, updated_steps)
        """
        # Build a textual summary for the LLM:
        # e.g., for each step in steps_so_far, gather "Step X description, status, output"
        executed_info = []
        for step in steps_so_far:
            n = step.get('number')
            desc = step.get('description', '')
            status = step.get('status', 'unknown')
            
            # Pull from step_results if present
            sr_key = str(n)
            sr = step_results.get(sr_key, {})
            stdout = sr.get('stdout', '')
            stderr = sr.get('stderr', '')
            
            executed_info.append(f"Step {n} ({status}): {desc}\nOutput: {stdout}\nErrors: {stderr}")

        progress_text = "\n".join(executed_info)

        # Also gather info about upcoming steps (remaining_steps)
        upcoming_desc = []
        for st in remaining_steps:
            upcoming_desc.append(f"Step {st['number']}: {st['description']}")

        upcoming_text = "\n".join(upcoming_desc)

        # Prepare prompt
        system_prompt = """
        You are a summarization assistant. Given the history of executed steps and the remaining steps,
        provide two things: 
        1) A short summary of what has been done so far.
        2) Updated or revised steps for the remaining plan if needed.
        
        Return JSON with keys "summary" and "updated_steps".
        "updated_steps" can be an array of step objects like:
        [
        {
            "number": 3,
            "description": "New desc",
            "command": "ls -la"
        },
        ...
        ]
        If no changes are needed to the next steps, just repeat them.
        """

        user_content = f"""
        Executed Steps So Far:
        {progress_text}

        Upcoming Steps:
        {upcoming_text}
        """

        # Call LLM
        response = self._call_gemini_api(system_prompt, user_content)

        # Parse JSON from the response
        import re, json
        match = re.search(r'{[\s\S]*}', response)
        if match:
            try:
                data = json.loads(match.group(0))
                summary = data.get('summary', 'No summary provided.')
                updated_steps = data.get('updated_steps', [])
                return summary, updated_steps
            except:
                pass

        # Fallback
        return "Could not parse summary", remaining_steps