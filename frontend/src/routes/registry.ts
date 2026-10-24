/**
 * Registration point for screens. Nobody edits this file to add a screen:
 *
 *   src/features/<area>/routes.tsx    export const routes: AppRoute[]        (signed-in screens in the shell)
 *                                     export const publicRoutes: AppRoute[]  (no sign-in, no shell; optional)
 *   src/features/<area>/HeaderSearch.tsx   default export component for the header search slot (Y5)
 *   src/features/<area>/Bell.tsx           default export component for the notification bell slot (K5)
 *
 * Vite discovers the files at build time, so a new feature appears after a restart of `npm run dev`.
 */
import type { ComponentType } from 'react'
import type { AppRoute } from './types'

interface RouteModule { routes?: AppRoute[]; publicRoutes?: AppRoute[] }

const modules = import.meta.glob<RouteModule>('../features/*/routes.tsx', { eager: true })

function collect(key: 'routes' | 'publicRoutes'): AppRoute[] {
  return Object.keys(modules).sort().flatMap((file) => modules[file]?.[key] ?? [])
}

export const appRoutes: AppRoute[] = collect('routes')
export const publicRoutes: AppRoute[] = collect('publicRoutes')

const searchModules = import.meta.glob<{ default: ComponentType }>('../features/*/HeaderSearch.tsx', { eager: true })
const bellModules = import.meta.glob<{ default: ComponentType }>('../features/*/Bell.tsx', { eager: true })

export const HeaderSearchSlot: ComponentType | null = Object.values(searchModules)[0]?.default ?? null
export const BellSlot: ComponentType | null = Object.values(bellModules)[0]?.default ?? null
