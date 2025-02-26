import React, { useState, useEffect } from 'react';
import { io } from 'socket.io-client';
import styled, { ThemeProvider } from 'styled-components';
import ChatContainer from './components/ChatContainer';
import PlanReviewModal from './components/PlanReviewModal';
import RiskyCommandModal from './components/RiskyCommandModal';
import GlobalStyle from './styles/GlobalStyle';
import { lightTheme, darkTheme } from './styles/theme';
import Header from './components/Header';
import axios from 'axios';

// Initialize socket connection
const socket = io(process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000');

function App() {
  const [theme, setTheme] = useState('light');
  const [messages, setMessages] = useState([
    { id: 1, content: 'Hi! I\'m MacAssistant. How can I help you with your macOS tasks today?', type: 'assistant', timestamp: new Date() }
  ]);
  const [showPlanReview, setShowPlanReview] = useState(false);
  const [showRiskyCommand, setShowRiskyCommand] = useState(false);
  const [currentPlan, setCurrentPlan] = useState(null);
  const [currentCommand, setCurrentCommand] = useState(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [feedbackText, setFeedbackText] = useState('');
  
  // Toggle theme
  const toggleTheme = () => {
    setTheme(theme === 'light' ? 'dark' : 'light');
  };
  
  // Socket.io event listeners
  useEffect(() => {
    socket.on('connect', () => {
      console.log('Connected to server');
    });
    
    socket.on('disconnect', () => {
      console.log('Disconnected from server');
      addMessage('Connection lost. Trying to reconnect...', 'system');
    });
    
    socket.on('execution_update', handleExecutionUpdate);
    
    return () => {
      socket.off('execution_update');
      socket.off('connect');
      socket.off('disconnect');
    };
  }, []);
  
  // Handle execution updates from server
  const handleExecutionUpdate = (data) => {
    console.log('Execution update:', data);
    
    // Handle different event types
    switch (data.event) {
      case 'step_completed':
        handleStepCompleted(data);
        break;
      case 'step_failed':
        handleStepFailed(data);
        break;
      case 'risky_command':
        handleRiskyCommand(data);
        break;
      case 'plan_completed':
        addMessage('All steps completed successfully!', 'assistant');
        break;
      case 'plan_aborted':
        addMessage('Plan execution was aborted.', 'system');
        break;
      case 'plan_revised':
        addMessage('Plan has been revised based on execution results.', 'system');
        
        // Get the revised plan ID from the event data
        const revisedPlanId = data.revised_plan_id;
        
        // If we have a revised plan ID, fetch the plan details
        if (revisedPlanId) {
          const apiUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
          try {
            // Fetch the revised plan details with the full URL
            axios.get(`${apiUrl}/api/plan/${revisedPlanId}`).then(response => {
              // Update the current plan with the revised one
              setCurrentPlan(response.data.plan);
              
              // Show the plan review modal
              setShowPlanReview(true);
            }).catch(error => {
              console.error('Error fetching revised plan:', error);
              addMessage('Error fetching the revised plan details.', 'system');
            });
          } catch (error) {
            console.error('Error fetching revised plan:', error);
            addMessage('Error fetching the revised plan details.', 'system');
          }
        }
        break;
      default:
        // General status update
        console.log('Status update:', data);
        break;
    }
  };
  
  // Add message to chat
  const addMessage = (content, type, output = null, isError = false) => {
    const newMessage = {
      id: Date.now(),
      content,
      type,
      timestamp: new Date(),
      output,
      isError
    };
    
    setMessages(prevMessages => [...prevMessages, newMessage]);
  };
  
  // Handle user message submission
  const handleSendMessage = async (text) => {
    // Add user message to chat
    addMessage(text, 'user');
    
    // Add typing indicator
    addMessage('Thinking...', 'system');
    
    try {
      const apiUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
      // Send request to server
      const response = await axios.post(`${apiUrl}/api/task`, { request: text });
      
      // Remove typing indicator
      setMessages(prev => prev.filter(message => message.content !== 'Thinking...'));
      
      // Store the plan
      setCurrentPlan(response.data.plan);
      
      // Show plan review modal
      setShowPlanReview(true);
    } catch (error) {
      // Remove typing indicator
      setMessages(prev => prev.filter(message => message.content !== 'Thinking...'));
      
      console.error('Error:', error);
      addMessage('Sorry, there was an error processing your request. Please try again.', 'system');
    }
  };
  
  // Handle plan acceptance
  const handlePlanAccept = async () => {
    // Hide modal
    setShowPlanReview(false);
    
    // Show acceptance message
    addMessage('Plan accepted. Beginning execution...', 'system');
    
    try {
      const apiUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
      // Send acceptance to server
      await axios.post(`${apiUrl}/api/plan/accept`, { plan_id: currentPlan.id });
    } catch (error) {
      console.error('Error accepting plan:', error);
      addMessage('Sorry, there was an error starting plan execution. Please try again.', 'system');
    }
  };
  
  // Handle plan rejection
  const handlePlanReject = () => {
    setShowFeedback(true);
  };
  
  // Handle feedback submission
  const handleFeedbackSubmit = async () => {
    // Hide modal
    setShowPlanReview(false);
    setShowFeedback(false);
    
    // Show rejection message
    if (feedbackText) {
      addMessage(`Plan rejected with feedback: "${feedbackText}"`, 'system');
    } else {
      addMessage('Plan rejected.', 'system');
    }
    
    try {
      const apiUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
      // Send rejection to server
      const response = await axios.post(`${apiUrl}/api/plan/reject`, { 
        plan_id: currentPlan.id,
        feedback: feedbackText
      });
      
      // If revised plan was returned
      if (response.data.revised_plan) {
        // Store the revised plan
        setCurrentPlan(response.data.revised_plan);
        
        // Show message about revision
        addMessage('I\'ve revised the plan based on your feedback.', 'assistant');
        
        // Show revised plan for review
        setShowPlanReview(true);
      }
      
      // Reset feedback
      setFeedbackText('');
    } catch (error) {
      console.error('Error rejecting plan:', error);
      addMessage('Sorry, there was an error processing your feedback. Please try again.', 'system');
    }
  };
  
  // Handle feedback cancellation
  const handleFeedbackCancel = () => {
    setShowFeedback(false);
  };
  
  // Handle risky command confirmation
  const handleCommandConfirm = async () => {
    // Hide modal
    setShowRiskyCommand(false);
    
    // Show confirmation message
    addMessage('Command confirmed. Executing...', 'system');
    
    try {
      const apiUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
      // Send confirmation to server
      await axios.post(`${apiUrl}/api/command/confirm`, { 
        command_id: currentCommand.command_id,
        confirmed: true
      });
    } catch (error) {
      console.error('Error confirming command:', error);
      addMessage('Sorry, there was an error confirming the command. Please try again.', 'system');
    }
  };
  
  // Handle command cancellation
  const handleCommandCancel = async () => {
    // Hide modal
    setShowRiskyCommand(false);
    
    // Show cancellation message
    addMessage('Command cancelled.', 'system');
    
    try {
      const apiUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:5000';
      // Send cancellation to server
      await axios.post(`${apiUrl}/api/command/confirm`, { 
        command_id: currentCommand.command_id,
        confirmed: false
      });
    } catch (error) {
      console.error('Error cancelling command:', error);
      addMessage('Sorry, there was an error cancelling the command. Please try again.', 'system');
    }
  };
  
  // Handle step completion
  const handleStepCompleted = (data) => {
    const stepIndex = data.step_index;
    const stdout = data.stdout.trim();
    const stderr = data.stderr.trim();
    
    // Show completion message
    const stepNumber = stepIndex + 1;
    addMessage(`Step ${stepNumber} completed successfully.`, 'assistant');
    
    // Show output if any
    if (stdout) {
      addMessage('Output:', 'assistant', stdout);
    }
    
    // Show stderr if any (as a warning, not an error)
    if (stderr) {
      addMessage('Additional output:', 'assistant', stderr);
    }
  };
  
  // Handle step failure
  const handleStepFailed = (data) => {
    const stepIndex = data.step_index;
    const stdout = data.stdout.trim();
    const stderr = data.stderr.trim();
    
    // Show failure message
    const stepNumber = stepIndex + 1;
    addMessage(`Step ${stepNumber} failed.`, 'system');
    
    // Show output if any
    if (stdout) {
      addMessage('Output:', 'assistant', stdout);
    }
    
    // Show error
    if (stderr) {
      addMessage('Error:', 'system', stderr, true);
    } else {
      addMessage('Error:', 'system', 'Unknown error occurred', true);
    }
  };
  
  // Handle risky command
  const handleRiskyCommand = (data) => {
    // Store current command
    setCurrentCommand(data);
    
    // Show message in chat
    addMessage(`Step ${data.step_index + 1} requires confirmation. Please review the command in the dialog.`, 'system');
    
    // Show risky command modal
    setShowRiskyCommand(true);
  };
  
  return (
    <ThemeProvider theme={theme === 'light' ? lightTheme : darkTheme}>
      <GlobalStyle />
      <AppContainer>
        <Header toggleTheme={toggleTheme} theme={theme} />
        <MainContent>
          <ChatContainer 
            messages={messages} 
            onSendMessage={handleSendMessage} 
          />
        </MainContent>
        
        {showPlanReview && (
          <PlanReviewModal 
            plan={currentPlan}
            onAccept={handlePlanAccept}
            onReject={handlePlanReject}
            showFeedback={showFeedback}
            feedbackText={feedbackText}
            onFeedbackChange={(e) => setFeedbackText(e.target.value)}
            onFeedbackSubmit={handleFeedbackSubmit}
            onFeedbackCancel={handleFeedbackCancel}
          />
        )}
        
        {showRiskyCommand && (
          <RiskyCommandModal 
            command={currentCommand.command}
            explanation="This command could potentially modify or delete important files."
            onConfirm={handleCommandConfirm}
            onCancel={handleCommandCancel}
          />
        )}
      </AppContainer>
    </ThemeProvider>
  );
}

const AppContainer = styled.div`
  display: flex;
  flex-direction: column;
  height: 100vh;
  max-width: 100%;
  overflow: hidden;
`;

const MainContent = styled.main`
  flex: 1;
  overflow: hidden;
  padding: 0 20px;
  display: flex;
  flex-direction: column;
`;

export default App;