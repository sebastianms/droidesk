import { useRef } from 'react'
import { Button } from '../../ui/Button'
import { Select } from '../../ui/Select'
import styles from './ListControls.module.css'
import { PRIORITY_LABEL, SLA_STATE_LABEL, SORT_LABEL, shownCountLabel } from './labels'
import {
  type FilterParam,
  isCustomized,
  isFiltering,
  type ListFilters,
  PRIORITIES,
  SLA_STATES,
  SORT_KEYS,
} from './listFilters'

interface ListControlsProps {
  filters: ListFilters
  shown: number
  total: number
  onChange: (name: FilterParam, value: string) => void
  onClear: () => void
}

/** Filtros por prioridad y SLA, orden, y cuántos tickets quedan a la vista. */
export function ListControls({ filters, shown, total, onChange, onClear }: ListControlsProps) {
  const firstControl = useRef<HTMLSelectElement>(null)

  function clear() {
    onClear()
    // El botón desaparece al limpiar: el foco pasa al primer control en vez de perderse.
    firstControl.current?.focus()
  }

  return (
    <div>
      <div className={styles.controls}>
        <Select
          ref={firstControl}
          label="Prioridad"
          value={filters.priority ?? ''}
          onChange={(event) => onChange('priority', event.target.value)}
        >
          <option value="">Todas</option>
          <Options values={PRIORITIES} labels={PRIORITY_LABEL} />
        </Select>
        <Select label="SLA" value={filters.sla ?? ''} onChange={(event) => onChange('sla', event.target.value)}>
          <option value="">Todos</option>
          <Options values={SLA_STATES} labels={SLA_STATE_LABEL} />
        </Select>
        <Select
          label="Ordenar por"
          value={filters.sort ?? ''}
          onChange={(event) => onChange('sort', event.target.value)}
        >
          <option value="">Predeterminado</option>
          <Options values={SORT_KEYS} labels={SORT_LABEL} />
        </Select>
        {isCustomized(filters) && (
          <Button variant="secondary" className={styles.clear} onClick={clear}>
            Limpiar filtros
          </Button>
        )}
      </div>
      {/* Siempre montada, aunque vacía, para que el lector de pantalla anuncie el conteo cuando aparece. */}
      <p aria-live="polite" className={styles.summary}>
        {isFiltering(filters) && shownCountLabel(shown, total)}
      </p>
    </div>
  )
}

function Options<K extends string>({ values, labels }: { values: readonly K[]; labels: Record<K, string> }) {
  return values.map((value) => (
    <option key={value} value={value}>
      {labels[value]}
    </option>
  ))
}
