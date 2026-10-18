import type { Ref } from 'react'
import { $api } from '../../api/client'
import { Button } from '../../ui/Button'
import { Light } from '../../ui/Light'
import type { Role } from './access'
import styles from './DemoUsersPanel.module.css'

// Un perfil nuevo en el contrato rompe la compilación hasta que tenga su título; el orden es el de la lista.
const GROUP_TITLE: Record<Role, string> = {
  requester: 'Solicitantes',
  agent: 'Agentes',
}

interface DemoUsersPanelProps {
  ref?: Ref<HTMLElement>
  id: string
  open: boolean
  onPick: (username: string) => void
}

export function DemoUsersPanel({ ref, id, open, onPick }: DemoUsersPanelProps) {
  const users = $api.useQuery('get', '/api/v1/auth/users', {}, { enabled: open })

  const headingId = `${id}-heading`

  return (
    <section ref={ref} id={id} hidden={!open} aria-labelledby={headingId}>
      <div className={styles.panel}>
        <h3 id={headingId} className={styles.heading}>
          Usuarios de demo
        </h3>
        <p className={styles.description}>
          Son cuentas de demostración precargadas para probar DroiDesk: los solicitantes crean tickets y los agentes los
          atienden. Elige una y escribe cualquier contraseña.
        </p>
        {users.isPending && <p role="status">Bip-bup: buscando a los usuarios de demo...</p>}
        {users.isError && (
          <div role="alert" className={styles.error}>
            <Light variant="alert" label="Bip-bup: no pude cargar los usuarios de demo." />
            <Button variant="secondary" onClick={() => users.refetch()}>
              Reintentar
            </Button>
          </div>
        )}
        {users.data?.length === 0 && <p>Bip-bup: no hay usuarios de demo cargados.</p>}
        {users.data && users.data.length > 0 && (
          <div className={styles.groups}>
            {Object.entries(GROUP_TITLE).map(([role, title]) => {
              const members = users.data.filter((user) => user.role === role)
              if (members.length === 0) return null
              const titleId = `${id}-${role}`
              return (
                <section key={role} aria-labelledby={titleId}>
                  <h4 id={titleId} className={styles.title}>
                    {title}
                  </h4>
                  <ul className={styles.list}>
                    {members.map((user) => (
                      <li key={user.username}>
                        <Button variant="secondary" className={styles.user} onClick={() => onPick(user.username)}>
                          <span className={styles.details}>
                            {user.name}
                            <span className={styles.username}>{user.username}</span>
                          </span>
                        </Button>
                      </li>
                    ))}
                  </ul>
                </section>
              )
            })}
          </div>
        )}
      </div>
    </section>
  )
}
