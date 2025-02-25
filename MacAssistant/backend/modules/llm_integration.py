"""
LLM Integration Module
Handles communication with the Gemini LLM API for plan generation and revision.
"""

import os
import json
import logging
import google.genai as genai
import google.genai.types as types
from config import active_config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMIntegration:
    """Class for integrating with Google's Gemini Large Language Model."""
    
    def __init__(self):
        self.api_key = active_config.GEMINI_API_KEY
        self.model = active_config.GEMINI_MODEL
        
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY in configuration.")
        
        self.client = genai.Client(api_key=self.api_key)
        self.plans = {}  # Store generated plans
        
    def generate_plan(self, user_request):
        """
        Generate a plan for a user task using Gemini.
        
        Args:
            user_request (str): The user's request for a task
            
        Returns:
            dict: A plan containing a list of sub-tasks
        """
        # System prompt to instruct the LLM
        system_prompt = """
        You are a helpful assistant that generates plans for macOS tasks. Given a task request, 
        create a plan with a list of numbered sub-tasks needed to accomplish the goal. Mark any 
        potentially risky operations with [RISKY] at the beginning of the step. Ensure each step 
        is clear, concise, and executable on macOS. Return the plan as a list of steps.
        """
        
        # Send request to Gemini
        response = self._call_gemini_api(system_prompt, user_request)
        
        # Parse the response to extract the plan
        plan = self._parse_plan(response)
        
        # Store the plan
        plan_id = str(hash(json.dumps(plan)))
        self.plans[plan_id] = plan
        plan['id'] = plan_id
        
        return plan
    
    def revise_plan(self, plan_id, feedback):
        """
        Revise a plan based on user feedback or execution failures.
        
        Args:
            plan_id (str): The ID of the plan to revise
            feedback (str): User feedback or execution failure details
            
        Returns:
            dict: A revised plan
        """
        # Get the original plan
        original_plan = self.plans.get(plan_id)
        if not original_plan:
            raise ValueError(f"Plan with ID {plan_id} not found")
        
        # System prompt for plan revision
        system_prompt = """
        You are a helpful assistant that revises plans for macOS tasks. Given an original plan 
        and feedback or error details, create a revised plan with a list of numbered sub-tasks. 
        Mark any potentially risky operations with [RISKY] at the beginning of the step. Ensure 
        each step is clear, concise, and executable on macOS. Return the revised plan as a list 
        of steps.
        """
        
        # User message with original plan and feedback
        user_message = f"""
        ORIGINAL PLAN:
        {json.dumps(original_plan['steps'])}
        
        FEEDBACK OR ERROR:
        {feedback}
        
        Please revise the plan based on this feedback.
        """
        
        # Send request to Gemini
        response = self._call_gemini_api(system_prompt, user_message)
        
        # Parse the response to extract the revised plan
        revised_plan = self._parse_plan(response)
        
        # Store the revised plan
        revised_plan_id = str(hash(json.dumps(revised_plan)))
        self.plans[revised_plan_id] = revised_plan
        revised_plan['id'] = revised_plan_id
        revised_plan['original_plan_id'] = plan_id
        
        return revised_plan
    
    def _call_gemini_api(self, system_prompt, user_message):
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
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[types.Part.from_text(text=combined_prompt)],
            )
            
            # Return raw response text
            return response.text
            
        except Exception as e:
            logger.exception(f"Error calling Gemini model: {e}")
            raise Exception(f"API request failed: {str(e)}")
    
    def _parse_plan(self, response):
        """
        Parse the LLM response to extract the plan.
        
        Args:
            response (str): The LLM response text
            
        Returns:
            dict: A structured plan with steps
        """
        lines = response.strip().split('\n')
        steps = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
                
            # Look for numbered steps (1. Step description)
            if line[0].isdigit() and '.' in line:
                step_number, step_text = line.split('.', 1)
                step_text = step_text.strip()
                
                # Check if the step is marked as risky
                is_risky = False
                if step_text.startswith('[RISKY]'):
                    is_risky = True
                    step_text = step_text[7:].strip()  # Remove the [RISKY] tag
                
                steps.append({
                    'number': int(step_number),
                    'description': step_text,
                    'is_risky': is_risky,
                    'status': 'pending'  # Initial status
                })
        
        return {
            'steps': steps,
            'status': 'generated'
        }