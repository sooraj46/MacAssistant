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

// Initialize Socket.IO with reconnection options
const socket = io({
    reconnection: true,
    reconnectionAttempts: 5,
    reconnectionDelay: 1000,
    reconnectionDelayMax: 5000,
    timeout: 20000
});

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
    // Connection events
    socket.on('connect', () => {
        console.log('Connected to server');
        addMessage('Connected to server', 'system');
    });
    
    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        addMessage('Error connecting to server. Please check your connection.', 'system');
    });
    
    socket.on('connect_timeout', () => {
        console.error('Connection timeout');
        addMessage('Connection timeout. Please check your connection.', 'system');
    });
    
    socket.on('reconnect', (attemptNumber) => {
        console.log('Reconnected to server after', attemptNumber, 'attempts');
        addMessage('Reconnected to server', 'system');
    });
    
    socket.on('reconnect_attempt', (attemptNumber) => {
        console.log('Trying to reconnect:', attemptNumber);
    });
    
    socket.on('reconnect_error', (error) => {
        console.error('Reconnection error:', error);
    });
    
    socket.on('reconnect_failed', () => {
        console.error('Failed to reconnect');
        addMessage('Failed to reconnect to server. Please refresh the page.', 'system');
    });
    
    socket.on('disconnect', (reason) => {
        console.log('Disconnected from server:', reason);
        if (reason === 'io server disconnect') {
            // Server disconnected us, need to reconnect manually
            socket.connect();
            addMessage('Disconnected from server. Trying to reconnect...', 'system');
        } else {
            // Socket automatically tries to reconnect
            addMessage('Connection lost. Trying to reconnect...', 'system');
        }
    });
    
    // Connection status confirmation from server
    socket.on('connection_status', (data) => {
        console.log('Connection status:', data);
    });
    
    // Execution updates
    socket.on('execution_update', (data) => {
        console.log('Execution update:', data);
        
        try {
            // Make sure we have valid data
            if (!data || !data.event) {
                console.error('Invalid execution update data:', data);
                return;
            }
            
            // Handle different event types
            switch (data.event) {
                case 'step_completed':
                    handleStepCompleted(data);
                    break;
                case 'step_completed_feedback':
                    handleStepCompletedFeedback(data);
                    break;
                case 'step_failed':
                    handleStepFailed(data);
                    break;
                case 'step_failure_options':
                    handleStepFailureOptions(data);
                    break;
                case 'user_confirmation_required':
                    handleUserConfirmationRequired(data);
                    break;
                case 'command_rejected':
                    handleCommandRejected(data);
                    break;
                case 'command_rejection_options':
                    handleCommandRejectionOptions(data);
                    break;
                case 'plan_completed':
                    handlePlanCompleted(data);
                    break;
                case 'plan_aborted':
                    handlePlanAborted(data);
                    break;
                case 'plan_paused':
                    handlePlanPaused(data);
                    break;
                case 'observation_required':
                    handleObservationRequired(data);
                    break;
                case 'plan_revised':
                    handlePlanRevised(data);
                    break;
                case 'execution_update':
                    handleExecutionUpdate(data);
                    break;
                default:
                    // General status update
                    updateExecutionStatus(data);
                    break;
            }
        } catch (error) {
            console.error('Error handling execution update:', error);
            addMessage('Error processing server update. Please try again.', 'system');
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
    .then(response => {
        if (!response.ok) {
            // Handle HTTP errors
            return response.json().then(errorData => {
                throw new Error(errorData.error || `HTTP error ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        // Remove typing indicator
        typingIndicator.remove();
        
        if (!data.plan) {
            throw new Error('No plan received from server');
        }
        
        // Store the plan
        currentPlan = data.plan;
        
        // Display plan for review
        showPlanReview(data.plan);
    })
    .catch(error => {
        // Remove typing indicator
        typingIndicator.remove();
        
        console.error('Error:', error);
        addMessage(`Sorry, there was an error processing your request: ${error.message}. Please try again.`, 'system');
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
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error ${response.status}`);
        }
        return response.json();
    })
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
    
    // Add revise plan option
    addRevisionOption(data);
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
    
    // Update the current plan if provided
    if (data.revised_plan) {
        currentPlan = data.revised_plan;
        
        // Show the changes made in the revision
        if (data.revision_summary) {
            addMessage(`Revision summary: ${data.revision_summary}`, 'assistant');
        }
        
        // If the plan is not already executing, show it for review
        if (data.requires_review) {
            addMessage('Please review the revised plan:', 'assistant');
            showPlanReview(data.revised_plan);
        } else {
            addMessage('Continuing execution with the revised plan...', 'system');
        }
    }
}

/**
 * Handle step completion with feedback request
 * @param {Object} data - Step data with verification
 */
function handleStepCompletedFeedback(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    const description = data.description;
    const stdout = data.stdout?.trim() || '';
    const explanation = data.explanation || 'Step completed successfully.';
    
    // Add message with verification result from LLM
    addMessage(`Step ${stepNumber} completed: ${explanation}`, 'assistant');
    
    // Show output if any
    if (stdout) {
        addMessageWithOutput('Output:', stdout);
    }
    
    // If we should not continue automatically, add feedback options
    if (!data.continue_automatically) {
        addStepFeedbackOption(data);
    }
}

/**
 * Handle step failure options
 * @param {Object} data - Step data with verification
 */
function handleStepFailureOptions(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    const verification = data.verification || {};
    const suggestion = data.suggestion || '';
    
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'failure-options');
    
    const messageText = document.createElement('p');
    messageText.textContent = 'How would you like to proceed with this failed step?';
    messageElement.appendChild(messageText);
    
    if (suggestion) {
        const suggestionText = document.createElement('p');
        suggestionText.classList.add('suggestion');
        suggestionText.textContent = `Suggestion: ${suggestion}`;
        messageElement.appendChild(suggestionText);
    }
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const reviseButton = document.createElement('button');
    reviseButton.classList.add('btn', 'btn-primary');
    reviseButton.textContent = 'Revise Plan';
    reviseButton.addEventListener('click', () => {
        messageElement.remove();
        requestPlanRevision({
            step_index: stepIndex,
            stdout: data.stdout || '',
            stderr: data.stderr || ''
        });
    });
    
    const skipButton = document.createElement('button');
    skipButton.classList.add('btn', 'btn-secondary');
    skipButton.textContent = 'Skip & Continue';
    skipButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Request to continue execution, skipping this step
        fetch('/api/plan/continue', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id,
                skip_failed_step: true
            })
        })
        .then(() => {
            addMessage(`Skipping step ${stepNumber} and continuing...`, 'system');
        })
        .catch(error => {
            console.error('Error continuing plan:', error);
        });
    });
    
    const abortButton = document.createElement('button');
    abortButton.classList.add('btn', 'btn-danger');
    abortButton.textContent = 'Abort Plan';
    abortButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Request to abort the plan
        fetch('/api/plan/abort', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id
            })
        })
        .then(() => {
            addMessage('Plan execution aborted.', 'system');
        })
        .catch(error => {
            console.error('Error aborting plan:', error);
        });
    });
    
    buttonContainer.appendChild(reviseButton);
    buttonContainer.appendChild(skipButton);
    buttonContainer.appendChild(abortButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Handle user confirmation requirement
 * @param {Object} data - Command and step data
 */
function handleUserConfirmationRequired(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    const command = data.command;
    const description = data.description;
    const commandId = data.command_id;
    
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'confirmation-required');
    
    const messageText = document.createElement('p');
    messageText.textContent = `Step ${stepNumber} requires your confirmation before execution:`;
    messageElement.appendChild(messageText);
    
    const descriptionText = document.createElement('p');
    descriptionText.classList.add('step-description');
    descriptionText.textContent = description;
    messageElement.appendChild(descriptionText);
    
    const commandCode = document.createElement('pre');
    commandCode.classList.add('command-code');
    commandCode.textContent = command;
    messageElement.appendChild(commandCode);
    
    const feedbackContainer = document.createElement('div');
    feedbackContainer.classList.add('feedback-container');
    
    const feedbackLabel = document.createElement('label');
    feedbackLabel.textContent = 'Optional feedback:';
    feedbackContainer.appendChild(feedbackLabel);
    
    const feedbackInput = document.createElement('input');
    feedbackInput.type = 'text';
    feedbackInput.placeholder = 'Enter feedback or suggestions...';
    feedbackContainer.appendChild(feedbackInput);
    
    messageElement.appendChild(feedbackContainer);
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const confirmButton = document.createElement('button');
    confirmButton.classList.add('btn', 'btn-primary');
    confirmButton.textContent = 'Approve & Execute';
    confirmButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Send confirmation to server
        fetch('/api/command/confirm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command_id: commandId,
                confirmed: true,
                feedback: feedbackInput.value.trim()
            })
        })
        .then(() => {
            addMessage(`Executing command: ${command}`, 'system');
        })
        .catch(error => {
            console.error('Error confirming command:', error);
        });
    });
    
    const rejectButton = document.createElement('button');
    rejectButton.classList.add('btn', 'btn-danger');
    rejectButton.textContent = 'Reject Command';
    rejectButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Send rejection to server
        fetch('/api/command/confirm', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command_id: commandId,
                confirmed: false,
                feedback: feedbackInput.value.trim()
            })
        })
        .then(() => {
            addMessage(`Command rejected: ${command}`, 'system');
        })
        .catch(error => {
            console.error('Error rejecting command:', error);
        });
    });
    
    buttonContainer.appendChild(confirmButton);
    buttonContainer.appendChild(rejectButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Handle command rejection
 * @param {Object} data - Rejection data
 */
function handleCommandRejected(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    const feedback = data.feedback;
    
    addMessage(`Step ${stepNumber} command was rejected.${feedback ? ` Feedback: ${feedback}` : ''}`, 'system');
}

/**
 * Handle command rejection options
 * @param {Object} data - Rejection data
 */
function handleCommandRejectionOptions(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'rejection-options');
    
    const messageText = document.createElement('p');
    messageText.textContent = 'How would you like to proceed after rejecting this command?';
    messageElement.appendChild(messageText);
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const reviseButton = document.createElement('button');
    reviseButton.classList.add('btn', 'btn-primary');
    reviseButton.textContent = 'Revise Plan';
    reviseButton.addEventListener('click', () => {
        messageElement.remove();
        requestPlanRevision({
            step_index: stepIndex,
            stderr: `Command was rejected by user${data.feedback ? `: ${data.feedback}` : ''}`
        });
    });
    
    const continueButton = document.createElement('button');
    continueButton.classList.add('btn', 'btn-secondary');
    continueButton.textContent = 'Skip & Continue';
    continueButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Request to continue execution, skipping this step
        fetch('/api/plan/continue', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id,
                skip_failed_step: true
            })
        })
        .then(() => {
            addMessage(`Skipping step ${stepNumber} and continuing with the plan...`, 'system');
        })
        .catch(error => {
            console.error('Error continuing plan:', error);
        });
    });
    
    const abortButton = document.createElement('button');
    abortButton.classList.add('btn', 'btn-danger');
    abortButton.textContent = 'Abort Plan';
    abortButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Request to abort the plan
        fetch('/api/plan/abort', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id
            })
        })
        .then(() => {
            addMessage('Plan execution aborted.', 'system');
        })
        .catch(error => {
            console.error('Error aborting plan:', error);
        });
    });
    
    buttonContainer.appendChild(reviseButton);
    buttonContainer.appendChild(continueButton);
    buttonContainer.appendChild(abortButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Handle execution status update
 * @param {Object} data - Status data
 */
function handleExecutionUpdate(data) {
    const status_update = data.status || 'No status update provided.';
      
    // For example, show the summary in the chat:
    addMessage(`Progress Update:\n${status_update}`, 'assistant');
  
  }

/**
 * Handle plan paused state
 * @param {Object} data - Pause data
 */
function handlePlanPaused(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    const reason = data.reason || 'User requested pause';
    
    addMessage(`Plan execution paused after step ${stepNumber}. ${reason}`, 'system');
    
    // Add option to continue
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'pause-options');
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const continueButton = document.createElement('button');
    continueButton.classList.add('btn', 'btn-primary');
    continueButton.textContent = 'Continue Execution';
    continueButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Request to continue execution
        fetch('/api/plan/continue', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id,
                skip_failed_step: false
            })
        })
        .then(() => {
            addMessage('Continuing plan execution...', 'system');
        })
        .catch(error => {
            console.error('Error continuing plan:', error);
        });
    });
    
    const reviseButton = document.createElement('button');
    reviseButton.classList.add('btn', 'btn-secondary');
    reviseButton.textContent = 'Revise Plan';
    reviseButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Get user feedback for revision
        const feedbackPrompt = document.createElement('div');
        feedbackPrompt.classList.add('message', 'message-system', 'feedback-prompt');
        
        const promptText = document.createElement('p');
        promptText.textContent = 'Please provide feedback for plan revision:';
        feedbackPrompt.appendChild(promptText);
        
        const feedbackInput = document.createElement('textarea');
        feedbackInput.rows = 3;
        feedbackInput.placeholder = 'Enter your feedback or instructions for plan revision...';
        feedbackPrompt.appendChild(feedbackInput);
        
        const submitButton = document.createElement('button');
        submitButton.classList.add('btn', 'btn-primary');
        submitButton.textContent = 'Submit Feedback';
        submitButton.addEventListener('click', () => {
            const feedback = feedbackInput.value.trim();
            if (feedback) {
                feedbackPrompt.remove();
                
                // Request plan revision with feedback
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
                    if (data.revised_plan) {
                        addMessage('Revising plan based on your feedback...', 'system');
                    } else {
                        addMessage('Failed to revise plan. Please try again.', 'system');
                    }
                })
                .catch(error => {
                    console.error('Error revising plan:', error);
                    addMessage('Error revising plan. Please try again.', 'system');
                });
            }
        });
        
        feedbackPrompt.appendChild(submitButton);
        chatMessages.appendChild(feedbackPrompt);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        feedbackInput.focus();
    });
    
    const abortButton = document.createElement('button');
    abortButton.classList.add('btn', 'btn-danger');
    abortButton.textContent = 'Abort Plan';
    abortButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Request to abort the plan
        fetch('/api/plan/abort', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id
            })
        })
        .then(() => {
            addMessage('Plan execution aborted.', 'system');
        })
        .catch(error => {
            console.error('Error aborting plan:', error);
        });
    });
    
    buttonContainer.appendChild(continueButton);
    buttonContainer.appendChild(reviseButton);
    buttonContainer.appendChild(abortButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Handle observation required event
 * @param {Object} data - Observation data
 */
function handleObservationRequired(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    const description = data.description;
    const stdout = data.stdout || '';
    
    // Add message about observation
    addMessage(`Step ${stepNumber} requires your observation: ${description}`, 'assistant');
    
    // Show output if any
    if (stdout) {
        addMessageWithOutput('Output:', stdout);
    }
    
    // Add observation feedback form
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'observation-required');
    
    const messageText = document.createElement('p');
    messageText.textContent = 'Please make the observation and provide any feedback:';
    messageElement.appendChild(messageText);
    
    const feedbackInput = document.createElement('textarea');
    feedbackInput.rows = 3;
    feedbackInput.placeholder = 'Enter your observations or feedback...';
    messageElement.appendChild(feedbackInput);
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const completeButton = document.createElement('button');
    completeButton.classList.add('btn', 'btn-primary');
    completeButton.textContent = 'Complete Observation';
    completeButton.addEventListener('click', () => {
        const feedback = feedbackInput.value.trim();
        messageElement.remove();
        
        // Send observation completion to server
        fetch('/api/step/observation', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id,
                step_index: stepIndex,
                feedback: feedback
            })
        })
        .then(() => {
            addMessage(`Observation completed${feedback ? ': ' + feedback : '.'}`, 'system');
        })
        .catch(error => {
            console.error('Error completing observation:', error);
        });
    });
    
    buttonContainer.appendChild(completeButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    feedbackInput.focus();
}

