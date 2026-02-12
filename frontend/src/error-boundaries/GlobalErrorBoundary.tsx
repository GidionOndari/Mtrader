import React from 'react';

class GlobalErrorBoundary extends React.Component<React.PropsWithChildren, { hasError: boolean; errorId?: string }> {
  constructor(props: React.PropsWithChildren) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): { hasError: boolean } {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    const errorId = crypto.randomUUID();
    this.setState({ errorId });
    // @ts-ignore
    if (window.Sentry) {
      // @ts-ignore
      window.Sentry.captureException(error, { extra: { componentStack: info.componentStack, errorId } });
    }
  }

  recover = () => {
    localStorage.clear();
    sessionStorage.clear();
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-slate-950 text-slate-100">
          <div className="p-6 rounded-xl bg-slate-900">
            <h1 className="text-xl font-semibold">Something went wrong</h1>
            <p className="text-sm mt-2">Error ID: {this.state.errorId}</p>
            <button className="mt-4 px-3 py-2 rounded bg-amber-700" onClick={this.recover}>Recover</button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export default GlobalErrorBoundary;
