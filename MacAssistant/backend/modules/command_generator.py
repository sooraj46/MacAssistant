"""
Command Generator Module
Translates high-level task descriptions into executable macOS shell commands or AppleScript.
"""

import re
import os
import json
from config import active_config

class CommandGenerator:
    """Class for generating executable commands from task descriptions."""
    
    def __init__(self):
        """Initialize the Command Generator."""
        # Load command templates if available
        self.templates_file = os.path.join(os.path.dirname(__file__), '../templates/command_templates.json')
        self.templates = self._load_templates()
    
    def generate_command(self, task_description):
        """
        Generate an executable command for a task description.
        
        Args:
            task_description (str): A description of the task to perform
            
        Returns:
            str: An executable shell command or AppleScript
        """
        # Check for exact matches in templates
        command = self._check_templates(task_description)
        if command:
            return command
        
        # Process common patterns
        command = self._process_patterns(task_description)
        if command:
            return command
        
        # Fall back to a simple echo command if no pattern matches
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
                return template['command']
        
        # Check for keyword matches
        for template in self.templates.get('keywords', []):
            keywords = template['keywords']
            if all(keyword.lower() in task_lower for keyword in keywords):
                command = template['command']
                
                # Replace placeholders in the command
                for placeholder in re.findall(r'\{(.*?)\}', command):
                    # Extract the value from the task description using regex
                    if placeholder in template['extractors']:
                        extractor = template['extractors'][placeholder]
                        match = re.search(extractor, task_description)
                        if match:
                            value = match.group(1)
                            command = command.replace(f'{{{placeholder}}}', value)
                
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
        
        # File operations
        if 'create file' in task_lower or 'create a file' in task_lower:
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
        elif any(x in task_lower for x in ['open application', 'launch application', 'start application']):
            match = re.search(r'(?:open|launch|start) (?:the )?application (?:named |called )?[\'"]?([\w\.\-]+)[\'"]?', task_description, re.IGNORECASE)
            if match:
                app_name = match.group(1)
                return f'open -a "{app_name}"'
        
        return None