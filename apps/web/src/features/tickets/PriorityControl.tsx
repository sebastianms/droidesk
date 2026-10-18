import { type FormEvent, useState } from 'react'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { Button } from '../../ui/Button'
import { ErrorNotice, LoadingNotice } from '../../ui/Notice'
import { Select } from '../../ui/Select'
import { ACTION_LABEL, policyLabel } from './labels'
import styles from './PriorityControl.module.css'
import type { Priority, SlaPolicy } from './types'

const LOAD_FAILURE = 'Bip-bup: no pude cargar las prioridades. Intenta de nuevo.'

interface PriorityControlProps {
  current: Priority
  pending: boolean
  /** Pide el cambio; `onDone` se llama si la API lo acepta. El fallo lo muestra quien monta el control. */
  onSubmit: (priority: Priority, onDone: () => void) => void
}

/** El ajuste de prioridad del agente. Quien lo monta decide si se ofrece, según `allowed_actions`, y muestra su fallo. */
export function PriorityControl(props: PriorityControlProps) {
  const policies = $api.useQuery('get', '/api/v1/sla-policies')

  if (policies.isError) return <ErrorNotice message={serverMessage(policies.error) ?? LOAD_FAILURE} />
  if (!policies.data) return <LoadingNotice message="Bip-bup: cargando las prioridades..." />
  return <PriorityForm {...props} policies={policies.data} />
}

// Cada `value` del select sale de una política: así el `string` del evento vuelve a ser una `Priority`.
function toPriority(policies: SlaPolicy[], value: string): Priority | undefined {
  return policies.find((policy) => policy.priority === value)?.priority
}

function PriorityForm({ current, pending, onSubmit, policies }: PriorityControlProps & { policies: SlaPolicy[] }) {
  // Sin elección propia se muestra la prioridad vigente del ticket, también si otro la cambia mientras tanto.
  const [picked, setPicked] = useState<Priority>()
  const selected = picked ?? current

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    onSubmit(selected, () => setPicked(undefined))
  }

  return (
    <form className={styles.form} onSubmit={submit}>
      <div className={styles.row}>
        <Select
          label="Prioridad"
          value={selected}
          onChange={(event) => setPicked(toPriority(policies, event.target.value))}
        >
          {policies.map((policy) => (
            <option key={policy.priority} value={policy.priority}>
              {policyLabel(policy)}
            </option>
          ))}
        </Select>
        <Button type="submit" variant="secondary" disabled={selected === current || pending}>
          {ACTION_LABEL.change_priority}
        </Button>
      </div>
    </form>
  )
}
