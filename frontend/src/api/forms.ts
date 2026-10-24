import type { FormInstance } from 'antd'
import { ApiError } from './client'

/** Copies a 400 response's per-field errors into an Ant Design form. Returns true when it handled them. */
export function applyFieldErrors(form: FormInstance, error: unknown): boolean {
  if (!(error instanceof ApiError) || !error.isValidation) return false
  const fields = Object.entries(error.errors)
    .filter(([name]) => name !== 'non_field_errors')
    .map(([name, errors]) => ({ name, errors }))
  if (fields.length) form.setFields(fields)
  return fields.length > 0
}

/** One readable sentence for any error, including the non-field part of a 400. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    const general = error.errors.non_field_errors?.join(' ')
    return general || error.message
  }
  return error instanceof Error ? error.message : 'Something went wrong.'
}
