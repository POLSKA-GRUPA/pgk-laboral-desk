import React, { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  retryCount: number;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, retryCount: 0 };

  static getDerivedStateFromError(): State {
    return { hasError: true, retryCount: 0 };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('ErrorBoundary caught:', error, info);
  }

  handleRetry = () => {
    this.setState((prev) => ({
      hasError: false,
      retryCount: prev.retryCount + 1,
    }));
  };

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 48, textAlign: 'center' }}>
          <h2 style={{ color: '#ff4d4f' }}>Error en la aplicacion</h2>
          <p>Ha ocurrido un error inesperado.</p>
          {this.state.retryCount >= 2 ? (
            <button onClick={() => window.location.reload()}>
              Recargar pagina
            </button>
          ) : (
            <button onClick={this.handleRetry}>Reintentar</button>
          )}
        </div>
      );
    }
    return this.props.children;
  }
}
