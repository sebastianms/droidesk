import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useId, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { useNavigate } from 'react-router'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { Button } from '../../ui/Button'
import { DroidLogo } from '../../ui/DroidLogo'
import { IconButton } from '../../ui/IconButton'
import { ErrorNotice } from '../../ui/Notice'
import { Panel } from '../../ui/Panel'
import { TextField } from '../../ui/TextField'
import { useEscapeKey } from '../../ui/useEscapeKey'
import { homePathFor } from './access'
import { type CredentialErrors, normalizeUsername, PASSWORD_MAX_LENGTH, validateCredentials } from './credentials'
import { DemoUsersPanel } from './DemoUsersPanel'
import styles from './LoginPage.module.css'
import { saveSession } from './session'

const GENERIC_FAILURE = 'Bip-bup: no pude abrir la compuerta. Intenta de nuevo.'

export function LoginPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const login = $api.useMutation('post', '/api/v1/auth/login', {
    onSuccess: (response) => {
      queryClient.clear()
      saveSession(response)
      navigate(homePathFor(response.user.role), { replace: true })
    },
  })
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<CredentialErrors>({})
  const [demoUsersOpen, setDemoUsersOpen] = useState(false)
  const demoUsersId = useId()
  const usernameInput = useRef<HTMLInputElement>(null)
  const passwordInput = useRef<HTMLInputElement>(null)
  const demoUsersButton = useRef<HTMLButtonElement>(null)
  const demoUsersPanel = useRef<HTMLElement>(null)

  useEscapeKey(demoUsersOpen, () => {
    const focused = document.activeElement
    const focusIsInHelp = focused === demoUsersButton.current || demoUsersPanel.current?.contains(focused)
    setDemoUsersOpen(false)
    if (focusIsInHelp) demoUsersButton.current?.focus()
  })

  function dismissError(field: keyof CredentialErrors) {
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  function pickDemoUser(picked: string) {
    setUsername(picked)
    dismissError('username')
    setDemoUsersOpen(false)
    passwordInput.current?.focus()
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validateCredentials({ username, password })
    // Síncrono: el campo ya debe estar descrito por su error cuando recibe el foco, para que se anuncie.
    flushSync(() => setErrors(found))
    if (found.username) {
      usernameInput.current?.focus()
    } else if (found.password) {
      passwordInput.current?.focus()
    } else {
      login.mutate({ body: { username: normalizeUsername(username), password } })
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.brand}>
        <DroidLogo size={56} />
        <h1>DroiDesk</h1>
      </div>
      <p className={styles.intro}>Ingreso simulado: usa uno de los usuarios de demo; cualquier contraseña sirve.</p>

      <Panel
        title="Ingreso"
        action={
          <IconButton
            ref={demoUsersButton}
            label="Ver usuarios de demo"
            aria-expanded={demoUsersOpen}
            aria-controls={demoUsersId}
            onClick={() => setDemoUsersOpen((open) => !open)}
          >
            ?
          </IconButton>
        }
      >
        <div className={styles.body}>
          <DemoUsersPanel ref={demoUsersPanel} id={demoUsersId} open={demoUsersOpen} onPick={pickDemoUser} />
          <form className={styles.form} onSubmit={submit} noValidate>
            <TextField
              ref={usernameInput}
              label="Usuario"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              value={username}
              error={errors.username}
              onChange={(event) => {
                setUsername(event.target.value)
                dismissError('username')
              }}
            />
            <TextField
              ref={passwordInput}
              label="Contraseña"
              type="password"
              autoComplete="current-password"
              maxLength={PASSWORD_MAX_LENGTH}
              required
              value={password}
              error={errors.password}
              onChange={(event) => {
                setPassword(event.target.value)
                dismissError('password')
              }}
            />
            {login.isError && <ErrorNotice message={serverMessage(login.error) ?? GENERIC_FAILURE} />}
            <Button type="submit" disabled={login.isPending}>
              {login.isPending ? 'Ingresando...' : 'Ingresar'}
            </Button>
          </form>
        </div>
      </Panel>
    </main>
  )
}
