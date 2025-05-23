# MacAssistant

MacAssistant is an intelligent task automation assistant for macOS. It allows you to describe tasks in natural language, reviews the execution plan with you, confirms risky operations, and provides detailed feedback on each step.

## Features

- **Natural Language Interface**: Describe your tasks in plain English. Allows users to interact with their Mac using simple, conversational language, making complex operations more accessible.
- **Plan Generation**: AI-generated step-by-step execution plans. Leverages Large Language Models to create detailed, step-by-step execution plans from user requests, showing you exactly what will happen before it does.
- **Human Feedback Loop**: Review and approve/reject plans before execution. Ensures user control by allowing review, modification, or rejection of proposed execution plans before any action is taken.
- **Safety First**: Explicit confirmation for potentially risky operations. Includes a configurable system for identifying potentially risky operations, requiring explicit user confirmation before proceeding with such commands.
- **Detailed Logging**: Comprehensive logging of all actions and results. Keeps a comprehensive record of all tasks, commands, and their outputs, aiding in troubleshooting and auditing.
- **Error Handling**: Intelligent error detection and recovery. Provides intelligent detection of errors during task execution and attempts to offer recovery suggestions or safe ways to halt.
- **Modern Chatbot UI**: Clean, responsive interface with light and dark mode. Offers a clean, intuitive, and responsive user interface, including support for both light and dark themes for user comfort.

## Architecture

MacAssistant employs a robust client-server architecture designed for clarity and extensibility:

- **React Frontend**: The frontend provides a modern, responsive chatbot interface built with React. It handles user input, displays conversation history, and communicates with the backend via HTTP requests. It's responsible for presenting plans, capturing user feedback (approvals/rejections), and showing execution results in real-time.

- **Flask Backend**: The backend is a Python-based Flask application that serves as the core orchestrator. Its responsibilities include:
    - **API Endpoints**: Receiving user queries and commands from the frontend.
    - **LLM Integration**: Communicating with Large Language Models (e.g., OpenAI GPT) to interpret natural language, generate execution plans, and refine them based on feedback.
    - **Plan Management**: Storing and managing the lifecycle of execution plans.
    - **Command Generation**: Translating plan steps into executable shell commands for macOS.
    - **Execution Engine**: Running the generated commands in a controlled environment.
    - **Safety Checker**: Analyzing commands against a list of risky patterns and flagging them for user confirmation.
    - **Logging**: Recording all significant events, including user interactions, LLM responses, executed commands, and their outcomes.

- **LLM Integration**: This module is responsible for abstracting the communication with various LLM providers. It handles prompt engineering, sending requests to the LLM, and parsing the generated plans or responses. This allows MacAssistant to be adaptable to different language models.

The typical workflow is as follows:
1. The user enters a task in the React frontend.
2. The frontend sends the task to the Flask backend.
3. The backend's LLM Integration module queries the LLM to generate a plan.
4. The backend presents the plan to the frontend for user review.
5. The user approves, rejects, or requests modifications to the plan via the frontend.
6. If approved, the backend's execution engine runs the commands, after passing them through the safety checker for any necessary confirmations.
7. Results and logs are streamed back to the frontend for the user to see.


## Installation

### Prerequisites

- Python 3.8+
- Node.js 16+
- macOS 10.15+ (Catalina or newer)
- OpenAI API key (or other supported LLM provider)

### Quick Start

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/MacAssistant.git
   cd MacAssistant
   ```

2. Run the setup script:
   ```bash
   ./build.sh
   ```
2a. **Verify build**: After the script finishes, check for any error messages. Ensure that the `MacAssistant/backend/static` directory has been created and populated with files (e.g., `index.html`, `main.js`).

3. Edit the `.env` file to add your OpenAI API key.
3a. **Verify .env**: Create or copy `.env.example` to `.env` in the `MacAssistant` root directory. Ensure your `OPENAI_API_KEY` is correctly set in this `.env` file. The application loads this file on startup to get necessary API keys.

4. **Start the application**:
   ```bash
   ./run.sh
   ```
   This script starts both the backend server and serves the frontend. Look for output indicating the server is running, typically `* Running on http://127.0.0.1:5000` (or `http://localhost:5000`).

5. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```
   If the page loads and you see the chat interface, the basic installation is successful.

### Development Mode

For development, you can run both the frontend and backend in development mode:

```bash
./start-dev.sh
```

This script typically starts the React development server for the frontend (often on port 3000) and the Flask development server for the backend (on port 5000). The React app will be configured to proxy API requests to the backend. You will need two terminal windows/tabs to see logs from both processes.

### Verifying Installation

- **Backend**: Access `http://localhost:5000/api/health` in your browser or via `curl`. You should see a JSON response like `{"status": "healthy"}`.
- **Frontend**: If the main page `http://localhost:5000` loads correctly and you can type in the chat box, the frontend is likely working.
- **LLM Connection**: After starting the application, try a simple command like "list files in my current directory". If you get a plan back, your LLM API key is likely configured correctly. If you see errors related to API keys or authentication, double-check your `.env` file.

## Usage

Using MacAssistant is designed to be straightforward:

1.  **Enter Task Description**: Type your desired task in natural language into the chat input. For example:
    *   "Create a backup of my Documents folder to an external drive named 'MyBackup'."
    *   "Find all PNG files in my Pictures folder larger than 1MB and move them to a new folder called 'Large PNGs'."
    *   "Rename all files starting with 'IMG_' in the 'VacationPhotos' folder to 'HolidayPic_'."
    *   "Check my current Wi-Fi network name."
    *   "What's the weather like in Cupertino?" (Note: Requires appropriate command template and potentially an API integration for external data)

2.  **Review Plan**: MacAssistant will process your request and present a step-by-step execution plan. Review this plan carefully to understand the actions it will take. You can:
    *   **Approve**: If the plan is acceptable.
    *   **Reject**: If you do not want to proceed with the plan.
    *   **(Future Feature Idea / For more advanced use)**: Request modifications if minor changes are needed (current capability may vary; this describes a general aim).

3.  **Confirm Risky Operations**: If any step in the plan is identified as potentially risky (e.g., deleting files, modifying system settings), MacAssistant will explicitly ask for your confirmation before executing that specific step. Review the command and its potential impact before confirming.

4.  **Monitor Execution**: Once approved (and risky steps confirmed), MacAssistant will execute the plan. You'll see real-time feedback, including the commands being run and their outputs or any errors encountered.

5.  **Review Results**: After execution, review the final outcome and any logs provided to ensure the task was completed as expected.

**Tips for Effective Usage:**

*   **Be Specific**: The more specific your request, the better MacAssistant can generate an accurate plan. Instead of "clean up files", try "delete all .tmp files from my Downloads folder".
*   **Start Simple**: If you're new, start with simpler, less critical tasks to get a feel for how MacAssistant works.
*   **Check Paths**: When dealing with files and folders, double-check that the paths in the generated plan are correct before approving.

## Security Considerations

MacAssistant is designed with user safety as a priority. However, as it interacts with your system by executing commands, it's crucial to understand the security measures in place and your role in maintaining a safe operation:

-   **User Permissions**: MacAssistant executes commands with the same permissions as the user account running the application. It does not elevate privileges on its own. Be mindful of what your user account has access to.
-   **Risky Command Detection**: A rule-based system (defined in `backend/templates/risky_patterns.json`) is used to identify commands that could be potentially harmful (e.g., deletions, overwrites, system modifications).
-   **Explicit Confirmation**: Any command flagged as risky requires explicit user confirmation before execution. You will be shown the exact command and asked to approve it. **Always review these commands carefully.**
-   **Input Sanitization**: While MacAssistant aims to generate commands based on your natural language input, and the LLM is instructed to avoid generating malicious code, input sanitization is a complex ongoing concern. The system primarily relies on the LLM's safety features and the risky command confirmation step. Direct execution of arbitrary user-supplied shell commands is generally avoided in the core design.
-   **No Sensitive Data Storage (by default)**: MacAssistant itself does not intentionally store your personal sensitive data (like passwords or private keys) beyond the API keys you provide in the `.env` file. Task history and logs are stored locally on your machine.
-   **API Key Security**: Your LLM API key (e.g., OpenAI API key) is stored in the `.env` file. Ensure this file is kept secure and not publicly exposed. MacAssistant uses this key to communicate with the LLM provider.
-   **Extensibility Risks**: When extending functionality (e.g., adding new command templates or modifying safety checks), be aware that improper configurations could potentially introduce new security vulnerabilities. Test custom extensions thoroughly.
-   **LLM Limitations**: While powerful, LLMs can sometimes misinterpret requests or generate unexpected command sequences. The human review and confirmation steps are critical safeguards against this.
-   **Local Network Exposure**: The Flask backend server, by default, runs on `localhost` and is only accessible from your machine. If you modify it to run on `0.0.0.0` (to be accessible on your local network), ensure your network is secure.