/**
 * Add step feedback option
 * @param {Object} data - Step data
 */
function addStepFeedbackOption(data) {
    const stepIndex = data.step_index;
    const stepNumber = stepIndex + 1;
    
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'step-feedback');
    
    const messageText = document.createElement('p');
    messageText.textContent = `How would you like to proceed after step ${stepNumber}?`;
    messageElement.appendChild(messageText);
    
    const feedbackInput = document.createElement('input');
    feedbackInput.type = 'text';
    feedbackInput.placeholder = 'Optional feedback...';
    messageElement.appendChild(feedbackInput);
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const continueButton = document.createElement('button');
    continueButton.classList.add('btn', 'btn-primary');
    continueButton.textContent = 'Continue';
    continueButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Send feedback and continue
        fetch('/api/step/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id,
                step_index: stepIndex,
                feedback: feedbackInput.value.trim(),
                continue_execution: true
            })
        })
        .then(() => {
            if (feedbackInput.value.trim()) {
                addMessage(`Continuing with feedback: ${feedbackInput.value.trim()}`, 'system');
            } else {
                addMessage('Continuing to next step...', 'system');
            }
        })
        .catch(error => {
            console.error('Error sending feedback:', error);
        });
    });
    
    const pauseButton = document.createElement('button');
    pauseButton.classList.add('btn', 'btn-secondary');
    pauseButton.textContent = 'Pause Execution';
    pauseButton.addEventListener('click', () => {
        messageElement.remove();
        
        // Send feedback and pause
        fetch('/api/step/feedback', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                plan_id: currentPlan.id,
                step_index: stepIndex,
                feedback: feedbackInput.value.trim(),
                continue_execution: false
            })
        })
        .then(() => {
            addMessage('Pausing execution. You can continue or revise the plan when ready.', 'system');
        })
        .catch(error => {
            console.error('Error sending feedback:', error);
        });
    });
    
    const reviseButton = document.createElement('button');
    reviseButton.classList.add('btn', 'btn-danger');
    reviseButton.textContent = 'Revise Plan';
    reviseButton.addEventListener('click', () => {
        messageElement.remove();
        
        const feedback = feedbackInput.value.trim() || 'User requested revision after step completion';
        
        // Request plan revision
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
            addMessage('Requesting plan revision...', 'system');
            if (data.revised_plan) {
                currentPlan = data.revised_plan;
                showPlanReview(data.revised_plan);
            }
        })
        .catch(error => {
            console.error('Error revising plan:', error);
        });
    });
    
    buttonContainer.appendChild(continueButton);
    buttonContainer.appendChild(pauseButton);
    buttonContainer.appendChild(reviseButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Update execution status in the UI
 * @param {Object} data - Status update data
 */
function updateExecutionStatus(data) {
    // This function could update a progress indicator or status display
    console.log('Status update:', data);
}

/**
 * Add revision option when a step fails
 * @param {Object} data - The step data that failed
 */
function addRevisionOption(data) {
    const messageElement = document.createElement('div');
    messageElement.classList.add('message', 'message-system', 'revision-option');
    
    const messageText = document.createElement('p');
    messageText.textContent = 'Would you like to revise the plan to handle this error?';
    messageElement.appendChild(messageText);
    
    const buttonContainer = document.createElement('div');
    buttonContainer.classList.add('button-container');
    
    const reviseButton = document.createElement('button');
    reviseButton.classList.add('btn', 'btn-primary');
    reviseButton.textContent = 'Revise Plan';
    reviseButton.addEventListener('click', () => requestPlanRevision(data));
    
    const continueButton = document.createElement('button');
    continueButton.classList.add('btn', 'btn-secondary');
    continueButton.textContent = 'Continue Without Revision';
    continueButton.addEventListener('click', () => {
        messageElement.remove();
        addMessage('Continuing with the remaining steps...', 'system');
        
        // Notify server to continue without revision
        fetch('/api/plan/continue', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                plan_id: currentPlan.id,
                skip_failed_step: true
            })
        })
        .catch(error => {
            console.error('Error continuing plan:', error);
        });
    });
    
    const abortButton = document.createElement('button');
    abortButton.classList.add('btn', 'btn-danger');
    abortButton.textContent = 'Abort Plan';
    abortButton.addEventListener('click', () => {
        messageElement.remove();
        addMessage('Plan execution aborted.', 'system');
        
        // Notify server to abort plan
        fetch('/api/plan/abort', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ plan_id: currentPlan.id })
        })
        .catch(error => {
            console.error('Error aborting plan:', error);
        });
    });
    
    buttonContainer.appendChild(reviseButton);
    buttonContainer.appendChild(continueButton);
    buttonContainer.appendChild(abortButton);
    messageElement.appendChild(buttonContainer);
    
    chatMessages.appendChild(messageElement);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

