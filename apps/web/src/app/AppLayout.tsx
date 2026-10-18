import { useQueryClient } from '@tanstack/react-query'
import { Outlet, useNavigate } from 'react-router'
import { LOGIN_PATH, ROLE_LABEL } from '../features/auth/access'
import { clearSession, getSession } from '../features/auth/session'
import { Button } from '../ui/Button'
import { DroidLogo } from '../ui/DroidLogo'
import { Light } from '../ui/Light'
import styles from './AppLayout.module.css'

export function AppLayout() {
  const session = getSession()
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  function signOut() {
    clearSession()
    queryClient.clear()
    navigate(LOGIN_PATH, { replace: true })
  }

  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <DroidLogo size={36} />
          DroiDesk
        </div>
        {session && (
          <div className={styles.user}>
            <span className={styles.userName}>{session.user.name}</span>
            <Light variant="holo" label={ROLE_LABEL[session.user.role]} />
            <Button variant="secondary" onClick={signOut}>
              Salir
            </Button>
          </div>
        )}
      </header>
      <main className={styles.main}>
        <Outlet />
      </main>
    </div>
  )
}