**User's Responsibility:**

*   **Review Plans and Commands**: Carefully review all generated plans and especially any commands flagged as risky before providing approval.
*   **Secure API Keys**: Protect your `.env` file and the API keys within it.
*   **Understand Task Impact**: Before running a complex task, try to understand its potential impact on your system and files.
*   **Keep Software Updated**: Ensure MacAssistant, your OS, and any related dependencies are kept up-to-date to benefit from the latest security patches (though MacAssistant itself does not yet have an auto-update feature).

## Extending Functionality

MacAssistant is designed to be extensible, allowing developers to add new capabilities or customize existing ones.

### Adding New Task Command Patterns

If you find that MacAssistant doesn't understand a particular type of task or doesn't generate the commands you expect, you can add new command patterns. These patterns help the LLM map natural language requests to specific shell command structures.

1.  **Edit `backend/templates/command_templates.json`**:
    *   This JSON file contains a list of predefined templates. Each template typically includes:
        *   `task_type`: A descriptive name for the kind of task (e.g., "file_backup", "text_manipulation").
        *   `description`: A brief explanation of what the template does.
        *   `patterns`: A list of example natural language phrases that should trigger this template. These are used by the LLM for matching.
        *   `command_template`: The actual shell command structure. Placeholders (e.g., `{{source_file}}`, `{{destination_folder}}`) are used to indicate where specific entities extracted from the user's request should be inserted.
        *   `entities`: A list of expected entities (like `source_file`, `destination_folder`) that need to be extracted from the user's query for this template.
        *   `example_command`: An example of how a generated command might look.
    *   Add your new template object to this list. Ensure your placeholders in `command_template` match the `entities` you define.

2.  **Update `backend/modules/command_generator.py` (if necessary)**:
    *   The `CommandGenerator` class, particularly its `_process_patterns` method (or similar logic responsible for selecting and formatting commands), might need adjustments if your new template requires special handling or new entity extraction logic that isn't covered by the existing setup.
    *   For many common patterns, simply adding a well-defined template to `command_templates.json` might be sufficient, as the LLM handles the matching and entity extraction. More complex integrations might require Python code changes here.

### Customizing Safety Checks

You can tailor the safety checker to your specific needs or to flag new types of commands as risky.

