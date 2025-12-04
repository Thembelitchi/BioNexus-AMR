import React, { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';

interface Props {
  children?: ReactNode;
  fallback?: ReactNode;
  onReset?: () => void;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends React.Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    // Log error for monitoring
    console.error('Uncaught error in component:', error);
    console.error('Component stack:', errorInfo.componentStack);
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: null });
    if (this.props.onReset) {
      this.props.onReset();
    }
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <div className="flex flex-col items-center justify-center p-6 bg-rose-50 border border-rose-100 rounded-xl text-center h-full min-h-[200px] animate-fade-in">
            <div className="bg-rose-100 p-3 rounded-full mb-3 shadow-sm">
                <AlertTriangle className="w-8 h-8 text-rose-600" />
            </div>
            <h3 className="text-lg font-bold text-slate-800 mb-1">Unable to Display Content</h3>
            <p className="text-sm text-slate-600 mb-4 max-w-xs">
                We encountered an unexpected error while rendering this element.
            </p>
            
            {this.state.error && (
                <details className="text-left w-full mb-4 bg-white p-3 rounded-lg border border-rose-100 text-xs text-rose-800 font-mono overflow-auto max-h-32 shadow-inner">
                    <summary className="cursor-pointer font-bold mb-1 outline-none hover:text-rose-900">Error Details</summary>
                    {this.state.error.message}
                </details>
            )}

            <button 
                onClick={this.handleRetry}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-slate-200 text-slate-700 rounded-lg hover:bg-slate-50 hover:text-blue-600 transition-all shadow-sm text-sm font-medium"
            >
                <RefreshCw className="w-4 h-4" /> Reset View
            </button>
        </div>
      );
    }

    return this.props.children;
  }
}
