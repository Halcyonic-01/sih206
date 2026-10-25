import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup, configure } from '@testing-library/react'

afterEach(() => cleanup())

// findBy*/waitFor give up after 1 s by default. On a busy CI runner the session check, a lazy route chunk and
// Ant Design's first render can take longer, so the same expectations get 5 s (each test still has 15 s).
configure({ asyncUtilTimeout: 5000 })

// Ant Design reads these browser APIs, which jsdom does not provide.
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query: string) => ({
    matches: false, media: query, onchange: null,
    addListener: () => {}, removeListener: () => {},
    addEventListener: () => {}, removeEventListener: () => {}, dispatchEvent: () => false,
  }),
})
class ResizeObserverStub { observe() {} unobserve() {} disconnect() {} }
;(globalThis as { ResizeObserver?: unknown }).ResizeObserver ??= ResizeObserverStub

// jsdom does not implement getComputedStyle with a pseudo-element (Ant Design's scrollbar measuring uses it).
const computedStyle = window.getComputedStyle.bind(window)
window.getComputedStyle = (element: Element) => computedStyle(element)