1.  **Edit `backend/templates/risky_patterns.json`**:
    *   This file contains a list of regular expressions. Any command generated by MacAssistant that matches one of these patterns will be flagged as risky, requiring user confirmation.
    *   Add your new regex pattern to this list. Be sure to test your regex thoroughly to avoid false positives or negatives. Each entry usually has a `pattern` (the regex) and a `description` (explaining why it's considered risky).

2.  **Update `backend/modules/safety_checker.py` (if necessary)**:
    *   The `SafetyChecker` class, specifically the `_check_dangerous_operations` method, applies these regex patterns.
    *   If your safety check requires more complex logic than a simple regex match (e.g., checking command arguments against a dynamic list, or context-aware checks), you might need to modify the Python code in this module.

**General Tips for Extending:**

*   **Testing**: Thoroughly test any new templates or safety patterns. Try various phrasings for tasks and ensure commands are generated correctly and safety checks trigger as expected.
*   **LLM Prompts**: The core prompts sent to the LLM (found within the `LlmIntegration` module or related configuration) might also influence how well new extensions are understood. Advanced changes might involve tuning these prompts.
*   **Consistency**: Try to follow the existing patterns and coding style within the project.

## Contributing

Contributions to MacAssistant are welcome! Whether it's bug reports, feature suggestions, or code contributions, your help is appreciated. Please follow these guidelines:

### Reporting Bugs

-   Before submitting a bug report, please check the existing issues on GitHub to see if the bug has already been reported.
-   If it hasn't, please open a new issue. Provide as much detail as possible:
    -   Steps to reproduce the bug.
    -   Expected behavior.
    -   Actual behavior.
    -   Your macOS version, Python version, Node.js version.
    -   Any relevant error messages or screenshots.

### Suggesting Enhancements

-   If you have an idea for a new feature or an improvement to an existing one, please open an issue on GitHub to discuss it.
-   Clearly describe the feature, why it would be useful, and any potential implementation ideas you might have.

### Pull Requests

1.  **Fork the Repository**: Create your own fork of the MacAssistant repository.
2.  **Create a Branch**: Create a new branch in your fork for your changes (e.g., `git checkout -b feature/my-new-feature` or `bugfix/issue-123`).
3.  **Make Changes**: Implement your feature or bug fix.
    -   Ensure your code follows the existing style of the project.
    -   If adding new features, consider if documentation or tests are needed.
4.  **Test Your Changes**: Test your changes thoroughly.
5.  **Commit Your Changes**: Write clear, concise commit messages.
6.  **Push to Your Fork**: Push your changes to your forked repository.
7.  **Submit a Pull Request**: Open a pull request from your branch to the `main` branch (or the relevant development branch) of the original MacAssistant repository.
    -   Provide a clear description of the changes in your pull request.
    -   Reference any relevant issues.

### Code of Conduct

While we don't have a formal Code of Conduct document yet, please be respectful and constructive in all your interactions within the project community.

## Troubleshooting

Here are some common issues and how to resolve them:

-   **Problem: Application doesn't start / `run.sh` fails.**
    -   **Solution**:
        -   Ensure all prerequisites (Python, Node.js) are installed correctly and their versions meet the requirements.
        -   Verify that the `build.sh` script completed without errors. If not, address any errors reported during the build process.
        -   Check that the `.env` file exists in the `MacAssistant` root directory and that `OPENAI_API_KEY` (or the key for your chosen LLM provider) is correctly set.
        -   Look for error messages in the terminal output when `run.sh` is executed. These often provide clues.

-   **Problem: Frontend loads, but I see errors related to API calls or "Could not connect to backend".**
    -   **Solution**:
        -   Make sure the backend server started correctly. Check the terminal window where you ran `run.sh` (or the backend part of `start-dev.sh`) for any error messages.
        -   If running in development mode (`start-dev.sh`), ensure both the frontend and backend servers are running (usually on different ports like 3000 for frontend and 5000 for backend).
        -   Verify the backend is healthy by accessing `http://localhost:5000/api/health`.

-   **Problem: Tasks are not understood / Plans are not generated / LLM errors.**
    -   **Solution**:
        -   Verify your `OPENAI_API_KEY` (or equivalent) in the `.env` file is correct and has available credit/quota with the provider.
        -   Check your internet connection.
        -   The LLM might be temporarily unavailable or overloaded. Try again after a few minutes.
        -   Simplify your task description. Very complex or ambiguous requests might be hard for the LLM to process.
        -   Consider if the type of task is supported by the existing `command_templates.json`. You might need to extend functionality for novel tasks.

-   **Problem: Commands are incorrect or don't do what I expect.**
    -   **Solution**:
        -   Review the generated plan carefully *before* approving. If the plan looks wrong, reject it.
        -   Try rephrasing your task description. The way you ask can significantly influence the generated commands.
        -   If a command is risky and requires confirmation, ensure you understand what it does before confirming.
        -   If you consistently get incorrect commands for a specific type of task, it might indicate a need to refine the corresponding entry in `command_templates.json` or the LLM prompting strategy.

-   **Problem: `build.sh` script fails with permission errors.**
    -   **Solution**:
        -   Ensure `build.sh` has execute permissions: `chmod +x build.sh`.
        -   You might need to run parts of the script with `sudo` if it involves installing global Node.js packages or other system-wide changes, though this is generally not recommended if avoidable. Review the script to see what it's doing.

-   **Problem: After pulling new changes, things are broken.**
    -   **Solution**:
        -   Re-run the build script: `./build.sh`. Dependencies or build steps might have changed.
        -   Check if there are new environment variables in `.env.example` that you need to copy to your `.env` file.
        -   Read any release notes or pull request descriptions for specific instructions.

## License

MIT License - See LICENSE file for details.

## Disclaimer

MacAssistant executes commands on your macOS system. While we implement numerous safety checks, please review all plans and commands carefully before execution, especially those marked as risky. The authors are not responsible for any data loss or system damage that may occur from using this software.
