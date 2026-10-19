import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App.jsx';
import './styles.css';

class RenderBoundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  componentDidCatch(error) { console.error('Dashboard render failed:', error); }
  render() {
    if (this.state.error) return <main style={{ margin: '12vh auto', maxWidth: 620, padding: 32, fontFamily: 'sans-serif', color: '#27363a' }}><h1>Dashboard could not render</h1><p>{this.state.error.message}</p><p>Check the API and browser console, then refresh the page.</p></main>;
    return this.props.children;
  }
}

createRoot(document.getElementById('root')).render(<React.StrictMode><RenderBoundary><App /></RenderBoundary></React.StrictMode>);
