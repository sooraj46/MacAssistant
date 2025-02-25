import React from 'react';
import styled from 'styled-components';
import Message from './Message';

const MessageList = ({ messages }) => {
  return (
    <Container>
      {messages.map(message => (
        <Message
          key={message.id}
          content={message.content}
          type={message.type}
          timestamp={message.timestamp}
          output={message.output}
          isError={message.isError}
        />
      ))}
    </Container>
  );
};

const Container = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  gap: 16px;
`;

export default MessageList;