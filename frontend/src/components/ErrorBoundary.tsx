import {Component, type ReactNode} from "react";

interface Props { children: ReactNode; }
interface State { error: Error | null; }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-slate-50 to-white">
          <div className="text-center space-y-3">
            <p className="text-lg font-semibold text-slate-800">出错了</p>
            <p className="text-sm text-slate-500 max-w-md">
              {this.state.error.message || "未知错误"}
            </p>
            <button
              onClick={() => { this.setState({ error: null }); window.location.href = "/"; }}
              className="mt-4 rounded-xl bg-indigo-500 px-4 py-2 text-sm text-white hover:bg-indigo-600"
            >
              返回首页
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
