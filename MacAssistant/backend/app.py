"""
MacAssistant Backend
A Flask server for the MacAssistant application, handling user requests, 
LLM communication, plan management, command execution, safety checks, and logging.
"""

import os
import json
import nest_asyncio
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from flask_socketio import SocketIO
from modules.llm_integration import LLMIntegration
from modules.agent_orchestrator import AgentOrchestrator
from modules.command_generator import CommandGenerator
from modules.safety_checker import SafetyChecker
from modules.execution_engine import ExecutionEngine
from modules.logger import Logger

# Apply nest_asyncio to make asyncio play nice with Flask
nest_asyncio.apply()

# Initialize Flask app
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize modules
llm_integration = LLMIntegration()
command_generator = CommandGenerator()
safety_checker = SafetyChecker()
execution_engine = ExecutionEngine()
logger = Logger()
agent_orchestrator = AgentOrchestrator(
    llm_integration, 
    command_generator, 
    safety_checker, 
    execution_engine,
    logger
)

@app.route('/')
def index():
    """Render the main application page."""
    return render_template('index.html')

@app.route('/api/task', methods=['POST'])
def process_task():
    """Process a user task request."""
    data = request.json
    user_request = data.get('request')
    
    # Log the user request
    logger.log_request(user_request)
    
    # Generate plan using LLM
    plan = llm_integration.generate_plan(user_request)
    
    # Log the generated plan
    logger.log_plan(plan)
    
    return jsonify({'plan': plan})

@app.route('/api/plan/accept', methods=['POST'])
def accept_plan():
    """Handle plan acceptance and begin execution."""
    data = request.json
    plan_id = data.get('plan_id')
    
    # Log the plan acceptance
    logger.log_plan_acceptance(plan_id)
    
    # Begin plan execution
    agent_orchestrator.execute_plan(plan_id)
    
    return jsonify({'status': 'execution_started'})

@app.route('/api/plan/reject', methods=['POST'])
def reject_plan():
    """Handle plan rejection and request revision if needed."""
    data = request.json
    plan_id = data.get('plan_id')
    feedback = data.get('feedback')
    
    # Log the plan rejection
    logger.log_plan_rejection(plan_id, feedback)
    
    # Request a revised plan if feedback is provided
    if feedback:
        revised_plan = llm_integration.revise_plan(plan_id, feedback)
        return jsonify({'revised_plan': revised_plan})
    
    return jsonify({'status': 'plan_rejected'})

@app.route('/api/command/confirm', methods=['POST'])
def confirm_risky_command():
    """Handle risky command confirmation."""
    data = request.json
    command_id = data.get('command_id')
    confirmed = data.get('confirmed')
    
    # Log the command confirmation/rejection
    logger.log_command_confirmation(command_id, confirmed)
    
    if confirmed:
        # Proceed with command execution
        agent_orchestrator.execute_command(command_id)
        return jsonify({'status': 'command_execution_started'})
    else:
        # Skip the command
        agent_orchestrator.skip_command(command_id)
        return jsonify({'status': 'command_skipped'})

@app.route('/api/plan/revise', methods=['POST'])
def revise_plan_on_failure():
    """Handle plan revision request after a step failure."""
    data = request.json
    plan_id = data.get('plan_id')
    failed_step_index = data.get('failed_step_index')
    stdout = data.get('stdout', '')
    stderr = data.get('stderr', '')
    
    # Log the plan revision request
    logger.log_info(f"plan_revision_requested: {json.dumps({'plan_id': plan_id, 'failed_step_index': failed_step_index})}")
    
    # Request a revised plan from the LLM
    revised_plan = llm_integration.revise_failed_step(plan_id, failed_step_index, stdout, stderr)
    
    if revised_plan:
        # Log the revised plan
        logger.log_info(f"plan_revised: {json.dumps({'plan_id': plan_id, 'revised_plan_id': revised_plan['id']})}")
        
        # Notify the client about the revision
        socketio.emit('execution_update', {
            'event': 'plan_revised',
            'plan_id': plan_id,
            'revised_plan': revised_plan,
            'revision_summary': f"Plan revised to handle failure at step {failed_step_index + 1}",
            'requires_review': True
        })
        
        return jsonify({'revised_plan': revised_plan})
    
    return jsonify({'status': 'revision_failed'})

@app.route('/api/plan/continue', methods=['POST'])
def continue_plan():
    """Handle continuing a plan after a step failure or other interruption."""
    data = request.json
    plan_id = data.get('plan_id')
    skip_failed_step = data.get('skip_failed_step', False)
    
    # Log the continue plan request
    logger.log_info(f"plan_continue_requested: {json.dumps({'plan_id': plan_id, 'skip_failed_step': skip_failed_step})}")
    
    # Ask the agent orchestrator to continue execution
    agent_orchestrator.continue_execution(plan_id, skip_failed_step)
    
    return jsonify({'status': 'execution_continued'})

@app.route('/api/plan/abort', methods=['POST'])
def abort_plan():
    """Handle aborting a plan execution."""
    data = request.json
    plan_id = data.get('plan_id')
    
    # Log the abort plan request
    logger.log_info(f"plan_abort_requested: {json.dumps({'plan_id': plan_id})}")
    
    # Ask the agent orchestrator to abort execution
    agent_orchestrator.abort_execution(plan_id)
    
    # Notify the client
    socketio.emit('execution_update', {
        'event': 'plan_aborted',
        'plan_id': plan_id
    })
    
    return jsonify({'status': 'execution_aborted'})

@app.route('/api/plan/<plan_id>', methods=['GET'])
def get_plan(plan_id):
    """Get a specific plan by ID."""
    plan = llm_integration.plans.get(plan_id)
    
    if not plan:
        return jsonify({'error': 'Plan not found'}), 404
        
    return jsonify({'plan': plan})

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """Get system logs (for admin use)."""
    log_type = request.args.get('type', 'all')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    logs = logger.get_logs(log_type, start_date, end_date)
    return jsonify({'logs': logs})

# WebSocket events for real-time updates
@socketio.on('connect')
def handle_connect():
    """Handle client connection to WebSocket."""
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection from WebSocket."""
    print('Client disconnected')

@socketio.on('execution_status')
def handle_execution_status(data):
    """Send execution status updates to the client."""
    socketio.emit('execution_update', data)

# This allows the application to be found when run with flask run command
application = app

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True)