/**
 * Request a plan revision after a step failure
 * @param {Object} data - The step data that failed
 */
function requestPlanRevision(data) {
    // Remove the revision option message
    const revisionOption = document.querySelector('.revision-option');
    if (revisionOption) {
        revisionOption.remove();
    }
    
    // Show revision request message
    addMessage('Requesting plan revision based on the error...', 'system');
    
    // Add typing indicator
    const typingIndicator = addMessage('Revising plan...', 'system', 'typing-indicator');
    
    // Request plan revision from server
    fetch('/api/plan/revise', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            plan_id: currentPlan.id,
            failed_step_index: data.step_index,
            stdout: data.stdout,
            stderr: data.stderr
        })
    })
    .then(response => response.json())
    .then(data => {
        // Remove typing indicator
        typingIndicator.remove();
        
        // Handle revised plan
        if (data.revised_plan) {
            // Store the revised plan
            currentPlan = data.revised_plan;
            
            // Show revised plan message
            addMessage('I\'ve revised the plan to handle the error. Here\'s the revised plan:', 'assistant');
            
            // Display revised plan for review
            showPlanReview(data.revised_plan);
        } else {
            addMessage('Sorry, I couldn\'t revise the plan based on the error. You can try providing more specific instructions.', 'assistant');
        }
    })
    .catch(error => {
        // Remove typing indicator
        typingIndicator.remove();
        
        console.error('Error revising plan:', error);
        addMessage('Sorry, there was an error revising the plan. Please try again.', 'system');
    });
}