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
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create a single global event loop to be reused
# global_loop and its management strategy:
# The `global_loop` is a single asyncio event loop created when this module is loaded.
# `asyncio.set_event_loop(global_loop)` sets this loop as the default for the current (main) thread.
# The primary purpose of this setup was to mitigate "Kqueue kqueue(2) error" issues on macOS
# when running asyncio code (like Google's genai library calls) within a threaded environment
# such as a Flask development server. These errors often arise from complexities in managing
# multiple event loops or loop lifecycles across threads, or interactions with macOS's kqueue mechanism.
#
# Original approach: `global_loop.run_until_complete()` was called directly in methods like `_call_gemini_api`.
# While this might have stabilized Kqueue issues by reusing a single loop, it made the async Gemini
# calls blocking from the perspective of the Flask request handler thread.
#
# Current approach (with ThreadPoolExecutor):
# The `_call_gemini_api` method now submits `global_loop.run_until_complete(self.async_call_gemini(...))`
# to a `concurrent.futures.ThreadPoolExecutor`. This means:
# 1. The actual execution of `run_until_complete` (and thus the Gemini API call) happens in a
#    worker thread from the pool, not directly in the Flask request thread.
# 2. The Flask request thread calls `future.result(timeout=...)`, which blocks *that specific request thread*
#    until the Gemini call completes in the worker thread (or times out), but it allows other Flask request threads
#    (if the server is multi-threaded) to handle other incoming requests concurrently.
# 3. This isolates the `global_loop`'s activity to designated worker threads, which is hoped
#    to maintain the Kqueue stability while allowing better concurrency for LLM operations.
#
# The `genai` library internally uses `asyncio.get_event_loop()` if its async methods are called
# without an active loop. By calling `async_call_gemini` via `global_loop.run_until_complete`,
# `global_loop` becomes the active loop during that execution within the worker thread.
#
# Retaining `asyncio.set_event_loop(global_loop)` in the main thread ensures that if any part of `genai`
# (or other asyncio-dependent libraries) performs initialization that captures the default loop
# when this module is imported, it captures `global_loop`. This is a defensive measure to ensure
# consistent loop context for libraries that might expect `asyncio.get_event_loop()` to return
# a specific loop if called during import time or from the main thread.
global_loop = asyncio.new_event_loop()
asyncio.set_event_loop(global_loop)


class LRUCache:
    """
    A simple Least Recently Used (LRU) Cache implementation using collections.OrderedDict.
    """
    def __init__(self, max_size=128):
        self.cache = OrderedDict()
        self.max_size = max_size

    def get(self, key):
        """
        Retrieves an item from the cache. Marks it as recently used.
        Returns the item if key exists, otherwise None.
        """
        if key not in self.cache:
            return None
        # Move the accessed item to the end to mark it as recently used
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key, value):
        """
        Adds an item to the cache. If the cache is full, evicts the least recently used item.
        """
        if key in self.cache:
            # Move existing item to end if it's updated, to mark as recently used
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.max_size:
            # Pop the first item (least recently used)
            self.cache.popitem(last=False)

    def __contains__(self, key):
        """
        Checks if a key is in the cache.
        """
        return key in self.cache

    def __len__(self):
        return len(self.cache)


