import React from 'react';
import styled from 'styled-components';
import { FiCheckCircle, FiXCircle, FiAlertTriangle } from 'react-icons/fi';

const PlanReviewModal = ({ 
  plan, 
  onAccept, 
  onReject, 
  showFeedback, 
  feedbackText, 
  onFeedbackChange, 
  onFeedbackSubmit, 
  onFeedbackCancel 
}) => {
  if (!plan) return null;
  
  return (
    <ModalOverlay>
      <ModalContainer>
        <ModalHeader>
          <ModalTitle>Review Plan</ModalTitle>
        </ModalHeader>
        
        <ModalContent>
          <ModalDescription>
            I'll complete your task with these steps:
          </ModalDescription>
          
          <PlanSteps>
            {plan.steps.map((step) => (
              <PlanStep key={step.number}>
                <StepNumber>{step.number}</StepNumber>
                <StepContent>
                  {step.is_risky && (
                    <RiskyBadge>
                      <FiAlertTriangle />
                      RISKY
                    </RiskyBadge>
                  )}
                  <StepDescription>{step.description}</StepDescription>
                </StepContent>
              </PlanStep>
            ))}
          </PlanSteps>
          
          {!showFeedback ? (
            <ButtonGroup>
              <ActionButton primary onClick={onAccept}>
                <FiCheckCircle />
                Accept Plan
              </ActionButton>
              <ActionButton secondary onClick={onReject}>
                <FiXCircle />
                Reject Plan
              </ActionButton>
            </ButtonGroup>
          ) : (
            <FeedbackContainer>
              <FeedbackHeader>Why are you rejecting this plan?</FeedbackHeader>
              <FeedbackTextarea 
                placeholder="Please provide feedback on why this plan doesn't meet your needs..."
                value={feedbackText}
                onChange={onFeedbackChange}
              />
              <ButtonGroup>
                <ActionButton primary onClick={onFeedbackSubmit}>
                  Submit Feedback
                </ActionButton>
                <ActionButton secondary onClick={onFeedbackCancel}>
                  Cancel
                </ActionButton>
              </ButtonGroup>
            </FeedbackContainer>
          )}
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
  max-width: 600px;
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

const ModalDescription = styled.p`
  margin-bottom: 20px;
  color: ${props => props.theme.textSecondary};
`;

const PlanSteps = styled.div`
  margin-bottom: 25px;
  display: flex;
  flex-direction: column;
  gap: 12px;
`;

const PlanStep = styled.div`
  display: flex;
  align-items: flex-start;
  padding: 12px;
  border-radius: 8px;
  background-color: ${props => props.theme.cardBackground};
  border: 1px solid ${props => props.theme.border};
`;

const StepNumber = styled.div`
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background-color: ${props => props.theme.primary};
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  margin-right: 12px;
  flex-shrink: 0;
`;

const StepContent = styled.div`
  flex: 1;
`;

const StepDescription = styled.div`
  color: ${props => props.theme.text};
`;

const RiskyBadge = styled.div`
  display: inline-flex;
  align-items: center;
  padding: 3px 8px;
  background-color: ${props => props.theme.warning};
  color: white;
  border-radius: 4px;
  font-size: 12px;
  font-weight: bold;
  margin-bottom: 6px;
  
  svg {
    margin-right: 4px;
  }
`;

const ButtonGroup = styled.div`
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
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
  `}
`;

const FeedbackContainer = styled.div`
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid ${props => props.theme.border};
`;

const FeedbackHeader = styled.h3`
  margin-bottom: 10px;
  font-size: 16px;
  color: ${props => props.theme.text};
`;

const FeedbackTextarea = styled.textarea`
  width: 100%;
  height: 120px;
  padding: 12px;
  border-radius: 8px;
  border: 1px solid ${props => props.theme.border};
  background-color: ${props => props.theme.inputBackground};
  color: ${props => props.theme.text};
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
  font-size: 14px;
  resize: vertical;
  outline: none;
  
  &:focus {
    border-color: ${props => props.theme.primary};
    box-shadow: 0 0 0 2px ${props => props.theme.primary}33;
  }
  
  &::placeholder {
    color: ${props => props.theme.textSecondary};
  }
`;

export default PlanReviewModal;