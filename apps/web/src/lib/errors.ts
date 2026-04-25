export function readableError(error: unknown): string {
  return error instanceof Error ? error.message : 'Something went wrong.'
}
