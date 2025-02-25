import React, { useRef, useEffect } from 'react';
import styled from 'styled-components';
import MessageList from './MessageList';
import ChatInput from './ChatInput';

const ChatContainer = ({ messages, onSendMessage }) => {
  const messagesEndRef = useRef(null);
  
  // Scroll to bottom when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages]);
  
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  
  return (
    <Container>
      <MessageList messages={messages} />
      <div ref={messagesEndRef} />
      <ChatInput onSendMessage={onSendMessage} />
    </Container>
  );
};

const Container = styled.div`
  display: flex;
  flex-direction: column;
  height: 100%;
  max-width: 1200px;
  margin: 0 auto;
  width: 100%;
  position: relative;
  padding-bottom: 10px;
`;

export default ChatContainer;