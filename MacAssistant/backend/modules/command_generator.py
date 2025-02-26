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
        # Load command templates if available
        self.templates_file = os.path.join(os.path.dirname(__file__), '../templates/command_templates.json')
        self.templates = self._load_templates()
        
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
        
        # Check for exact matches in templates
        command = self._check_templates(task_description)
        if command:
            logger.info(f"Template match found: {command}")
            return command
        
        # Process common patterns
        command = self._process_patterns(task_description)
        if command:
            logger.info(f"Pattern match found: {command}")
            return command
        
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
    
    def _load_templates(self):
        """
        Load command templates from JSON file.
        
        Returns:
            dict: A dictionary of command templates
        """
        templates = {}
        
        if os.path.exists(self.templates_file):
            try:
                with open(self.templates_file, 'r') as f:
                    templates = json.load(f)
            except Exception as e:
                print(f"Error loading command templates: {e}")
        
        return templates
    
    def _check_templates(self, task_description):
        """
        Check if the task matches any templates.
        
        Args:
            task_description (str): A description of the task
            
        Returns:
            str or None: A command if a template matches, None otherwise
        """
        task_lower = task_description.lower()
        
        # Check for exact matches
        for template in self.templates.get('exact', []):
            if task_lower == template['pattern'].lower():
                logger.info(f"Found exact template match: {template['pattern']}")
                return template['command']
        
        # Check for keyword matches
        for template in self.templates.get('keywords', []):
            keywords = template['keywords']
            if all(keyword.lower() in task_lower for keyword in keywords):
                logger.info(f"Found keyword match: {keywords}")
                command = template['command']
                
                # Replace placeholders in the command
                for placeholder in re.findall(r'\{(.*?)\}', command):
                    # Extract the value from the task description using regex
                    if placeholder in template['extractors']:
                        extractor = template['extractors'][placeholder]
                        match = re.search(extractor, task_description)
                        if match:
                            value = match.group(1)
                            original_command = command
                            command = command.replace(f'{{{placeholder}}}', value)
                            logger.info(f"Replaced placeholder {{{placeholder}}} with '{value}': {original_command} -> {command}")
                        else:
                            logger.warning(f"No match found for extractor pattern: {extractor}")
                    else:
                        logger.warning(f"No extractor found for placeholder: {placeholder}")
                
                return command
        
        return None
    
    def _process_patterns(self, task_description):
        """
        Process common task patterns and generate commands.
        
        Args:
            task_description (str): A description of the task
            
        Returns:
            str or None: A command if a pattern matches, None otherwise
        """
        task_lower = task_description.lower()
        
        # Version checks (common pattern found in logs)
        if 'python --version' in task_lower or ('version' in task_lower and 'python' in task_lower and not 'python3' in task_lower):
            return 'python --version'
            
        elif 'python3 --version' in task_lower or ('version' in task_lower and 'python3' in task_lower):
            return 'python3 --version'
            
        elif any(cmd in task_lower for cmd in ['--version', '-v', 'version']) and not any(word in task_lower for word in ['result', 'note', 'check']):
            # Generic version check for various commands
            # Extract the command before --version
            cmd_match = re.search(r'`?([a-zA-Z0-9_\-]+)`?\s+(?:--version|-v|version)', task_description)
            if cmd_match:
                cmd = cmd_match.group(1).strip()
                return f'{cmd} --version'
        
        # File operations
        elif 'create file' in task_lower or 'create a file' in task_lower:
            match = re.search(r'create (?:a )?file (?:named |called )?[\'"]?([\w\.\-]+)[\'"]?(?:.* with content[s]? [\'"]?(.+)[\'"]?)?', task_description, re.IGNORECASE)
            if match:
                filename = match.group(1)
                content = match.group(2) or ''
                return f'echo "{content}" > {filename}'
        
        elif 'delete file' in task_lower or 'remove file' in task_lower:
            match = re.search(r'(?:delete|remove) (?:a |the )?file (?:named |called )?[\'"]?([\w\.\-/]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                filename = match.group(1)
                return f'rm {filename}'
        
        # Directory operations
        elif 'create directory' in task_lower or 'create folder' in task_lower:
            match = re.search(r'create (?:a |the )?(?:directory|folder) (?:named |called )?[\'"]?([\w\.\-/]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                dirname = match.group(1)
                return f'mkdir -p {dirname}'
        
        elif 'delete directory' in task_lower or 'remove directory' in task_lower:
            match = re.search(r'(?:delete|remove) (?:a |the )?(?:directory|folder) (?:named |called )?[\'"]?([\w\.\-/]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                dirname = match.group(1)
                return f'rm -r {dirname}'
        
        # System information
        elif 'show system info' in task_lower or 'system information' in task_lower:
            return 'system_profiler SPHardwareDataType'
        
        elif 'list files' in task_lower or 'show files' in task_lower:
            match = re.search(r'(?:list|show) files (?:in |from )?(?:the )?(?:directory |folder )?[\'"]?([\w\.\-/]*)[\'"]?', task_description, re.IGNORECASE)
            dirname = match.group(1) if match else '.'
            return f'ls -la {dirname}'
        
        # Process management
        elif 'list processes' in task_lower or 'show processes' in task_lower:
            return 'ps aux'
        
        elif 'kill process' in task_lower:
            match = re.search(r'kill (?:the )?process (?:named |called |with pid )?[\'"]?([\w\.\-]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                process = match.group(1)
                # Check if it's a PID (number) or a process name
                if process.isdigit():
                    return f'kill {process}'
                else:
                    return f'pkill -f {process}'
        
        # Network operations
        elif 'ping' in task_lower:
            match = re.search(r'ping (?:the )?(?:host |ip |address |server )?[\'"]?([\w\.\-]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                host = match.group(1)
                return f'ping -c 4 {host}'
        
        # AppleScript operations (for GUI automation)
        elif any(x in task_lower for x in ['open application', 'launch application', 'start application']) or 'open terminal' in task_lower:
            # If it's about opening Terminal specifically
            if 'terminal' in task_lower:
                logger.info("Detected request to open Terminal application")
                return 'open -a Terminal'
            
            # For other applications
            match = re.search(r'(?:open|launch|start) (?:the )?application (?:named |called )?[\'"]?([\w\.\-]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                app_name = match.group(1)
                logger.info(f"Detected request to open application: {app_name}")
                cmd = f'open -a {app_name}'
                logger.info(f"Generated command: {cmd}")
                return cmd
        
        return None
        
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