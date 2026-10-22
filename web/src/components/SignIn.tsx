import { useState, type FormEvent } from "react";
import { api, ApiError } from "../api";
import { Mark } from "../icons";

/** The only screen someone without the password ever sees. */
export function SignIn() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.login(password);
      location.reload();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setBusy(false);
    }
  };

  return (
    <main className="signin">
      <form onSubmit={submit} aria-labelledby="signin-h">
        <div className="signin-head">
          <Mark />
          <b id="signin-h">TIP-OFF DESK</b>
        </div>
        <label htmlFor="pw">Desk password</label>
        <input
          id="pw"
          type="password"
          autoComplete="current-password"
          autoFocus
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={!!error}
          aria-describedby={error ? "pw-error" : undefined}
        />
        {error && (
          <p id="pw-error" className="signin-error" role="alert">
            {error}
          </p>
        )}
        <button className="btn primary" disabled={busy || !password}>
          {busy ? "Signing in…" : "Sign in"}
        </button>
        <small>Stays signed in on this device for 30 days.</small>
      </form>
    </main>
  );
}