class LLMIntegration:
    """Class for integrating with Google's Gemini Large Language Model."""
    
    def __init__(self):
        self.api_key = active_config.GEMINI_API_KEY
        self.model = active_config.GEMINI_MODEL
        
        if not self.api_key:
            raise ValueError("Missing GEMINI_API_KEY in configuration.")

        # Initialize ThreadPoolExecutor
        # The number of workers can be made configurable, e.g., via active_config.LLM_MAX_WORKERS
        self.executor = ThreadPoolExecutor(max_workers=getattr(active_config, 'LLM_MAX_WORKERS', 4))
        logger.info(f"Initialized ThreadPoolExecutor with max_workers={self.executor._max_workers} for LLMIntegration")
        
        # Initialize LRU cache for plans
        # Default to 128 if PLAN_CACHE_SIZE is not in config, though it should be.
        cache_size = getattr(active_config, 'PLAN_CACHE_SIZE', 128) 
        self.plans_cache = LRUCache(max_size=cache_size)
        logger.info(f"Initialized LRU plan cache with max size: {cache_size}")
        
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
        Given a task request, provide a plan as a single JSON object.
        The JSON object should have a key "plan" which is a list of step objects.
        Each step object must contain:
        - "number" (int): The step number.
        - "description" (str): The human-readable description of the step.
        - "command" (str, optional): The executable macOS command. Omit or set to null if not applicable (e.g., for observation steps).
        - "is_risky" (bool): True if the step involves a risky operation (e.g., deleting files, modifying system settings).
        - "is_observe" (bool): True if the step requires human observation or input.

        EXAMPLE JSON RESPONSE:
        {
          "plan": [
            {
              "number": 1,
              "description": "Check available disk space",
              "command": "df -h",
              "is_risky": false,
              "is_observe": false
            },
            {
              "number": 2,
              "description": "Create a new directory for backup files",
              "command": "mkdir -p ~/backups",
              "is_risky": false,
              "is_observe": false
            },
            {
              "number": 3,
              "description": "Remove old temporary files",
              "command": "rm -rf ~/tmp/*",
              "is_risky": true,
              "is_observe": false
            },
            {
              "number": 4,
              "description": "Verify the backup appears in Finder",
              "command": "open ~/backups",
              "is_risky": false,
              "is_observe": true
            }
          ]
        }
        """
        
        # Send request to Gemini
        response_text = self._call_gemini_api(system_prompt, user_request)
        
        # Parse the response to extract the plan with commands
        plan_data = self._parse_plan_with_commands(response_text) 
        
        if 'error' in plan_data:
            logger.error(f"Failed to generate plan: {plan_data['error']}")
            return {'id': None, 'steps': [], 'status': 'error', 'error': plan_data['error']}

        self._store_plan(plan_data)
        
        return plan_data
    
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
        1. Analyze what went wrong or needs improvement.
        2. Create a REVISED plan as a single JSON object.
        3. The JSON object must have a "revision_summary" (str) key explaining the changes,
           and a "plan" key, which is a list of step objects.
        4. Each step object must contain:
           - "number" (int): The step number.
           - "description" (str): The human-readable description of the step.
           - "command" (str, optional): The executable macOS command. Omit or set to null if not applicable.
           - "is_risky" (bool): True if the step involves a risky operation.
           - "is_observe" (bool): True if the step requires human observation.

        EXAMPLE JSON RESPONSE:
        {
          "revision_summary": "The previous command for listing files was incorrect. This version uses 'ls -la'.",
          "plan": [
            {
              "number": 1,
              "description": "List files in the current directory with details.",
              "command": "ls -la",
              "is_risky": false,
              "is_observe": false
            },
            {
              "number": 2,
              "description": "Verify the output.",
              "command": null,
              "is_risky": false,
              "is_observe": true
            }
          ]
        }
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
        response_text = self._call_gemini_api(system_prompt, user_message)
        logger.info(f"Revised plan response: {response_text}")
        
        # Parse the response to extract the revised plan
        parsed_data = self._parse_plan_with_commands(response_text, is_revision=True)

        if 'error' in parsed_data:
            logger.error(f"Failed to revise plan: {parsed_data['error']}")
            return {'id': None, 'steps': [], 'status': 'error', 'error': parsed_data['error'], 'revision_summary': ''}
        
        self._store_plan(parsed_data, is_revision=True, original_plan_id=plan_id)
        
        return parsed_data
    
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
        # Use the global event loop defined at module level, but run it in the executor.
        # This isolates the event loop's execution from the main Flask thread,
        # aiming to prevent Kqueue conflicts on macOS and improve concurrency.
        future = self.executor.submit(global_loop.run_until_complete, self.async_call_gemini(system_prompt, user_message))
        try:
            # Configurable timeout for the LLM call.
            timeout = getattr(active_config, 'LLM_TIMEOUT', 60) 
            return future.result(timeout=timeout) 
        except TimeoutError as e:
            logger.error(f"Timeout waiting for Gemini API call ({timeout}s): {e}")
            # Upstream code should be prepared to handle this.
            # Consider returning a specific error structure or raising a custom timeout error.
            raise TimeoutError(f"Gemini API call timed out after {timeout} seconds.") from e
        except Exception as e:
            logger.exception(f"Error getting result from executor for Gemini API call: {e}")
            # Propagate the error. Upstream code should handle it.
            raise Exception(f"Gemini API call via executor failed: {str(e)}") from e
        
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
        raw_response_snippet = response[:200] # For logging

        try:
            # Attempt to find JSON block if LLM wraps it in markdown or directly
            json_str = None
            match_markdown = re.search(r'```json\s*([\s\S]*?)\s*```', response)
            if match_markdown:
                json_str = match_markdown.group(1)
            else:
                # Fallback: try to find JSON object directly if no markdown block
                match_direct_json = re.search(r'{\s*".*?":[\s\S]*}', response)
                if match_direct_json:
                    json_str = match_direct_json.group(0)
            
            if not json_str:
                logger.error(f"No JSON block found in LLM verification response. Snippet: {raw_response_snippet}")
                return {
                    "success": success,  # Fall back to the command's success status
                    "explanation": "Unable to parse LLM verification response: No JSON block found.",
                    "suggestion": "Please check the command output manually.",
                    "error_code": "NO_JSON_FOUND"
                }

            try:
                parsed_json = json.loads(json_str)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed for verification response: {e}. Snippet: {raw_response_snippet}. JSON string used: {json_str[:200]}")
                return {
                    "success": success, # Fall back
                    "explanation": f"JSON parsing failed for verification response: {str(e)}",
                    "suggestion": "Please check the command output manually.",
                    "error_code": "PARSING_FAILED"
                }

            # Validate structure
            if not isinstance(parsed_json, dict) or \
               'success' not in parsed_json or \
               'explanation' not in parsed_json:
                logger.error(f"Invalid structure in LLM verification response. Missing 'success' or 'explanation'. Parsed: {parsed_json}. Snippet: {raw_response_snippet}")
                return {
                    "success": success, # Fall back
                    "explanation": "Invalid structure in LLM verification response. Missing 'success' or 'explanation'.",
                    "suggestion": "Please check the command output manually.",
                    "error_code": "VALIDATION_FAILED"
                }
            
            # Ensure 'suggestion' key exists, even if it's None or empty, for consistent access
            if 'suggestion' not in parsed_json:
                parsed_json['suggestion'] = "" # Default to empty string if missing

            return parsed_json # Contains success, explanation, suggestion
                
        except Exception as e: # Catch-all for unexpected errors during parsing logic
            logger.exception(f"Unexpected error parsing verification response: {e}. Snippet: {raw_response_snippet}")
            return {
                "success": success, # Fall back
                "explanation": f"Unexpected error analyzing results: {str(e)}",
                "suggestion": "Please check the command output manually.",
                "error_code": "UNKNOWN_PARSING_ERROR"
            }
    
    def _parse_plan_with_commands(self, response_text, is_revision=False):
        """
        Parse the LLM JSON response to extract the plan with commands.
        
        Args:
            response_text (str): The LLM response text, expected to be JSON.
            is_revision (bool): True if parsing a response for a revision, expecting "revision_summary".
            
        Returns:
            dict: A structured plan (internal format) or an error dictionary.
        """
        raw_response_snippet = response_text[:200] # For logging

        try:
            # Attempt to find JSON block if LLM wraps it in markdown
            match_markdown = re.search(r'```json\s*([\s\S]*?)\s*```', response_text)
            if match_markdown:
                json_str = match_markdown.group(1)
            else:
                # Fallback: try to find JSON object directly if no markdown block
                # This is a more general regex for a JSON object
                match_direct_json = re.search(r'{\s*".*?":[\s\S]*}', response_text)
                if match_direct_json:
                    json_str = match_direct_json.group(0)
                else:
                    json_str = response_text # Assume the whole response is JSON if no specific block found

            try:
                parsed_json = json.loads(json_str)
            except json.JSONDecodeError as e:
                # Try to clean up common issues like trailing commas (requires more sophisticated parsing)
                # For now, we log and return a structured error.
                # A more advanced approach could involve a library that handles lenient JSON.
                logger.error(f"Initial JSON parsing failed: {e}. Snippet: {raw_response_snippet}")
                # Attempt to strip leading/trailing non-JSON characters if any
                # This is a simple attempt, more complex cleaning might be needed
                cleaned_json_str = json_str.strip()
                if not (cleaned_json_str.startswith('{') and cleaned_json_str.endswith('}')) and \
                   not (cleaned_json_str.startswith('[') and cleaned_json_str.endswith(']')):
                     # If it doesn't look like a JSON object/array after stripping, it's unlikely to parse
                    logger.error(f"JSON parsing failed after stripping: {e}. Original snippet: {raw_response_snippet}")
                    return {
                        'id': None, 
                        'error_code': 'PARSING_FAILED',
                        'message': f"JSON decoding error: {str(e)}", 
                        'raw_response_snippet': raw_response_snippet,
                        'steps': [], 
                        'status': 'error'
                    }
                try:
                    parsed_json = json.loads(cleaned_json_str)
                except json.JSONDecodeError as final_e:
                    logger.error(f"JSON parsing failed even after basic cleaning: {final_e}. Snippet: {raw_response_snippet}")
                    return {
                        'id': None,
                        'error_code': 'PARSING_FAILED',
                        'message': f"JSON decoding error after cleaning: {str(final_e)}",
                        'raw_response_snippet': raw_response_snippet,
                        'steps': [],
                        'status': 'error'
                    }

            # --- Structural Validation ---
            if not isinstance(parsed_json, dict):
                logger.error(f"Invalid plan format: Root is not a JSON object. Snippet: {raw_response_snippet}")
                return {
                    'id': None,
                    'error_code': 'VALIDATION_FAILED',
                    'message': "Invalid plan format: Root is not a JSON object.",
                    'raw_response_snippet': raw_response_snippet,
                    'steps': [],
                    'status': 'error'
                }

            raw_steps = parsed_json.get('plan')
            if not isinstance(raw_steps, list):
                logger.error(f"Invalid plan format: 'plan' key is missing or not a list. Snippet: {raw_response_snippet}")
                return {
                    'id': None, 
                    'error_code': 'VALIDATION_FAILED',
                    'message': "Invalid plan format: 'plan' key is missing or not a list.", 
                    'raw_response_snippet': raw_response_snippet,
                    'steps': [], 
                    'status': 'error'
                }

            internal_steps = []
            for i, step_data in enumerate(raw_steps):
                if not isinstance(step_data, dict):
                    logger.warning(f"Skipping invalid step data (not a dict) at index {i}: {step_data}. Snippet: {raw_response_snippet}")
                    # Depending on strictness, you might want to return an error here
                    continue 

                # Validate essential keys
                essential_keys = ['number', 'description', 'command', 'is_risky', 'is_observe']
                missing_keys = [key for key in essential_keys if key not in step_data]
                if any(key not in step_data for key in ['number', 'description']): # number and description are critical
                    logger.error(f"Invalid step structure at index {i}: Missing critical keys ('number', 'description'). Step data: {step_data}. Snippet: {raw_response_snippet}")
                    return {
                        'id': None,
                        'error_code': 'VALIDATION_FAILED',
                        'message': f"Invalid step structure at index {i}: Missing critical keys ('number', 'description'). Found: {list(step_data.keys())}",
                        'raw_response_snippet': raw_response_snippet,
                        'steps': [],
                        'status': 'error'
                    }

                command = step_data.get('command') # Allow command to be None or empty string
                if command and isinstance(command, str):
                    command = command.strip()
                    if command.startswith('`') and command.endswith('`') and len(command) > 1: # Avoid stripping if command is just '`'
                        command = command[1:-1].strip()
                elif command is None: 
                    command = "" # Standardize to empty string if command is None
                elif not isinstance(command, str): # Command must be string or None
                    logger.warning(f"Invalid command type for step {step_data.get('number', i)}: {type(command)}. Setting to empty. Snippet: {raw_response_snippet}")
                    command = ""


                internal_steps.append({
                    'number': step_data.get('number'),
                    'description': step_data.get('description', 'No description provided.'),
                    'command': command,
                    'is_risky': step_data.get('is_risky', False) if isinstance(step_data.get('is_risky'), bool) else False,
                    'is_observe': step_data.get('is_observe', False) if isinstance(step_data.get('is_observe'), bool) else False,
                    'status': 'pending'
                })
            
            plan_id = str(hash(json.dumps(internal_steps))) 

            plan_output = {
                'id': plan_id,
                'steps': internal_steps,
                'status': 'generated'
            }

            if is_revision:
                revision_summary = parsed_json.get('revision_summary', '')
                if not isinstance(revision_summary, str):
                    logger.warning(f"Revision summary is not a string. Defaulting to empty. Snippet: {raw_response_snippet}")
                    revision_summary = 'Revision summary was not a string or was missing.'
                plan_output['revision_summary'] = revision_summary
            
            return plan_output

        except json.JSONDecodeError as e: # Should be caught by inner try-except, but as a fallback
            logger.error(f"Outer JSON parsing failed: {e}. Snippet: {raw_response_snippet}")
            return {
                'id': None, 
                'error_code': 'PARSING_FAILED_UNEXPECTED',
                'message': f"Unexpected JSON decoding error: {str(e)}", 
                'raw_response_snippet': raw_response_snippet,
                'steps': [], 
                'status': 'error'
            }
        except TypeError as e: 
            logger.error(f"Type error during plan parsing: {e}. Snippet: {raw_response_snippet}")
            return {
                'id': None, 
                'error_code': 'TYPE_ERROR',
                'message': f"Type error during plan parsing: {str(e)}", 
                'raw_response_snippet': raw_response_snippet,
                'steps': [], 
                'status': 'error'
            }
        except Exception as e: 
            logger.error(f"Unexpected error parsing plan: {e}. Snippet: {raw_response_snippet}")
            return {
                'id': None, 
                'error_code': 'UNKNOWN_PARSING_ERROR',
                'message': f"Unexpected error parsing plan: {str(e)}", 
                'raw_response_snippet': raw_response_snippet,
                'steps': [], 
                'status': 'error'
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
        1. Analyze the error and determine what went wrong.
        2. Create a REVISED plan as a single JSON object that addresses the failure.
        3. The JSON object must have a "revision_summary" (str) key explaining the changes,
           and a "plan" key, which is a list of step objects.
        4. You can modify the failed step, add more steps before/after it, or completely change the approach.
        5. Each step object must contain:
           - "number" (int): The step number.
           - "description" (str): The human-readable description of the step.
           - "command" (str, optional): The executable macOS command. Omit or set to null if not applicable.
           - "is_risky" (bool): True if the step involves a risky operation.
           - "is_observe" (bool): True if the step requires human observation.
        6. Ensure the "revision_summary" clearly explains the reasoning for the changes.

        EXAMPLE JSON RESPONSE:
        {
          "revision_summary": "The 'mkdir' command failed because the directory already existed. Added a check first.",
          "plan": [
            {
              "number": 1,
              "description": "Check if directory '~/test_dir' exists",
              "command": "test -d ~/test_dir",
              "is_risky": false,
              "is_observe": false
            },
            {
              "number": 2,
              "description": "Create directory '~/test_dir' only if it doesn't exist",
              "command": "if [ $? -ne 0 ]; then mkdir ~/test_dir; fi",
              "is_risky": false,
              "is_observe": false
            }
          ]
        }
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
        response_text = self._call_gemini_api(system_prompt, user_message)
        logger.info(f"Revised plan response for failed step: {response_text}")
        
        # Parse the response to extract the revised plan
        parsed_data = self._parse_plan_with_commands(response_text, is_revision=True)

        if 'error' in parsed_data:
            logger.error(f"Failed to revise plan after step failure: {parsed_data['error']}")
            return {'id': None, 'steps': [], 'status': 'error', 'error': parsed_data['error'], 'revision_summary': ''}
                
        self._store_plan(parsed_data, is_revision=True, original_plan_id=plan_id)
        
        return parsed_data
        
    def _store_plan(self, plan_data, is_revision=False, original_plan_id=None):
        """
        Store a plan both in memory and on disk.
        
        Args:
            plan_data (dict): The plan data to store (this is the internal representation of the plan)
            is_revision (bool): Whether this is a revised plan
            original_plan_id (str): The ID of the original plan if this is a revision
            
        Returns:
            str: The plan ID or None if plan_data is invalid
        """
        if not plan_data or 'error' in plan_data or not plan_data.get('steps'):
             logger.warning(f"Attempted to store an invalid or error plan for ID: {plan_data.get('id', 'N/A')}")
             return plan_data.get('id') 

        plan_id = plan_data.get('id')
        if not plan_id:
            # This should ideally be set by _parse_plan_with_commands upon successful parse
            logger.error("Plan data is missing an ID during storage.")
            # Fallback, though less ideal as ID should be stable post-parsing
            plan_id = str(hash(json.dumps(plan_data.get('steps', []))))
            plan_data['id'] = plan_id
        
        if is_revision and original_plan_id:
            plan_data['original_plan_id'] = original_plan_id
        
        # Store in LRU cache
        self.plans_cache.put(plan_id, plan_data)
        
        # Persist to disk (unchanged)
        self._save_plan_to_disk(plan_id, plan_data)
        
        logger.info(f"{'Revised p' if is_revision else 'P'}lan stored with ID: {plan_id}. Cache size: {len(self.plans_cache)}")
        return plan_id
    
    def _save_plan_to_disk(self, plan_id, plan_data):
        """
        Save a plan to disk for persistence.
        
        Args:
            plan_id (str): The ID of the plan
            plan_data (dict): The plan data to save
        """
        try:
            plan_path = os.path.join(self.plans_dir, f"{plan_id}.json")
            
            with tempfile.NamedTemporaryFile('w', delete=False) as temp_file:
                json.dump(plan_data, temp_file, indent=2) 
                
            shutil.move(temp_file.name, plan_path)
            logger.debug(f"Plan saved to {plan_path}")
            
        except Exception as e:
            logger.error(f"Error saving plan to disk: {e}")
    
    def get_plan(self, plan_id):
        """
        Get a plan by ID, checking both memory cache and disk storage.
        
        Args:
            plan_id (str): The ID of the plan to get
            
        Returns:
            dict: The plan, or None if not found
        """
        # Check LRU cache first
        plan = self.plans_cache.get(plan_id)
        if plan is not None:
            logger.info(f"Plan {plan_id} found in LRU cache (cache hit).")
            return plan
        
        logger.info(f"Plan {plan_id} not in LRU cache (cache miss). Attempting to load from disk.")
            
        # If not in cache, try to load from disk
        try:
            plan_path = os.path.join(self.plans_dir, f"{plan_id}.json")
            if os.path.exists(plan_path):
                with open(plan_path, 'r') as f:
                    disk_plan = json.load(f)
                # Add to LRU cache after loading from disk
                self.plans_cache.put(plan_id, disk_plan)
                logger.info(f"Plan {plan_id} loaded from disk and added to LRU cache. Cache size: {len(self.plans_cache)}")
                return disk_plan
        except Exception as e:
            logger.error(f"Error loading plan {plan_id} from disk: {e}")
            
        # Not found in cache or on disk
        logger.warning(f"Plan {plan_id} not found in cache or on disk.")
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