import { useSearchParams } from 'react-router'
import { type FilterParam, type ListFilters, readFilters, withoutFilters, withParam } from './listFilters'

interface UseListFilters {
  filters: ListFilters
  setFilter: (name: FilterParam, value: string) => void
  clear: () => void
}

/** Los filtros y el orden del listado viven en la URL; cambiarlos conserva el resto de los parámetros, como `view`. */
export function useListFilters(): UseListFilters {
  const [searchParams, setSearchParams] = useSearchParams()

  return {
    filters: readFilters(searchParams),
    // `replace`: ajustar un filtro no debe llenar el historial de pasos a los que "Atrás" tenga que volver.
    setFilter: (name, value) => setSearchParams((current) => withParam(current, name, value), { replace: true }),
    clear: () => setSearchParams(withoutFilters, { replace: true }),
  }
}
