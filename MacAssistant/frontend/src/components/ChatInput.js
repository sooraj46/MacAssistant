import React, { useState } from 'react';
import styled from 'styled-components';
import { FiSend } from 'react-icons/fi';

const ChatInput = ({ onSendMessage }) => {
  const [message, setMessage] = useState('');
  
  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (message.trim()) {
      onSendMessage(message);
      setMessage('');
    }
  };
  
  return (
    <Container>
      <Form onSubmit={handleSubmit}>
        <Input 
          type="text" 
          value={message} 
          onChange={(e) => setMessage(e.target.value)}
          placeholder="Describe your task (e.g., 'Create a backup of my Documents folder')"
        />
        <SendButton type="submit" disabled={!message.trim()}>
          <FiSend size={18} />
        </SendButton>
      </Form>
    </Container>
  );
};

const Container = styled.div`
  padding: 15px 0 5px 0;
  background-color: ${props => props.theme.background};
  border-top: 1px solid ${props => props.theme.border};
  position: sticky;
  bottom: 0;
`;

const Form = styled.form`
  display: flex;
  align-items: center;
`;

const Input = styled.input`
  flex: 1;
  padding: 12px 16px;
  border-radius: 24px;
  border: 1px solid ${props => props.theme.border};
  background-color: ${props => props.theme.inputBackground};
  color: ${props => props.theme.text};
  font-size: 16px;
  outline: none;
  
  &:focus {
    border-color: ${props => props.theme.primary};
    box-shadow: 0 0 0 2px ${props => props.theme.primary}33;
  }
  
  &::placeholder {
    color: ${props => props.theme.textSecondary};
  }
`;

const SendButton = styled.button`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background-color: ${props => props.theme.primary};
  color: white;
  border: none;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-left: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  
  &:hover {
    background-color: ${props => props.theme.secondary};
  }
  
  &:disabled {
    background-color: ${props => props.theme.border};
    cursor: not-allowed;
  }
`;

export default ChatInput;