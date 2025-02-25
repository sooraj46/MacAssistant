#!/usr/bin/env python
"""
gemini_llm.py

A minimal example of sending a prompt to Google's Gemini LLM and returning the raw text response.

Usage:
    python gemini_llm.py "Your prompt here"
"""

import os
import sys
import logging

import google.genai as genai
import google.genai.types as types

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL_NAME = "gemini-2.0-flash-thinking-exp-01-21"

def gemini_prompt(prompt: str) -> str:
    """
    Send a prompt string to Gemini and return the raw text of the response.

    Args:
        prompt (str): The text prompt you want to send to the LLM.

    Returns:
        str: The raw text response from Gemini.
    """
    if not API_KEY:
        raise ValueError("Missing GOOGLE_API_KEY environment variable.")
        
    client = genai.Client(api_key=API_KEY)
    logger.info("Sending prompt to Gemini model...")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[types.Part.from_text(text=prompt)],
        )
        # Return raw response text
        return response.text
    except Exception as e:
        logger.exception("Error calling Gemini model: %s", e)
        return f"Error: {e}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python gemini_llm.py \"Your prompt here\"")
        sys.exit(1)

    # The rest of the command line (after the script name) is the prompt
    user_prompt = " ".join(sys.argv[1:])
    result = gemini_prompt(user_prompt)
    print("\n===== GEMINI RESPONSE =====")
    print(result)

