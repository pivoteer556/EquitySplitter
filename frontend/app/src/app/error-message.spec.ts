import { friendlyError } from './error-message';

describe('friendlyError', () => {
  it('maps 401 to an incorrect credentials message', () => {
    expect(friendlyError({ status: 401, error: { detail: 'Invalid credentials' } })).toBe(
      'Incorrect email or password.',
    );
  });

  it('maps 429 to a wait message', () => {
    expect(friendlyError({ status: 429, error: { detail: 'Too many failed login attempts' } })).toBe(
      'Too many attempts. Please wait a minute and try again.',
    );
  });

  it('maps status 0 to a connectivity message', () => {
    expect(friendlyError({ status: 0, error: new ProgressEvent('error') })).toBe(
      "Can't reach the server. Check your connection and try again.",
    );
  });

  it('shows a string detail from the server (403, 409)', () => {
    expect(friendlyError({ status: 403, error: { detail: 'Password reset required' } })).toBe(
      'Password reset required',
    );
    expect(friendlyError({ status: 409, error: { detail: 'Email already registered' } })).toBe(
      'Email already registered',
    );
  });

  it('falls back to a generic message for 422 list details and unknown shapes', () => {
    const generic = 'Something went wrong. Please try again.';
    expect(friendlyError({ status: 422, error: { detail: [{ loc: ['body', 'email'], msg: 'x' }] } })).toBe(generic);
    expect(friendlyError(undefined)).toBe(generic);
    expect(friendlyError({ status: 500, error: 'oops' })).toBe(generic);
  });
});
