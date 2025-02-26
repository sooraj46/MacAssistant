"""
LLM Integration Module
Handles communication with the Gemini LLM API for plan generation and revision.
"""

import asyncio
import os
import json
import logging
import google.genai as genai
import google.genai.types as types # Fixed import
from config import active_config

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
        
        self.plans = {}  # Store generated plans
        
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
        plan_id = str(hash(json.dumps(plan)))
        self.plans[plan_id] = plan
        plan['id'] = plan_id
        
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
        original_plan = self.plans.get(plan_id)
        if not original_plan:
            raise ValueError(f"Plan with ID {plan_id} not found")
        
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
        revised_plan_id = str(hash(json.dumps(revised_plan)))
        self.plans[revised_plan_id] = revised_plan
        revised_plan['id'] = revised_plan_id
        revised_plan['original_plan_id'] = plan_id
        
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
        
    def _parse_plan(self, response):
        """
        Legacy method to parse plans without commands.
        Now forwards to _parse_plan_with_commands.
        
        Args:
            response (str): The LLM response text
            
        Returns:
            dict: A structured plan with steps
        """
        return self._parse_plan_with_commands(response)