import React from 'react';
import styled from 'styled-components';
import { FiSun, FiMoon } from 'react-icons/fi';

const Header = ({ toggleTheme, theme }) => {
  return (
    <HeaderContainer>
      <Logo>
        <LogoIcon>🤖</LogoIcon>
        <LogoText>MacAssistant</LogoText>
      </Logo>
      <ThemeToggle onClick={toggleTheme}>
        {theme === 'light' ? <FiMoon size={20} /> : <FiSun size={20} />}
      </ThemeToggle>
    </HeaderContainer>
  );
};

const HeaderContainer = styled.header`
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid ${props => props.theme.border};
  background-color: ${props => props.theme.background};
  position: sticky;
  top: 0;
  z-index: 10;
`;

const Logo = styled.div`
  display: flex;
  align-items: center;
`;

const LogoIcon = styled.span`
  font-size: 24px;
  margin-right: 10px;
`;

const LogoText = styled.h1`
  font-size: 22px;
  font-weight: 600;
  color: ${props => props.theme.text};
`;

const ThemeToggle = styled.button`
  background: none;
  border: none;
  color: ${props => props.theme.text};
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 8px;
  border-radius: 50%;
  
  &:hover {
    background-color: ${props => props.theme.cardBackground};
  }
`;

export default Header;