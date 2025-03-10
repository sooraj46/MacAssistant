# MacAssistant

MacAssistant is an intelligent task automation assistant for macOS. It allows you to describe tasks in natural language, reviews the execution plan with you, confirms risky operations, and provides detailed feedback on each step.

## Features

- **Natural Language Interface**: Describe your tasks in plain English
- **Plan Generation**: AI-generated step-by-step execution plans
- **Human Feedback Loop**: Review and approve/reject plans before execution
- **Safety First**: Explicit confirmation for potentially risky operations
- **Detailed Logging**: Comprehensive logging of all actions and results
- **Error Handling**: Intelligent error detection and recovery
- **Modern Chatbot UI**: Clean, responsive interface with light and dark mode

## Architecture

MacAssistant follows a client-server architecture:

- **React Frontend**: Modern chatbot UI for user interaction, with real-time updates
- **Flask Backend**: Core application server handling user requests, LLM communication, plan management, command execution, safety checks, and logging
- **LLM Integration**: Uses OpenAI API (or other providers) for plan generation and revision


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

3. Edit the `.env` file to add your OpenAI API key.

4. Start the application:
   ```bash
   ./run.sh
   ```

5. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

### Development Mode

For development, you can run both the frontend and backend in development mode:

```bash
./start-dev.sh
```

This will start:
http://localhost:5000

## Usage

1. Enter a task description in the chat input (e.g., "Create a backup of my Documents folder")
2. Review the generated plan and either accept or reject it
3. If a step requires confirmation (marked as risky), review the command and confirm if appropriate
4. View the execution results and output for each step

## Security Considerations

- MacAssistant uses a rule-based system to identify potentially risky commands
- All risky commands require explicit user confirmation
- System commands are executed with the current user's permissions
- Command injection is prevented through proper input sanitization
- No sensitive data is stored or transmitted outside your machine

### Extending Functionality

To add new task patterns to the command generator:

1. Edit `backend/templates/command_templates.json` to add new templates
2. Update the `_process_patterns` method in `backend/modules/command_generator.py`

To add additional safety checks:

1. Edit `backend/templates/risky_patterns.json` to add new risky patterns
2. Update the `_check_dangerous_operations` method in `backend/modules/safety_checker.py`



## License

MIT License - See LICENSE file for details.

## Disclaimer

MacAssistant executes commands on your macOS system. While we implement numerous safety checks, please review all plans and commands carefully before execution, especially those marked as risky. The authors are not responsible for any data loss or system damage that may occur from using this software.
