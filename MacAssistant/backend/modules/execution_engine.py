"""
Execution Engine Module
Executes commands on the macOS system and captures their output.
"""

import os
import subprocess
import shlex
import time
from config import active_config

class ExecutionEngine:
    """Class for executing commands on the macOS system."""
    
    def __init__(self):
        """Initialize the Execution Engine."""
        self.max_execution_time = active_config.MAX_EXECUTION_TIME
    
    def execute(self, command):
        """
        Execute a command on the macOS system.
        
        Args:
            command (str): The command to execute
            
        Returns:
            tuple: (success, stdout, stderr)
                success (bool): True if the command executed successfully, False otherwise
                stdout (str): The standard output of the command
                stderr (str): The standard error of the command
        """
        # Determine if this is a shell command or AppleScript
        if command.strip().startswith('tell application') or command.strip().startswith('osascript'):
            return self._execute_applescript(command)
        else:
            return self._execute_shell_command(command)
    
    def _execute_shell_command(self, command):
        """
        Execute a shell command.
        
        Args:
            command (str): The shell command to execute
            
        Returns:
            tuple: (success, stdout, stderr)
        """
        try:
            # Split the command for security (prevents shell injection)
            # but use shell=True for commands with pipes, redirections, etc.
            if '|' in command or '>' in command or '<' in command or '&' in command:
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True
                )
            else:
                args = shlex.split(command)
                process = subprocess.Popen(
                    args,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
            
            # Set a timeout for the command
            start_time = time.time()
            
            # Wait for the process to complete or timeout
            while process.poll() is None:
                if time.time() - start_time > self.max_execution_time:
                    process.terminate()
                    return False, "", f"Command timed out after {self.max_execution_time} seconds"
                time.sleep(0.1)
            
            # Get the output
            stdout, stderr = process.communicate()
            
            # Check return code
            success = process.returncode == 0
            
            return success, stdout, stderr
        
        except Exception as e:
            return False, "", f"Error executing command: {str(e)}"
    
    def _execute_applescript(self, script):
        """
        Execute an AppleScript.
        
        Args:
            script (str): The AppleScript to execute
            
        Returns:
            tuple: (success, stdout, stderr)
        """
        try:
            # Check if the script is already an osascript command
            if script.strip().startswith('osascript'):
                return self._execute_shell_command(script)
            
            # Wrap the script in osascript
            command = f'osascript -e \'{script}\''
            
            # Execute the command
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                text=True
            )
            
            # Set a timeout for the command
            start_time = time.time()
            
            # Wait for the process to complete or timeout
            while process.poll() is None:
                if time.time() - start_time > self.max_execution_time:
                    process.terminate()
                    return False, "", f"AppleScript timed out after {self.max_execution_time} seconds"
                time.sleep(0.1)
            
            # Get the output
            stdout, stderr = process.communicate()
            
            # Check return code
            success = process.returncode == 0
            
            return success, stdout, stderr
        
        except Exception as e:
            return False, "", f"Error executing AppleScript: {str(e)}"