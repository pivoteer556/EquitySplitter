// Shared by the page specs: the server's PASSWORD_POLICY (app/services/auth.py) as advertised to browsers.
// Changing the rule means changing the server regex, this constant and the three templates together.
export const PASSWORD_PATTERN = String.raw`(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}`;
export const PASSWORD_RULES = 'minlength: 10; required: lower; required: upper; required: digit; required: special;';
const SERVER = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{10,}$/;
const GOOD = ['Str0ng!Passw0rd', 'abcDEF123!xyz', 'Pässw0rd!ünï'];
const WEAK = ['Str0ngPassw0rd', 'Strong!Password', 'Str0ng!Pw', 'str0ng!passw0rd', 'STR0NG!PASSW0RD', ''];

/** Asserts the advertised rule on one new-password input; the browser compiles `pattern` as ^(?:...)$ with the v flag. */
export function expectPasswordRule(pw: HTMLInputElement): void {
  expect(pw.autocomplete).toBe('new-password');
  expect(pw.getAttribute('minlength')).toBe('10');
  expect(pw.getAttribute('pattern')).toBe(PASSWORD_PATTERN);
  expect(pw.getAttribute('passwordrules')).toBe(PASSWORD_RULES);
  expect(pw.title).toContain('10 characters');
  const hint = pw.ownerDocument.getElementById(pw.getAttribute('aria-describedby') ?? '');
  expect(hint?.textContent).toContain('10 characters');
  const re = new RegExp('^(?:' + pw.getAttribute('pattern') + ')$', 'v');
  for (const p of GOOD) {
    expect(re.test(p)).withContext(p).toBe(SERVER.test(p));
    expect(re.test(p)).withContext(p).toBeTrue();
  }
  for (const p of WEAK) {
    expect(re.test(p)).withContext(p).toBeFalse();
    expect(SERVER.test(p)).withContext(p).toBeFalse();
  }
  // the real browser validity states, not just the regex
  pw.value = 'Str0ng!Passw0rd';
  expect(pw.validity.valid).toBeTrue();
  pw.value = 'Str0ngPassw0rd';
  expect(pw.validity.patternMismatch).toBeTrue();
  pw.value = 'nouppercase1!';
  expect(pw.validity.patternMismatch).toBeTrue();
  pw.value = 'Sh0rt!Pw';
  expect(pw.validity.patternMismatch).toBeTrue();
}
