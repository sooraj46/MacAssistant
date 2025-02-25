import React from 'react';
import styled from 'styled-components';
import ReactMarkdown from 'react-markdown';

const Message = ({ content, type, timestamp, output, isError }) => {
  // Format timestamp
  const formattedTime = new Date(timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit'
  });
  
  return (
    <Container type={type}>
      <MessageContent type={type}>
        <ReactMarkdown>{content}</ReactMarkdown>
        
        {output && (
          <OutputBlock isError={isError}>
            {output}
          </OutputBlock>
        )}
        
        <Timestamp>{formattedTime}</Timestamp>
      </MessageContent>
    </Container>
  );
};

const Container = styled.div`
  display: flex;
  justify-content: ${props => props.type === 'user' ? 'flex-end' : 'flex-start'};
  margin-bottom: 4px;
  
  ${props => props.type === 'system' && `
    justify-content: center;
  `}
`;

const MessageContent = styled.div`
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 18px;
  background-color: ${props => 
    props.type === 'user' 
      ? props.theme.userMessage 
      : props.type === 'assistant'
        ? props.theme.assistantMessage
        : props.theme.systemMessage
  };
  color: ${props => 
    props.type === 'user' 
      ? props.theme.userMessageText 
      : props.type === 'assistant'
        ? props.theme.assistantMessageText
        : props.theme.systemMessageText
  };
  
  ${props => props.type === 'user' && `
    border-bottom-right-radius: 4px;
  `}
  
  ${props => props.type === 'assistant' && `
    border-bottom-left-radius: 4px;
  `}
  
  ${props => props.type === 'system' && `
    font-style: italic;
    font-size: 14px;
    max-width: 90%;
    text-align: center;
    opacity: 0.8;
  `}
  
  p {
    margin: 0;
  }
`;

const Timestamp = styled.div`
  font-size: 11px;
  opacity: 0.7;
  margin-top: 5px;
  text-align: right;
`;

const OutputBlock = styled.pre`
  margin-top: 8px;
  padding: 12px;
  background-color: ${props => props.theme.codeBlock};
  color: ${props => props.isError ? props.theme.danger : props.theme.codeBlockText};
  border-radius: 6px;
  font-family: Menlo, Monaco, 'Courier New', monospace;
  font-size: 13px;
  overflow-x: auto;
  white-space: pre-wrap;
  max-height: 300px;
  overflow-y: auto;
`;

export default Message;