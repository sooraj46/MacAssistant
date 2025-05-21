import unittest
from unittest.mock import patch, MagicMock, mock_open, call
import sys
import os
import json
import asyncio # Required for async test helper
from concurrent.futures import TimeoutError as FuturesTimeoutError 

# Add the backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from modules.llm_integration import LLMIntegration, LRUCache, global_loop as llm_integration_global_loop
from config import TestingConfig # Import TestingConfig directly

# Suppress logging during tests for cleaner output
import logging
logging.disable(logging.CRITICAL)


class TestLLMIntegration(unittest.TestCase):

    def setUp(self):
        self.test_config = TestingConfig() 
        self.test_config.GEMINI_API_KEY = "test_api_key"
        self.test_config.LOG_DIR = "test_logs_llm_integration" 
        self.test_config.PLAN_CACHE_SIZE = 3 
        self.test_config.LLM_MAX_WORKERS = 2
        self.test_config.LLM_TIMEOUT = 0.1 # Very short timeout for testing

        # Create mock directories
        self.mock_plans_dir = os.path.join(self.test_config.LOG_DIR, 'plans')
        os.makedirs(self.mock_plans_dir, exist_ok=True)

        # Patch 'modules.llm_integration.active_config'
        # This ensures that when LLMIntegration() is instantiated, it uses self.test_config
        self.active_config_patcher = patch('modules.llm_integration.active_config', self.test_config)
        self.mock_active_config = self.active_config_patcher.start()
        
        self.llm_integration = LLMIntegration()
        
        # Clear the LRU cache before each test
        self.llm_integration.plans_cache.cache.clear()

    def tearDown(self):
        self.active_config_patcher.stop()
        # Clean up the mocked log directory structure
        if os.path.exists(self.test_config.LOG_DIR):
            import shutil
            shutil.rmtree(self.test_config.LOG_DIR)

    # --- Cache Usage Tests ---
    @patch('modules.llm_integration.os.path.exists')
    @patch('modules.llm_integration.open', new_callable=mock_open)
    @patch('modules.llm_integration.json.load')
    def test_get_plan_cache_hit(self, mock_json_load, mock_file_open, mock_path_exists):
        plan_id = "plan123"
        plan_data = {"id": plan_id, "steps": [{"description": "Test step"}]}
        self.llm_integration.plans_cache.put(plan_id, plan_data)

        retrieved_plan = self.llm_integration.get_plan(plan_id)

        self.assertEqual(retrieved_plan, plan_data)
        mock_path_exists.assert_not_called()
        mock_file_open.assert_not_called()
        mock_json_load.assert_not_called()

    @patch('modules.llm_integration.os.path.exists')
    @patch('modules.llm_integration.open', new_callable=mock_open)
    @patch('modules.llm_integration.json.load')
    def test_get_plan_cache_miss_disk_hit(self, mock_json_load, mock_file_open, mock_path_exists):
        plan_id = "plan456"
        plan_data_on_disk = {"id": plan_id, "steps": [{"description": "Loaded from disk"}]}
        
        mock_path_exists.return_value = True
        mock_json_load.return_value = plan_data_on_disk

        self.assertIsNone(self.llm_integration.plans_cache.get(plan_id)) # Not in cache

        retrieved_plan = self.llm_integration.get_plan(plan_id)

        self.assertEqual(retrieved_plan, plan_data_on_disk)
        expected_plan_path = os.path.join(self.mock_plans_dir, f"{plan_id}.json")
        mock_path_exists.assert_called_once_with(expected_plan_path)
        mock_file_open.assert_called_once_with(expected_plan_path, 'r')
        mock_json_load.assert_called_once()
        self.assertEqual(self.llm_integration.plans_cache.get(plan_id), plan_data_on_disk) # Now in cache

    @patch('modules.llm_integration.os.path.exists')
    def test_get_plan_not_in_cache_or_disk(self, mock_path_exists):
        plan_id = "plan789"
        mock_path_exists.return_value = False

        retrieved_plan = self.llm_integration.get_plan(plan_id)

        self.assertIsNone(retrieved_plan)
        expected_plan_path = os.path.join(self.mock_plans_dir, f"{plan_id}.json")
        mock_path_exists.assert_called_once_with(expected_plan_path)

    @patch('modules.llm_integration.LLMIntegration._save_plan_to_disk')
    def test_store_plan_puts_in_cache_and_calls_save_to_disk(self, mock_save_to_disk):
        plan_id = "planStore1"
        plan_data = {"id": plan_id, "steps": [{"description": "Test store"}], "status": "generated"}
        
        self.assertIsNone(self.llm_integration.plans_cache.get(plan_id))

        stored_id = self.llm_integration._store_plan(plan_data)
        self.assertEqual(stored_id, plan_id)
        self.assertEqual(self.llm_integration.plans_cache.get(plan_id), plan_data)
        mock_save_to_disk.assert_called_once_with(plan_id, plan_data)

    @patch('modules.llm_integration.tempfile.NamedTemporaryFile') # Keep before shutil.move
    @patch('modules.llm_integration.shutil.move')
    @patch('modules.llm_integration.json.dump')
    def test_save_plan_to_disk_actual_implementation(self, mock_json_dump, mock_shutil_move, mock_temp_file_constructor):
        # mock_temp_file_constructor is the mock for the tempfile.NamedTemporaryFile class itself
        mock_temp_file_instance = MagicMock()
        mock_temp_file_instance.name = "dummy_temp_file_name.json"
        # Configure the __enter__ method of the context manager returned by mock_open
        mock_temp_file_constructor.return_value.__enter__.return_value = mock_temp_file_instance
        
        plan_id = "planDiskSave2"
        plan_data = {"id": plan_id, "steps": [{"description": "Test disk save"}]}
        
        self.llm_integration._save_plan_to_disk(plan_id, plan_data)

        mock_temp_file_constructor.assert_called_once_with('w', delete=False)
        mock_json_dump.assert_called_once_with(plan_data, mock_temp_file_instance)
        
        final_plan_path = os.path.join(self.mock_plans_dir, f"{plan_id}.json")
        mock_shutil_move.assert_called_once_with(mock_temp_file_instance.name, final_plan_path)

    # --- _call_gemini_api Tests ---
    @patch('modules.llm_integration.LLMIntegration.async_call_gemini')
    @patch('modules.llm_integration.global_loop') # Mock the loop itself
    def test_call_gemini_api_success(self, mock_global_loop, mock_async_call_gemini_method):
        # Configure the mock executor directly on the instance for this test
        mock_executor_submit_future = MagicMock()
        mock_executor_submit_future.result.return_value = "LLM response text"
        self.llm_integration.executor.submit = MagicMock(return_value=mock_executor_submit_future)
        
        # mock_async_call_gemini_method is already a mock due to @patch, 
        # it will return a coroutine-like MagicMock by default.
        # Let's make it return a specific mock for clarity if needed, but usually not required.
        # mock_async_call_gemini_method.return_value = asyncio.Future() (if we were using real futures)

        system_prompt = "System prompt"
        user_message = "User message"
        
        response = self.llm_integration._call_gemini_api(system_prompt, user_message)

        self.assertEqual(response, "LLM response text")
        # The first arg to submit is global_loop.run_until_complete
        # The second arg is the coroutine, which is the result of calling async_call_gemini
        self.llm_integration.executor.submit.assert_called_once()
        call_args = self.llm_integration.executor.submit.call_args
        self.assertEqual(call_args[0][0], mock_global_loop.run_until_complete)
        # The coroutine object passed to run_until_complete is the result of mock_async_call_gemini_method
        mock_async_call_gemini_method.assert_called_once_with(system_prompt, user_message)
        self.assertEqual(call_args[0][1], mock_async_call_gemini_method.return_value)
        
        mock_executor_submit_future.result.assert_called_once_with(timeout=self.test_config.LLM_TIMEOUT)

    @patch('modules.llm_integration.LLMIntegration.async_call_gemini')
    @patch('modules.llm_integration.global_loop')
    def test_call_gemini_api_llm_error(self, mock_global_loop, mock_async_call_gemini_method):
        mock_executor_submit_future = MagicMock()
        mock_executor_submit_future.result.side_effect = Exception("LLM API Error")
        self.llm_integration.executor.submit = MagicMock(return_value=mock_executor_submit_future)

        with self.assertRaisesRegex(Exception, "Gemini API call via executor failed: LLM API Error"):
            self.llm_integration._call_gemini_api("sys", "user")
        
        mock_executor_submit_future.result.assert_called_once_with(timeout=self.test_config.LLM_TIMEOUT)

    @patch('modules.llm_integration.LLMIntegration.async_call_gemini')
    @patch('modules.llm_integration.global_loop')
    def test_call_gemini_api_timeout(self, mock_global_loop, mock_async_call_gemini_method):
        mock_executor_submit_future = MagicMock()
        mock_executor_submit_future.result.side_effect = FuturesTimeoutError("API call timed out")
        self.llm_integration.executor.submit = MagicMock(return_value=mock_executor_submit_future)

        with self.assertRaisesRegex(TimeoutError, f"Gemini API call timed out after {self.test_config.LLM_TIMEOUT} seconds."):
            self.llm_integration._call_gemini_api("sys", "user")
            
        mock_executor_submit_future.result.assert_called_once_with(timeout=self.test_config.LLM_TIMEOUT)

    # Test the actual async_call_gemini by mocking genai.Client
    # This test needs to be run in an event loop.
    @patch('modules.llm_integration.genai.Client')
    def test_async_call_gemini_actual_logic(self, MockGenAIClient):
        mock_genai_instance = MagicMock()
        mock_genai_response = MagicMock()
        mock_genai_response.text = "Mocked GenAI response"
        mock_genai_instance.models.generate_content.return_value = mock_genai_response
        MockGenAIClient.return_value = mock_genai_instance

        system_prompt = "Test system prompt"
        user_message = "Test user message"
        
        # Use the global_loop from the module for this async test
        response_text = llm_integration_global_loop.run_until_complete(
            self.llm_integration.async_call_gemini(system_prompt, user_message)
        )

        self.assertEqual(response_text, "Mocked GenAI response")
        MockGenAIClient.assert_called_once_with(api_key=self.test_config.GEMINI_API_KEY)
        
        expected_combined_prompt = f"{system_prompt}\n\nUser request: {user_message}"
        args, kwargs = mock_genai_instance.models.generate_content.call_args
        self.assertEqual(kwargs['model'], self.test_config.GEMINI_MODEL)
        # Simple check for contents (actual type is Part)
        self.assertTrue(expected_combined_prompt in str(kwargs['contents'][0]))

if __name__ == '__main__':
    # Re-enable logging if running tests directly for debugging
    # logging.disable(logging.NOTSET) 
    unittest.main()
