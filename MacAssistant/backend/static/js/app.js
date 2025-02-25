/**
 * MacAssistant Frontend Application
 * Handles UI interactions, chat functionality, plan review, and command confirmation.
 */

// DOM Elements
const chatMessages = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const planReviewModal = document.getElementById('plan-review-modal');
const planSteps = document.getElementById('plan-steps');
const acceptPlanBtn = document.getElementById('accept-plan');
const rejectPlanBtn = document.getElementById('reject-plan');
const planFeedback = document.getElementById('plan-feedback');
const planFeedbackInput = document.getElementById('plan-feedback-input');
const submitFeedbackBtn = document.getElementById('submit-feedback');
const cancelFeedbackBtn = document.getElementById('cancel-feedback');
const riskyCommandModal = document.getElementById('risky-command-modal');
const riskyCommand = document.getElementById('risky-command');
const riskExplanation = document.getElementById('risk-explanation');
const confirmationInput = document.getElementById('confirmation-input');
const confirmCommandBtn = document.getElementById('confirm-command');
const cancelCommandBtn = document.getElementById('cancel-command');

// State
let currentPlan = null;
let currentCommand = null;

// Initialize Socket.IO
const socket = io();

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    // Add initial system message
    addMessage('Welcome to MacAssistant! How can I help you with your macOS tasks today?', 'assistant');
    
    // Chat form submission
    chatForm.addEventListener('submit', handleChatSubmit);
    
    // Plan review buttons
    acceptPlanBtn.addEventListener('click', handlePlanAccept);
    rejectPlanBtn.addEventListener('click', handlePlanReject);
    submitFeedbackBtn.addEventListener('click', handleFeedbackSubmit);
    cancelFeedbackBtn.addEventListener('click', handleFeedbackCancel);
    
    // Risky command buttons
    confirmCommandBtn.addEventListener('click', handleCommandConfirm);
    cancelCommandBtn.addEventListener('click', handleCommandCancel);
    confirmationInput.addEventListener('input', checkConfirmationInput);
    
    // Socket.IO events
    setupSocketEvents();
});

/**
 * Set up Socket.IO event listeners
 */
function setupSocketEvents() {
    // Connection and disconnection events
    socket.on('connect', () => {
        console.log('Connected to server');
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        addMessage('Connection lost. Trying to reconnect...', 'system');
    });
    
    // Execution updates
    socket.on('execution_update', (data) => {
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
                handlePlanCompleted(data);
                break;
            case 'plan_aborted':
                handlePlanAborted(data);
                break;
            case 'plan_revised':
                handlePlanRevised(data);
                break;
            default:
                // General status update
                updateExecutionStatus(data);
                break;
        }
    });
}

/**
 * Handle chat form submission
 * @param {Event} e - Form submit event
 */
function handleChatSubmit(e) {
    e.preventDefault();
    
    const message = chatInput.value.trim();
    if (!message) return;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Clear input
    chatInput.value = '';
    
    // Add typing indicator
    const typingIndicator = addMessage('Thinking...', 'system', 'typing-indicator');
    
    // Send request to server
    fetch('/api/task', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ request: message })
    })
    .then(response => response.json())
    .then(data => {
        // Remove typing indicator
        typingIndicator.remove();
        
        // Store the plan
        currentPlan = data.plan;
        
        // Display plan for review
        showPlanReview(data.plan);
    })
    .catch(error => {
        // Remove typing indicator
        typingIndicator.remove();
        
        console.error('Error:', error);
        addMessage('Sorry, there was an error processing your request. Please try again.', 'system');
    });
}

/**
 * Add a message to the chat
 * @param {string} text - Message text
 * @param {string} type - Message type ('user', 'assistant', 'system')
 * @param {string} [className] - Optional additional CSS class
 * @returns {HTMLElement} - The message element
 */
function addMessage(text, type, className = '') {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', `message-${type}`);
    if (className) {
        messageElement.classList.add(className);
    }
    
    messageElement.textContent = text;
    
    // Add timestamp
    const timestamp = document.createElement('span');
    timestamp.classList.add('timestamp');
    timestamp.textContent = new Date().toLocaleTimeString();
    messageElement.appendChild(timestamp);
    
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return messageElement;
}

