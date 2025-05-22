import unittest
from unittest.mock import patch, MagicMock, mock_open
import sys
import os
import json
import asyncio
from concurrent.futures import TimeoutError as FuturesTimeoutError

# Add the backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.command_generator import CommandGenerator
from modules.llm_integration import global_loop as command_generator_global_loop # Import the loop
from config import TestingConfig

# Suppress logging during tests
import logging
logging.disable(logging.CRITICAL)

class TestCommandGenerator(unittest.TestCase):

    def setUp(self):
        self.test_config = TestingConfig()
        self.test_config.GEMINI_API_KEY = "test_api_key_for_command_gen"
        self.test_config.USE_LLM_COMMAND_GENERATION = True # Ensure LLM path is tested
        self.test_config.COMMAND_TEMPERATURE = 0.1
        self.test_config.LLM_MAX_WORKERS = 1 # For command generator, maybe 1 is enough
        self.test_config.LLM_TIMEOUT = 0.05 # Very short for testing timeouts

        # Patch active_config for CommandGenerator instantiation
        self.active_config_patcher = patch('modules.command_generator.active_config', self.test_config)
        self.mock_active_config = self.active_config_patcher.start()

        # Mock templates file loading
        self.templates_patcher = patch.object(CommandGenerator, '_load_templates', return_value=self._get_mock_templates())
        self.mock_load_templates = self.templates_patcher.start()

        self.command_generator = CommandGenerator()

    def tearDown(self):
        self.active_config_patcher.stop()
        self.templates_patcher.stop()

    def _get_mock_templates(self):
        return {
            "exact": [
                {"pattern": "show test exact", "command": "echo 'exact template test'"}
            ],
            "keywords": [
                {
                    "keywords": ["test keyword", "file"],
                    "command": "touch {filename}",
                    "extractors": {"filename": "file named (\\w+\\.txt)"}
                }
            ]
        }

    # --- Non-LLM Tests ---
    def test_generate_command_exact_template_match(self):
        command = self.command_generator.generate_command("show test exact")
        self.assertEqual(command, "echo 'exact template test'")

    def test_generate_command_keyword_template_match(self):
        command = self.command_generator.generate_command("This is a test keyword for a file named mydoc.txt please.")
        self.assertEqual(command, "touch mydoc.txt")

    def test_generate_command_pattern_match_python_version(self):
        command = self.command_generator.generate_command("check python --version")
        self.assertEqual(command, "python --version")

    def test_generate_command_pattern_match_create_file(self):
        command = self.command_generator.generate_command("Create file 'test.txt' with content \"hello world\"")
        self.assertEqual(command, 'echo "hello world" > test.txt')
        
        command_no_content = self.command_generator.generate_command("Create file named anothertest.log")
        self.assertEqual(command_no_content, 'echo "" > anothertest.log')


    def test_generate_command_no_match_fallback(self):
        # Ensure LLM is disabled for this specific test to check fallback
        self.command_generator.llm_available = False 
        task_desc = "some obscure task with no template or pattern"
        command = self.command_generator.generate_command(task_desc)
        self.assertEqual(command, f'echo "No command generated for: {task_desc}"')
        self.command_generator.llm_available = self.test_config.USE_LLM_COMMAND_GENERATION # Restore

    # --- LLM-based Command Generation Tests ---
    @patch('modules.command_generator.CommandGenerator._async_generate_command_with_llm')
    # Patch the global_loop imported into command_generator, not the one in llm_integration
    @patch('modules.command_generator.global_loop') 
    def test_generate_command_with_llm_success(self, mock_command_gen_global_loop, mock_async_gen_cmd_llm):
        expected_llm_command = "ls -l /tmp"
        
        # Configure the mock executor on the instance
        mock_executor_future = MagicMock()
        mock_executor_future.result.return_value = expected_llm_command
        self.command_generator.executor.submit = MagicMock(return_value=mock_executor_future)
        
        task_description = "list files in temp directory with details"
        # This call will go through _generate_command_with_llm
        command = self.command_generator.generate_command(task_description) 

        self.assertEqual(command, expected_llm_command)
        self.command_generator.executor.submit.assert_called_once()
        call_args = self.command_generator.executor.submit.call_args
        self.assertEqual(call_args[0][0], mock_command_gen_global_loop.run_until_complete)
        
        # The coroutine is the result of calling _async_generate_command_with_llm
        mock_async_gen_cmd_llm.assert_called_once_with(task_description)
        self.assertEqual(call_args[0][1], mock_async_gen_cmd_llm.return_value)
        
        mock_executor_future.result.assert_called_once_with(timeout=self.test_config.LLM_TIMEOUT)

    @patch('modules.command_generator.CommandGenerator._async_generate_command_with_llm')
    @patch('modules.command_generator.global_loop')
    def test_generate_command_with_llm_api_error(self, mock_command_gen_global_loop, mock_async_gen_cmd_llm):
        mock_executor_future = MagicMock()
        mock_executor_future.result.side_effect = Exception("LLM Gen Error")
        self.command_generator.executor.submit = MagicMock(return_value=mock_executor_future)
        
        task_description = "a complex task for llm"
        # generate_command catches the exception from _generate_command_with_llm and logs it.
        # It should then return the fallback echo command.
        command = self.command_generator.generate_command(task_description)
        
        self.assertEqual(command, f'echo "No command generated for: {task_description}"')
        mock_executor_future.result.assert_called_once_with(timeout=self.test_config.LLM_TIMEOUT)


    @patch('modules.command_generator.CommandGenerator._async_generate_command_with_llm')
    @patch('modules.command_generator.global_loop')
    def test_generate_command_with_llm_timeout(self, mock_command_gen_global_loop, mock_async_gen_cmd_llm):
        mock_executor_future = MagicMock()
        mock_executor_future.result.side_effect = FuturesTimeoutError("LLM Gen Timeout")
        self.command_generator.executor.submit = MagicMock(return_value=mock_executor_future)

        task_description = "another complex task for llm"
        # Similar to API error, timeout should be caught and lead to fallback.
        command = self.command_generator.generate_command(task_description)

        self.assertEqual(command, f'echo "No command generated for: {task_description}"')
        mock_executor_future.result.assert_called_once_with(timeout=self.test_config.LLM_TIMEOUT)

    # Test the actual _async_generate_command_with_llm method
    @patch('modules.command_generator.genai.Client')
    def test_async_generate_command_with_llm_actual_logic(self, MockGenAIClient):
        mock_genai_instance = MagicMock()
        mock_genai_response = MagicMock()
        mock_genai_response.text = "touch test_file.txt" # Expected command
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        MockGenAIClient.return_value = mock_genai_instance

        task_description = "create a test file"
        
        # Run the async method using the global_loop imported by command_generator
        # This loop is originally from llm_integration
        actual_command = command_generator_global_loop.run_until_complete(
            self.command_generator._async_generate_command_with_llm(task_description)
        )

        self.assertEqual(actual_command, "touch test_file.txt")
        MockGenAIClient.assert_called_once_with(api_key=self.test_config.GEMINI_API_KEY)
        
        args, kwargs = mock_genai_instance.models.generate_content.call_args
        self.assertEqual(kwargs['model'], self.test_config.GEMINI_MODEL)
        # Check that generation_config from the method is used
        self.assertEqual(kwargs['generation_config']['temperature'], self.test_config.COMMAND_TEMPERATURE)
        self.assertTrue(f"Task: {task_description}" in str(kwargs['contents'][0]))


    @patch('modules.command_generator.genai.Client')
    def test_async_generate_command_llm_dangerous_command_filter(self, MockGenAIClient):
        mock_genai_instance = MagicMock()
        mock_genai_response = MagicMock()
        mock_genai_response.text = "sudo rm -rf /" 
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        MockGenAIClient.return_value = mock_genai_instance
        
        actual_command = command_generator_global_loop.run_until_complete(
            self.command_generator._async_generate_command_with_llm("do something very risky")
        )
        self.assertIsNone(actual_command) # Dangerous command should be filtered

    @patch('modules.command_generator.genai.Client')
    def test_async_generate_command_llm_code_block_extraction(self, MockGenAIClient):
        mock_genai_instance = MagicMock()
        mock_genai_response = MagicMock()
        mock_genai_response.text = "Here is the command:\n```bash\nls -la\n```\nExecute it."
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        MockGenAIClient.return_value = mock_genai_instance
        
        actual_command = command_generator_global_loop.run_until_complete(
            self.command_generator._async_generate_command_with_llm("list files with details")
        )
        self.assertEqual(actual_command, "ls -la")


if __name__ == '__main__':
    # Re-enable logging if running tests directly for debugging
    # logging.disable(logging.NOTSET)
    unittest.main()
