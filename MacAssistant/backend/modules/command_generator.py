"""
Command Generator Module
Translates high-level task descriptions into executable macOS shell commands or AppleScript.
Now supports LLM-based command generation for more complex tasks.
"""

import re
import os
import json
import logging
from config import active_config
import google.genai as genai
import google.genai.types as types
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

# Reuse the global event loop from llm_integration.py
# This should be imported from llm_integration to avoid duplication
try:
    from modules.llm_integration import global_loop
except ImportError:
    # Fallback in case the import fails
    global_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(global_loop)

class CommandGenerator:
    """Class for generating executable commands from task descriptions."""
    
    def __init__(self):
        """Initialize the Command Generator."""
        
        # Initialize LLM client for command generation
        self.api_key = active_config.GEMINI_API_KEY
        self.model = active_config.GEMINI_MODEL
        self.use_llm = active_config.USE_LLM_COMMAND_GENERATION
        self.temperature = active_config.COMMAND_TEMPERATURE
        
        # Check if LLM command generation is available
        if not self.api_key:
            logger.warning("Missing GEMINI_API_KEY in configuration. LLM-based command generation will not be available.")
            self.llm_available = False
        else:
            self.llm_available = self.use_llm
            if self.llm_available:
                logger.info("LLM-based command generation is enabled")
            else:
                logger.info("LLM-based command generation is disabled in configuration")
    
    def generate_command(self, task_description):
        """
        Generate an executable command for a task description.
        
        Args:
            task_description (str): A description of the task to perform
            
        Returns:
            str: An executable shell command or AppleScript
        """
        logger.info(f"Generating command for task: {task_description}")
        
        
        # Use LLM-based command generation as a fallback
        if self.llm_available:
            try:
                logger.info("Attempting LLM-based command generation")
                command = self._generate_command_with_llm(task_description)
                if command:
                    logger.info(f"LLM generated command: {command}")
                    return command
            except Exception as e:
                logger.error(f"Error in LLM command generation: {e}")
        
        # Fall back to a simple echo command if no pattern matches
        logger.warning(f"No command pattern match for: {task_description}")
        return f'echo "No command generated for: {task_description}"'
    

        
    async def _async_generate_command_with_llm(self, task_description):
        """
        Generate a command using the LLM API asynchronously.
        
        Args:
            task_description (str): A description of the task
            
        Returns:
            str: A generated shell command
        """
        try:
            # System prompt for command generation
            system_prompt = """
            You are a command generation assistant for macOS. Given a task description, generate a single
            executable shell command or AppleScript command that performs the task efficiently. 
            Follow these guidelines:
            
            1. Return ONLY the command, with no explanation, comments, or backticks
            2. Favor built-in macOS commands and utilities
            3. Ensure the command is secure and follows best practices
            4. For file operations, use shell commands (ls, cp, mv, etc.)
            5. For application control, use AppleScript when appropriate
            6. For long commands, use proper quoting and escaping
            7. Be cautious with destructive operations (rm, sudo, etc.)
            8. For instructions to 'type a command', just return that command directly - don't include "echo" or other wrappers
            9. For version checks like "check the version of X", return "X --version"
            10. If the task is to observe output or make a human judgment, no command is needed - return a simple echo command
            
            Examples:
            - Task: "Show CPU usage" -> "top -o cpu -n 5"
            - Task: "Open Safari" -> "open -a Safari" 
            - Task: "Type python3 --version" -> "python3 --version"
            - Task: "Check the version of npm" -> "npm --version"
            - Task: "Create a blank text file named notes.txt" -> "touch notes.txt"
            - Task: "Find all PNG images in Downloads folder" -> "find ~/Downloads -name '*.png'"
            - Task: "Note the output of the previous command" -> "echo 'Noted'"
            """
            
            # Combine prompts
            combined_prompt = f"{system_prompt}\n\nTask: {task_description}\nCommand:"
            
            # Call LLM API
            client = genai.Client(api_key=self.api_key)
            
            # Configure generation parameters
            generation_config = {
                "temperature": self.temperature,  # Lower temperature for more deterministic outputs
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 256,  # Limit output length for commands
            }
            
            response = client.models.generate_content(
                model=self.model,
                contents=[types.Part.from_text(text=combined_prompt)],
                generation_config=generation_config,
            )
            
            # Process response
            command = response.text.strip()
            
            # Log the raw response for debugging
            logger.info(f"Raw LLM response: {command}")
            
            # Remove any explanations or commentary
            # If the response has multiple lines, try to find the actual command
            if "\n" in command and not "```" in command:
                # Look for a line that looks like a command (contains unix commands or typical symbols)
                command_indicators = ['ls', 'cd', 'grep', 'find', 'echo', 'cat', 'touch', 'mkdir', 
                                    'rm', 'cp', 'mv', 'python', 'python3', '--version', '-v', '|', 
                                    'open', '-a', '>', '>>', '&&', '||', ';']
                                    
                for line in command.split('\n'):
                    line = line.strip()
                    # Check if this line looks like a command
                    if any(indicator in line for indicator in command_indicators) and len(line) < 100:
                        command = line
                        logger.info(f"Selected likely command from multi-line response: {command}")
                        break
            
            # Sanity checks 
            if len(command) > 1000:  # Command too long
                logger.warning(f"LLM generated command is too long: {len(command)} chars")
                return None
                
            if "```" in command:  # Command includes markdown code blocks
                # Try to extract just the command
                code_match = re.search(r"```(?:bash|sh)?\n(.+?)```", command, re.DOTALL)
                if code_match:
                    command = code_match.group(1).strip()
                    logger.info(f"Extracted command from code block: {command}")
                else:
                    logger.warning(f"Could not extract command from code block: {command}")
                    return None
                    
            # Check for dangerous commands
            dangerous_patterns = ["rm -rf /", "sudo rm", "> /dev/", "mkfs", "dd if=", ":(){ :|:& };:"]
            if any(pattern in command for pattern in dangerous_patterns):
                logger.warning(f"LLM generated potentially dangerous command: {command}")
                return None
                
            return command
            
        except Exception as e:
            logger.exception(f"Error generating command with LLM: {e}")
            return None
            
    def _generate_command_with_llm(self, task_description):
        """
        Generate a command using the LLM API.
        
        Args:
            task_description (str): A description of the task
            
        Returns:
            str: A generated shell command
        """
        # Run the async function in the event loop
        return global_loop.run_until_complete(self._async_generate_command_with_llm(task_description))