/**
 * Add a message with command output
 * @param {string} text - Message text
 * @param {string} output - Command output
 * @param {boolean} isError - Whether the output is an error
 */
function addMessageWithOutput(text, output, isError = false) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-assistant');
    
    messageElement.textContent = text;
    
    // Create output block
    const outputElement = document.createElement('pre');
    outputElement.classList.add('output-block');
    if (isError) {
        outputElement.classList.add('error-text');
    }
    outputElement.textContent = output;
    messageElement.appendChild(outputElement);
    
    // Add timestamp
    const timestamp = document.createElement('span');
    timestamp.classList.add('timestamp');
    timestamp.textContent = new Date().toLocaleTimeString();
    messageElement.appendChild(timestamp);
    
    chatMessages.appendChild(messageElement);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Show the plan review modal
 * @param {Object} plan - The plan to review
 */
function showPlanReview(plan) {
    // Clear existing steps
    planSteps.innerHTML = '';
    
    // Add each step
    plan.steps.forEach((step, index) => {
        const stepElement = document.createElement('div');
        stepElement.classList.add('plan-step');
        
        const stepNumberElement = document.createElement('div');
        stepNumberElement.classList.add('step-number');
        stepNumberElement.textContent = step.number;
        
        const stepContentElement = document.createElement('div');
        stepContentElement.classList.add('step-content');
        
        const stepDescriptionElement = document.createElement('div');
        stepDescriptionElement.classList.add('step-description');
        
        // Add risky indicator if needed
        if (step.is_risky) {
            const riskyElement = document.createElement('span');
            riskyElement.classList.add('step-risky');
            riskyElement.textContent = 'RISKY';
            stepContentElement.appendChild(riskyElement);
        }
        
        stepDescriptionElement.textContent = step.description;
        stepContentElement.appendChild(stepDescriptionElement);
        
        stepElement.appendChild(stepNumberElement);
        stepElement.appendChild(stepContentElement);
        
        planSteps.appendChild(stepElement);
    });
    
    // Reset feedback elements
    planFeedback.classList.add('hidden');
    planFeedbackInput.value = '';
    
    // Show the modal
    planReviewModal.classList.add('show');
}

/**
 * Handle plan acceptance
 */
function handlePlanAccept() {
    // Hide the modal
    planReviewModal.classList.remove('show');
    
    // Show acceptance message
    addMessage('Plan accepted. Beginning execution...', 'system');
    
    // Send acceptance to server
    fetch('/api/plan/accept', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ plan_id: currentPlan.id })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Plan accepted:', data);
    })
    .catch(error => {
        console.error('Error accepting plan:', error);
        addMessage('Sorry, there was an error starting plan execution. Please try again.', 'system');
    });
}

/**
 * Handle plan rejection
 */
function handlePlanReject() {
    // Show feedback form
    planFeedback.classList.remove('hidden');
}

/**
 * Handle feedback submission
 */
function handleFeedbackSubmit() {
    const feedback = planFeedbackInput.value.trim();
    
    // Hide the modal
    planReviewModal.classList.remove('show');
    
    // Show rejection message
    if (feedback) {
        addMessage(`Plan rejected with feedback: "${feedback}"`, 'system');
    } else {
        addMessage('Plan rejected.', 'system');
    }
    
    // Send rejection to server
    fetch('/api/plan/reject', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            plan_id: currentPlan.id,
            feedback: feedback
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Plan rejected:', data);
        
        // If a revised plan was returned
        if (data.revised_plan) {
            // Store the revised plan
            currentPlan = data.revised_plan;
            
            // Show message about revision
            addMessage('I\'ve revised the plan based on your feedback.', 'assistant');
            
            // Display revised plan for review
            showPlanReview(data.revised_plan);
        }
    })
    .catch(error => {
        console.error('Error rejecting plan:', error);
        addMessage('Sorry, there was an error processing your feedback. Please try again.', 'system');
    });
}

/**
 * Handle feedback cancellation
 */
function handleFeedbackCancel() {
    // Hide feedback form
    planFeedback.classList.add('hidden');
}

