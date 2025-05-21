import unittest
import sys
import os
import json
import logging

# Add the backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.llm_integration import LLMIntegration

# Suppress logging during tests for cleaner output
logging.disable(logging.CRITICAL)

class TestLLMIntegrationParsing(unittest.TestCase):

    def setUp(self):
        # We don't need a real API key or full config for parsing tests
        # However, LLMIntegration constructor expects GEMINI_API_KEY.
        # We can mock active_config or parts of it if necessary,
        # but for now, these parsing methods are static or only need self.
        # For _parse_plan_with_commands, an instance is needed.
        
        # Mock active_config to avoid issues with LLMIntegration instantiation
        # if it were to read more from config in __init__ for these specific methods.
        # For now, the parsing methods don't heavily depend on active_config.
        self.llm_integration_instance = LLMIntegration()
        # Monkey patch the logger inside the instance to control its output during tests if needed
        # self.llm_integration_instance.logger = MagicMock() 


    # --- Tests for _parse_plan_with_commands ---

    def test_parse_valid_plan(self):
        response_text = """
        {
          "plan": [
            {
              "number": 1,
              "description": "Check disk space",
              "command": "df -h",
              "is_risky": false,
              "is_observe": false
            },
            {
              "number": 2,
              "description": "Observe output",
              "command": null,
              "is_risky": false,
              "is_observe": true
            }
          ]
        }
        """
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data)
        self.assertIsNotNone(parsed_data.get('id'))
        self.assertEqual(parsed_data.get('status'), 'generated')
        self.assertEqual(len(parsed_data['steps']), 2)
        self.assertEqual(parsed_data['steps'][0]['description'], "Check disk space")
        self.assertEqual(parsed_data['steps'][0]['command'], "df -h")
        self.assertEqual(parsed_data['steps'][1]['command'], "") # None command becomes empty string

    def test_parse_json_syntax_error(self):
        response_text = '{"plan": [{"number": 1, "description": "Test", "command": "ls",}]}' # Trailing comma
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertEqual(parsed_data.get('status'), 'error')
        self.assertEqual(parsed_data.get('error_code'), 'PARSING_FAILED')
        self.assertIn("JSON decoding error", parsed_data.get('message', ''))
        self.assertIn(response_text[:200], parsed_data.get('raw_response_snippet', ''))

    def test_parse_missing_plan_key(self):
        response_text = '{"description": "This is not a plan"}'
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertEqual(parsed_data.get('status'), 'error')
        self.assertEqual(parsed_data.get('error_code'), 'VALIDATION_FAILED')
        self.assertIn("'plan' key is missing or not a list", parsed_data.get('message', ''))
        self.assertIn(response_text[:200], parsed_data.get('raw_response_snippet', ''))

    def test_parse_plan_key_not_a_list(self):
        response_text = '{"plan": "This should be a list"}'
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertEqual(parsed_data.get('status'), 'error')
        self.assertEqual(parsed_data.get('error_code'), 'VALIDATION_FAILED')
        self.assertIn("'plan' key is missing or not a list", parsed_data.get('message', ''))

    def test_parse_step_not_a_dictionary(self):
        response_text = '{"plan": [ "Step 1 should be a dict, not a string" ]}'
        # The current implementation skips invalid steps rather than returning an error for the whole plan.
        # Let's verify this behavior. If strictness is desired, the code would change.
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data) # No global error
        self.assertEqual(len(parsed_data['steps']), 0) # The invalid step is skipped

    def test_parse_step_missing_number(self):
        response_text = '{"plan": [{"description": "missing number", "command": "ls"}]}'
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertEqual(parsed_data.get('status'), 'error')
        self.assertEqual(parsed_data.get('error_code'), 'VALIDATION_FAILED')
        self.assertIn("Missing critical keys ('number', 'description')", parsed_data.get('message', ''))

    def test_parse_step_missing_description(self):
        response_text = '{"plan": [{"number": 1, "command": "ls"}]}'
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertEqual(parsed_data.get('status'), 'error')
        self.assertEqual(parsed_data.get('error_code'), 'VALIDATION_FAILED')
        self.assertIn("Missing critical keys ('number', 'description')", parsed_data.get('message', ''))

    def test_parse_command_with_backticks(self):
        response_text = '{"plan": [{"number": 1, "description": "command with backticks", "command": "`ls -la`"}]}'
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data)
        self.assertEqual(parsed_data['steps'][0]['command'], "ls -la")

    def test_parse_command_is_none(self):
        response_text = '{"plan": [{"number": 1, "description": "command is null", "command": null}]}'
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data)
        self.assertEqual(parsed_data['steps'][0]['command'], "") # None command becomes empty string

    def test_parse_is_risky_is_observe_missing_or_invalid(self):
        response_text = """
        {
          "plan": [
            {"number": 1, "description": "Risky missing", "command": "cmd1"},
            {"number": 2, "description": "Observe invalid", "command": "cmd2", "is_observe": "not-a-boolean"},
            {"number": 3, "description": "Both present", "command": "cmd3", "is_risky": true, "is_observe": true}
          ]
        }
        """
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data)
        self.assertEqual(len(parsed_data['steps']), 3)
        self.assertFalse(parsed_data['steps'][0]['is_risky'])
        self.assertFalse(parsed_data['steps'][0]['is_observe'])
        self.assertFalse(parsed_data['steps'][1]['is_risky'])
        self.assertFalse(parsed_data['steps'][1]['is_observe']) # Invalid string becomes False
        self.assertTrue(parsed_data['steps'][2]['is_risky'])
        self.assertTrue(parsed_data['steps'][2]['is_observe'])

    def test_parse_markdown_wrapped_json(self):
        response_text = """
        Some text before.
        ```json
        {
          "plan": [
            {
              "number": 1,
              "description": "Markdown wrapped",
              "command": "cat file.txt",
              "is_risky": false,
              "is_observe": false
            }
          ]
        }
        ```
        Some text after.
        """
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data, f"Parsing failed with error: {parsed_data.get('message')}")
        self.assertEqual(len(parsed_data['steps']), 1)
        self.assertEqual(parsed_data['steps'][0]['description'], "Markdown wrapped")

    def test_parse_json_with_leading_trailing_text_no_markdown(self):
        response_text = """
        Here is the plan:
        {
          "plan": [
            {
              "number": 1,
              "description": "Just JSON with text",
              "command": "pwd"
            }
          ]
        }
        Hope this helps!
        """
        # The current regex `r'{\s*".*?":[\s\S]*}'` should find the JSON block.
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text)
        self.assertNotIn('error_code', parsed_data, f"Parsing failed with error: {parsed_data.get('message')}")
        self.assertEqual(len(parsed_data['steps']), 1)
        self.assertEqual(parsed_data['steps'][0]['description'], "Just JSON with text")

    def test_parse_revision_summary(self):
        response_text = """
        {
          "revision_summary": "Made changes to step 1.",
          "plan": [
            {
              "number": 1,
              "description": "Revised step",
              "command": "ls -l"
            }
          ]
        }
        """
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text, is_revision=True)
        self.assertNotIn('error_code', parsed_data)
        self.assertEqual(parsed_data.get('revision_summary'), "Made changes to step 1.")
        self.assertEqual(len(parsed_data['steps']), 1)

    def test_parse_revision_summary_missing(self):
        response_text = """
        {
          "plan": [
            {
              "number": 1,
              "description": "No revision summary provided",
              "command": "ls -l"
            }
          ]
        }
        """
        parsed_data = self.llm_integration_instance._parse_plan_with_commands(response_text, is_revision=True)
        self.assertNotIn('error_code', parsed_data)
        # Defaults to an empty string or a placeholder if not found.
        # Current implementation sets it to 'Revision summary was not a string or was missing.'
        self.assertEqual(parsed_data.get('revision_summary'), 'Revision summary was not a string or was missing.')


    # --- Tests for verify_execution_result parsing ---

    def test_verify_execution_valid_json(self):
        response_text = '{"success": true, "explanation": "Command ran well.", "suggestion": "None needed."}'
        # Note: verify_execution_result is a method of LLMIntegration instance
        # For testing parsing logic directly, we can simulate its behavior or test parts.
        # The method itself involves an LLM call. Here, we are interested in the parsing part.
        # Let's assume the LLM call returned `response_text`.
        # We need to mock `_call_gemini_api` for `verify_execution_result`.
        # However, the subtask asks to test the *parsing logic*.
        # The parsing logic is inside `verify_execution_result` after the LLM call.
        # A direct test of a private parsing helper would be ideal if it existed.
        # Since it doesn't, we test `verify_execution_result` and mock the LLM call.
        
        self.llm_integration_instance._call_gemini_api = lambda sys_prompt, usr_msg: response_text
        
        result = self.llm_integration_instance.verify_execution_result("desc", "cmd", "stdout", "stderr", True)
        self.assertTrue(result['success'])
        self.assertEqual(result['explanation'], "Command ran well.")
        self.assertEqual(result['suggestion'], "None needed.")
        self.assertNotIn("error_code", result)


    def test_verify_execution_missing_success_key(self):
        response_text = '{"explanation": "Forgot success.", "suggestion": "Add it."}'
        self.llm_integration_instance._call_gemini_api = lambda sys_prompt, usr_msg: response_text
        
        # `original_success_status` is the `success` argument passed to verify_execution_result
        original_success_status = True 
        result = self.llm_integration_instance.verify_execution_result("desc", "cmd", "stdout", "stderr", original_success_status)
        
        self.assertEqual(result['success'], original_success_status) # Should fall back to original success
        self.assertEqual(result['explanation'], "Invalid structure in LLM verification response. Missing 'success' or 'explanation'.")
        self.assertEqual(result['error_code'], "VALIDATION_FAILED")

    def test_verify_execution_json_syntax_error(self):
        response_text = '{"success": true, "explanation": "Bad JSON,,}' # Extra comma
        self.llm_integration_instance._call_gemini_api = lambda sys_prompt, usr_msg: response_text
        original_success_status = False
        result = self.llm_integration_instance.verify_execution_result("desc", "cmd", "stdout", "stderr", original_success_status)

        self.assertEqual(result['success'], original_success_status)
        self.assertTrue("JSON parsing failed for verification response" in result['explanation'])
        self.assertEqual(result['error_code'], "PARSING_FAILED")

    def test_verify_execution_markdown_wrapped_json(self):
        response_text = "```json\n{\"success\": false, \"explanation\": \"It failed.\", \"suggestion\": \"Check logs.\"}\n```"
        self.llm_integration_instance._call_gemini_api = lambda sys_prompt, usr_msg: response_text
        result = self.llm_integration_instance.verify_execution_result("desc", "cmd", "stdout", "stderr", True)

        self.assertFalse(result['success'])
        self.assertEqual(result['explanation'], "It failed.")
        self.assertEqual(result['suggestion'], "Check logs.")
        self.assertNotIn("error_code", result)

    def test_verify_execution_no_json_found(self):
        response_text = "This is not a JSON response at all."
        self.llm_integration_instance._call_gemini_api = lambda sys_prompt, usr_msg: response_text
        original_success_status = True
        result = self.llm_integration_instance.verify_execution_result("desc", "cmd", "stdout", "stderr", original_success_status)

        self.assertEqual(result['success'], original_success_status) # Fallback
        self.assertEqual(result['explanation'], "Unable to parse LLM verification response: No JSON block found.")
        self.assertEqual(result['error_code'], "NO_JSON_FOUND")
        
    def test_verify_execution_suggestion_missing(self):
        response_text = '{"success": true, "explanation": "No suggestion here."}'
        self.llm_integration_instance._call_gemini_api = lambda sys_prompt, usr_msg: response_text
        result = self.llm_integration_instance.verify_execution_result("desc", "cmd", "stdout", "stderr", True)

        self.assertTrue(result['success'])
        self.assertEqual(result['explanation'], "No suggestion here.")
        self.assertEqual(result['suggestion'], "") # Should default to empty string
        self.assertNotIn("error_code", result)

if __name__ == '__main__':
    # Re-enable logging if running tests directly for debugging
    # logging.disable(logging.NOTSET) 
    unittest.main()
