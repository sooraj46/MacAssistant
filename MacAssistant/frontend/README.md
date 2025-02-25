# MacAssistant Frontend

This is the React-based frontend for MacAssistant, an intelligent task automation assistant for macOS. The frontend provides a modern chatbot interface for interacting with the MacAssistant backend.

## Features

- Clean, modern chatbot UI
- Real-time updates using WebSockets
- Markdown support for rich message formatting
- Light and dark theme support
- Plan review with accept/reject workflow
- Risky command confirmation modal
- Responsive design for all screen sizes

## Getting Started

### Prerequisites

- Node.js 16+ and npm

### Installation

1. Install dependencies:
   ```bash
   npm install
   ```

2. Start the development server:
   ```bash
   npm start
   ```

3. The app will be available at:
   ```
   http://localhost:3000
   ```

## Project Structure

```
frontend/
├── public/                # Public assets
│   ├── index.html        # HTML template
│   └── manifest.json     # Web app manifest
├── src/                   # Source code
│   ├── components/       # React components
│   │   ├── ChatContainer.js
│   │   ├── ChatInput.js
│   │   ├── Header.js
│   │   ├── Message.js
│   │   ├── MessageList.js
│   │   ├── PlanReviewModal.js
│   │   └── RiskyCommandModal.js
│   ├── styles/           # Styling
│   │   ├── GlobalStyle.js
│   │   └── theme.js
│   ├── App.js            # Main application component
│   └── index.js          # Entry point
└── package.json          # Dependencies and scripts
```

## Building for Production

To build the app for production:

```bash
npm run build
```

This will create an optimized production build in the `build` folder, which can be served by the backend Flask server.

## Configuration

The app is configured to proxy API requests to the backend server running at `http://localhost:5000`. You can change this in the `package.json` file:

```json
"proxy": "http://localhost:5000"
```

For production deployment, you may need to configure the WebSocket connection URL. This can be done by setting the `REACT_APP_BACKEND_URL` environment variable.

## Features

### Chat Interface

The chat interface supports different message types:
- User messages (right-aligned)
- Assistant messages (left-aligned)
- System messages (centered)

Messages can include command outputs, which are displayed in a code block format.

### Plan Review

When a task is requested, the backend generates a plan that is presented to the user for review. The user can:
- Accept the plan to begin execution
- Reject the plan and provide feedback for revision

### Risky Command Confirmation

When a potentially risky command is detected, the user is prompted to confirm execution. The user must type "YES" to proceed.

## Development

### Adding New Components

To add a new component:

1. Create a new file in the `src/components` directory
2. Import and use the component in the appropriate parent component
3. Use styled-components for styling

### Theme Customization

The app supports light and dark themes. You can customize these themes in the `src/styles/theme.js` file.

## License

This project is licensed under the MIT License - see the LICENSE file for details.