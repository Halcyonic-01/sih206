import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

afterEach(() => cleanup())

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
