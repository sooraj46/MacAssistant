import React, { useState } from 'react';
import styled from 'styled-components';
import { FiAlertTriangle, FiCheckCircle, FiXCircle } from 'react-icons/fi';

const RiskyCommandModal = ({ command, explanation, onConfirm, onCancel }) => {
  const [confirmationText, setConfirmationText] = useState('');
  
  const handleConfirm = () => {
    if (confirmationText === 'YES') {
      onConfirm();
    }
  };
  
  return (
    <ModalOverlay>
      <ModalContainer>
        <ModalHeader>
          <ModalTitle>Risky Command Confirmation</ModalTitle>
        </ModalHeader>
        
        <ModalContent>
          <WarningContainer>
            <WarningIcon>
              <FiAlertTriangle size={40} />
            </WarningIcon>
            <WarningText>This command is potentially risky:</WarningText>
          </WarningContainer>
          
          <CommandBlock>{command}</CommandBlock>
          
          <RiskExplanation>{explanation}</RiskExplanation>
          
          <ConfirmationInstructions>
            To proceed, please type <ConfirmText>YES</ConfirmText> to confirm:
          </ConfirmationInstructions>
          
          <ConfirmationInput
            type="text"
            value={confirmationText}
            onChange={(e) => setConfirmationText(e.target.value)}
            placeholder="Type YES to confirm"
          />
          
          <ButtonGroup>
            <ActionButton 
              danger 
              onClick={handleConfirm} 
              disabled={confirmationText !== 'YES'}
            >
              <FiCheckCircle />
              Confirm Execution
            </ActionButton>
            <ActionButton secondary onClick={onCancel}>
              <FiXCircle />
              Cancel
            </ActionButton>
          </ButtonGroup>
        </ModalContent>
      </ModalContainer>
    </ModalOverlay>
  );
};

const ModalOverlay = styled.div`
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: ${props => props.theme.modalOverlay};
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 20px;
`;

const ModalContainer = styled.div`
  background-color: ${props => props.theme.modalBackground};
  border-radius: 12px;
  width: 100%;
  max-width: 550px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 10px 25px ${props => props.theme.shadow};
`;

const ModalHeader = styled.div`
  padding: 20px;
  border-bottom: 1px solid ${props => props.theme.border};
`;

const ModalTitle = styled.h2`
  margin: 0;
  font-size: 20px;
  color: ${props => props.theme.text};
`;

const ModalContent = styled.div`
  padding: 20px;
`;

const WarningContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 20px;
`;

const WarningIcon = styled.div`
  color: ${props => props.theme.warning};
  margin-bottom: 10px;
`;

const WarningText = styled.p`
  font-weight: bold;
  color: ${props => props.theme.danger};
  margin: 0;
`;

const CommandBlock = styled.pre`
  width: 100%;
  padding: 12px;
  background-color: ${props => props.theme.codeBlock};
  color: ${props => props.theme.codeBlockText};
  border-radius: 6px;
  font-family: Menlo, Monaco, 'Courier New', monospace;
  font-size: 13px;
  overflow-x: auto;
  margin-bottom: 20px;
`;

const RiskExplanation = styled.div`
  padding: 12px;
  background-color: ${props => props.theme.warning}20;
  border-left: 4px solid ${props => props.theme.warning};
  color: ${props => props.theme.text};
  border-radius: 4px;
  margin-bottom: 20px;
`;

const ConfirmationInstructions = styled.p`
  margin-bottom: 10px;
  color: ${props => props.theme.text};
`;

const ConfirmText = styled.span`
  font-weight: bold;
  color: ${props => props.theme.danger};
`;

const ConfirmationInput = styled.input`
  width: 100%;
  padding: 12px;
  border-radius: 6px;
  border: 1px solid ${props => props.theme.border};
  background-color: ${props => props.theme.inputBackground};
  color: ${props => props.theme.text};
  font-size: 16px;
  margin-bottom: 20px;
  outline: none;
  
  &:focus {
    border-color: ${props => props.theme.danger};
    box-shadow: 0 0 0 2px ${props => props.theme.danger}33;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 10px;
`;

const ActionButton = styled.button`
  display: flex;
  align-items: center;
  padding: 10px 16px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s ease;
  
  svg {
    margin-right: 6px;
  }
  
  ${props => props.primary && `
    background-color: ${props.theme.primary};
    color: white;
    border: none;
    
    &:hover {
      background-color: ${props.theme.secondary};
    }
  `}
  
  ${props => props.secondary && `
    background-color: transparent;
    color: ${props.theme.text};
    border: 1px solid ${props.theme.border};
    
    &:hover {
      background-color: ${props.theme.cardBackground};
    }
  `}
  
  ${props => props.danger && `
    background-color: ${props.theme.danger};
    color: white;
    border: none;
    
    &:hover {
      opacity: 0.9;
    }
    
    &:disabled {
      background-color: ${props.theme.textSecondary};
      cursor: not-allowed;
      opacity: 0.7;
    }
  `}
`;

export default RiskyCommandModal;