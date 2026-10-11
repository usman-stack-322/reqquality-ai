export const BACKEND_UNAVAILABLE = 'The sign-in service is unavailable. Check that the backend is running and try again.';

export function loginErrorMessage(status, data = {}) {
  if (status === 401) return 'Email or password is incorrect.';
  if (status === 503 && data.code === 'database_unavailable') {
    return 'The database is temporarily unavailable. Please try again later.';
  }
  if (status >= 500) return BACKEND_UNAVAILABLE;
  if (status === 429) return 'Too many sign-in attempts. Please wait before trying again.';
  return typeof data.error === 'string' ? data.error : 'Unable to sign in. Please try again.';
}
