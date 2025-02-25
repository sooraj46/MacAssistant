# Contributing to MacAssistant

Thank you for considering contributing to MacAssistant! This document outlines the process for contributing to the project.

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone.

## How Can I Contribute?

### Reporting Bugs

- Check if the bug has already been reported in the Issues section
- If not, create a new issue with a clear title and description
- Include steps to reproduce the bug
- Describe the expected behavior vs the actual behavior
- Include screenshots if applicable

### Suggesting Enhancements

- Check if the enhancement has already been suggested in the Issues section
- If not, create a new issue with a clear title and description
- Explain why this enhancement would be useful

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes with clear commit messages
4. Update documentation as needed
5. Submit a pull request

## Development Setup

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/MacAssistant.git
   cd MacAssistant
   ```

2. Set up the development environment:
   ```
   ./start-dev.sh
   ```

3. Create a `.env` file based on the `.env.example` template.

## Project Structure

- `backend/`: Flask backend server
  - `app.py`: Main application entry point
  - `modules/`: Backend modules
  - `templates/`: HTML templates
  - `static/`: Static assets

- `frontend/`: React frontend
  - `src/components/`: React components
  - `src/styles/`: Styling
  - `public/`: Public assets

## Coding Guidelines

- Follow existing code style and patterns
- Write clear, descriptive commit messages
- Add comments for complex sections of code
- Write tests for new features

## License

By contributing to MacAssistant, you agree that your contributions will be licensed under the project's MIT License.