import { useState, type FormEvent } from 'react'
import { api } from '../api'
import { Mark } from '../components/Mark'

export function Login({ configured, onDone }: { configured: boolean; onDone: () => void }) {
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const submit = (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    api
      .entrar(password)
      .then(onDone)
      .catch((err: Error) => setError(err.message))
      .finally(() => setBusy(false))
  }

  return (
    <main className="login">
      <div className="login-card panel">
        <div className="brand">
          <Mark />
          <div>
            Quant Monitor
            <small>Antes de arriesgar tu dinero, compruébalo.</small>
          </div>
        </div>
        {configured ? (
          <form onSubmit={submit}>
            <label className="field">
              <span className="field-label">Contraseña</span>
              <input
                className="input"
                type="password"
                autoComplete="current-password"
                autoFocus
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
            {error && (
              <p className="error-line" role="alert">
                {error}
              </p>
            )}
            <button className="btn" type="submit" disabled={busy || password.length === 0}>
              {busy ? 'Entrando…' : 'Entrar'}
            </button>
          </form>
        ) : (
          <p className="callout">
            Falta crear la contraseña. En la carpeta del proyecto ejecuta{' '}
            <code>python scripts/set_web_password.py</code> y reinicia el servidor.
          </p>
        )}
      </div>
    </main>
  )
}
