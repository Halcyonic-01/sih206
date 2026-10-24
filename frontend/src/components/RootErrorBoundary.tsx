import { Component, type ReactNode } from 'react'
import { ErrorState } from './states'

export class RootErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed
      ? <ErrorState title="This page crashed" detail="Reload the page. If it keeps happening, tell the portal operator."
                    onRetry={() => window.location.reload()} />
      : this.props.children
  }
}
