"""
Execution Engine Module
Executes commands on the macOS system and captures their output.
"""

import os
import subprocess
import shlex
import time
import logging
from config import active_config

# Configure logging
logger = logging.getLogger(__name__)

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
        logger.info(f"Executing command: {command}")
        
        # Determine if this is a shell command or AppleScript
        if command.strip().startswith('tell application') or command.strip().startswith('osascript'):
            logger.info("Detected AppleScript command")
            return self._execute_applescript(command)
        else:
            logger.info("Detected shell command")
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
            # Check for unsubstituted placeholders or typical LLM formatting issues
            if "{" in command and "}" in command:
                logger.error(f"Command contains unsubstituted placeholder: {command}")
                return False, "", f"Error: Command contains unsubstituted placeholder variables: {command}"
                
            # Check for backticks/markdown leftovers - common in LLM outputs
            if command.startswith('`') and command.endswith('`'):
                # Clean up backticks
                command = command.strip('`')
                logger.info(f"Removed enclosing backticks from command: {command}")
                
            # Debug command before execution
            logger.info(f"Shell command to execute: {command}")
            
            # Special handling for 'open -a' commands
            if command.startswith('open -a'):
                logger.info("Handling open -a command")
                # Make sure app name is properly quoted if needed
                if '"' not in command and "'" not in command:
                    # Check if there's a space in the app name that needs quoting
                    if len(command.split()) > 3:
                        app_name = ' '.join(command.split()[2:])
                        command = f'open -a "{app_name}"'
                        logger.info(f"Modified command with quotes: {command}")
            
            # Split the command for security (prevents shell injection)
            # but use shell=True for commands with pipes, redirections, etc.
            if '|' in command or '>' in command or '<' in command or '&' in command:
                logger.info("Using shell=True for command with special characters")
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    text=True
                )
            else:
                try:
                    args = shlex.split(command)
                    logger.info(f"Parsed command args: {args}")
                    process = subprocess.Popen(
                        args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                except Exception as e:
                    logger.error(f"Error splitting command: {e}")
                    logger.info("Falling back to shell=True")
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
                    logger.warning(f"Command timed out after {self.max_execution_time} seconds")
                    return False, "", f"Command timed out after {self.max_execution_time} seconds"
                time.sleep(0.1)
            
            # Get the output
            stdout, stderr = process.communicate()
            
            # Check return code
            success = process.returncode == 0
            
            # Log results
            logger.info(f"Command completed with return code: {process.returncode}")
            logger.info(f"stdout: {stdout}")
            logger.info(f"stderr: {stderr}")
            
            return success, stdout, stderr
        
        except Exception as e:
            logger.error(f"Exception executing command: {str(e)}")
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