/**
 * Handle risky command confirmation
 * @param {Object} data - Command data
 */
function handleRiskyCommand(data) {
    // Store current command
    currentCommand = data;
    
    // Set command text and explanation
    riskyCommand.textContent = data.command;
    
    // Get risk explanation (should come from server, using placeholder)
    riskExplanation.textContent = "This command could potentially modify or delete important files.";
    
    // Reset confirmation input
    confirmationInput.value = '';
    confirmCommandBtn.disabled = true;
    
    // Show the modal
    riskyCommandModal.classList.add('show');
    
    // Show message in chat
    addMessage(`Step ${data.step_index + 1} requires confirmation. Please review the command in the dialog.`, 'system');
}

/**
 * Check confirmation input to enable/disable confirm button
 */
function checkConfirmationInput() {
    confirmCommandBtn.disabled = confirmationInput.value !== 'YES';
}

/**
 * Handle command confirmation
 */
function handleCommandConfirm() {
    // Check if confirmation is valid
    if (confirmationInput.value !== 'YES') {
        return;
    }
    
    // Hide the modal
    riskyCommandModal.classList.remove('show');
    
    // Show confirmation message
    addMessage('Command confirmed. Executing...', 'system');
    
    // Send confirmation to server
    fetch('/api/command/confirm', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            command_id: currentCommand.command_id,
            confirmed: true
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Command confirmed:', data);
    })
    .catch(error => {
        console.error('Error confirming command:', error);
        addMessage('Sorry, there was an error confirming the command. Please try again.', 'system');
    });
}

/**
 * Handle command cancellation
 */
function handleCommandCancel() {
    // Hide the modal
    riskyCommandModal.classList.remove('show');
    
    // Show cancellation message
    addMessage('Command cancelled.', 'system');
    
    // Send cancellation to server
    fetch('/api/command/confirm', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ 
            command_id: currentCommand.command_id,
            confirmed: false
        })
    })
    .then(response => response.json())
    .then(data => {
        console.log('Command cancelled:', data);
    })
    .catch(error => {
        console.error('Error cancelling command:', error);
        addMessage('Sorry, there was an error cancelling the command. Please try again.', 'system');
    });
}

/**
 * Handle step completion
 * @param {Object} data - Step data
 */
function handleStepCompleted(data) {
    const stepIndex = data.step_index;
    const stdout = data.stdout.trim();
    const stderr = data.stderr.trim();
    
    // Show completion message
    const stepNumber = stepIndex + 1;
    addMessage(`Step ${stepNumber} completed successfully.`, 'assistant');
    
    // Show output if any
    if (stdout) {
        addMessageWithOutput('Output:', stdout);
    }
    
    // Show stderr if any (as a warning, not an error)
    if (stderr) {
        addMessageWithOutput('Additional output:', stderr, false);
    }
}

/**
 * Handle step failure
 * @param {Object} data - Step data
 */
function handleStepFailed(data) {
    const stepIndex = data.step_index;
    const stdout = data.stdout.trim();
    const stderr = data.stderr.trim();
    
    // Show failure message
    const stepNumber = stepIndex + 1;
    addMessage(`Step ${stepNumber} failed.`, 'system');
    
    // Show output if any
    if (stdout) {
        addMessageWithOutput('Output:', stdout);
    }
    
    // Show error
    if (stderr) {
        addMessageWithOutput('Error:', stderr, true);
    } else {
        addMessageWithOutput('Error:', 'Unknown error occurred', true);
    }
}

/**
 * Handle plan completion
 */
function handlePlanCompleted() {
    addMessage('All steps completed successfully!', 'assistant');
}

/**
 * Handle plan abortion
 */
function handlePlanAborted() {
    addMessage('Plan execution was aborted.', 'system');
}

/**
 * Handle plan revision
 * @param {Object} data - Revision data
 */
function handlePlanRevised(data) {
    addMessage('Plan has been revised based on execution results.', 'system');
}

/**
 * Update execution status in the UI
 * @param {Object} data - Status update data
 */
function updateExecutionStatus(data) {
    // This function could update a progress indicator or status display
    console.log('Status update:', data);
}