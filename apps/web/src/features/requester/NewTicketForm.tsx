import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, type RefObject, useRef, useState } from 'react'
import { flushSync } from 'react-dom'
import { useNavigate } from 'react-router'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { Button } from '../../ui/Button'
import { ButtonLink } from '../../ui/ButtonLink'
import { ErrorNotice, LoadingNotice } from '../../ui/Notice'
import { Panel } from '../../ui/Panel'
import { Select } from '../../ui/Select'
import { TextArea } from '../../ui/TextArea'
import { TextField } from '../../ui/TextField'
import { homePathFor } from '../auth/access'
import { refreshTicketLists } from '../tickets/queries'
import type { Category, Priority, SlaPolicy } from '../tickets/types'
import styles from './NewTicketForm.module.css'
import {
  firstErrorField,
  serverFieldErrors,
  type TicketFormErrors,
  type TicketFormField,
  validateTicketDraft,
} from './ticketForm'

const DEFAULT_PRIORITY: Priority = 'medium'
const MY_TICKETS_PATH = homePathFor('requester')
const LOAD_FAILURE = 'Bip-bup: no pude preparar el formulario. Intenta de nuevo.'
const CREATE_FAILURE = 'Bip-bup: no pude crear el ticket. Intenta de nuevo.'

export function NewTicketForm() {
  return (
    <div className={styles.page}>
      <h1>Nuevo ticket</h1>
      <p className={styles.intro}>Cuéntanos qué necesitas: un agente lo atenderá según su prioridad.</p>
      <Panel title="Datos del ticket">
        <FormOptions />
      </Panel>
    </div>
  )
}

/** Carga las categorías y las prioridades, que el formulario necesita para ofrecerlas. */
function FormOptions() {
  const categories = $api.useQuery('get', '/api/v1/categories')
  const policies = $api.useQuery('get', '/api/v1/sla-policies')

  if (categories.isError || policies.isError) {
    return <ErrorNotice message={serverMessage(categories.error ?? policies.error) ?? LOAD_FAILURE} />
  }
  if (!categories.data || !policies.data) return <LoadingNotice message="Bip-bup: preparando el formulario..." />
  return <TicketFields categories={categories.data} policies={policies.data} />
}

interface TicketFieldsProps {
  categories: Category[]
  policies: SlaPolicy[]
}

function TicketFields({ categories, policies }: TicketFieldsProps) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [priority, setPriority] = useState(DEFAULT_PRIORITY)
  const [errors, setErrors] = useState<TicketFormErrors>({})
  const titleInput = useRef<HTMLInputElement>(null)
  const descriptionInput = useRef<HTMLTextAreaElement>(null)
  const categoryInput = useRef<HTMLSelectElement>(null)
  const inputs: Record<TicketFormField, RefObject<HTMLElement | null>> = {
    title: titleInput,
    description: descriptionInput,
    category: categoryInput,
  }
  const create = $api.useMutation('post', '/api/v1/tickets', {
    onSuccess: async () => {
      await refreshTicketLists(queryClient)
      navigate(MY_TICKETS_PATH)
    },
    onError: (error) => showErrors(serverFieldErrors(error)),
  })
  const rejectedByField = firstErrorField(serverFieldErrors(create.error)) !== undefined
  const guide = policies.find((policy) => policy.priority === priority)?.description

  function dismissError(field: TicketFormField) {
    setErrors((current) => ({ ...current, [field]: undefined }))
  }

  function showErrors(found: TicketFormErrors) {
    // Síncrono: el campo ya debe estar descrito por su error cuando recibe el foco, para que se anuncie.
    flushSync(() => setErrors(found))
    const first = firstErrorField(found)
    if (first) inputs[first].current?.focus()
  }

  function pickPriority(picked: string) {
    const policy = policies.find((candidate) => candidate.priority === picked)
    if (policy) setPriority(policy.priority)
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validateTicketDraft({ title, description, categoryId })
    showErrors(found)
    if (firstErrorField(found)) return
    create.mutate({
      body: { title: title.trim(), description: description.trim(), category_id: Number(categoryId), priority },
    })
  }

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      <TextField
        ref={titleInput}
        label="Título"
        required
        value={title}
        error={errors.title}
        onChange={(event) => {
          setTitle(event.target.value)
          dismissError('title')
        }}
      />
      <TextArea
        ref={descriptionInput}
        label="Descripción"
        rows={6}
        required
        value={description}
        error={errors.description}
        onChange={(event) => {
          setDescription(event.target.value)
          dismissError('description')
        }}
      />
      <Select
        ref={categoryInput}
        label="Categoría"
        required
        value={categoryId}
        error={errors.category}
        onChange={(event) => {
          setCategoryId(event.target.value)
          dismissError('category')
        }}
      >
        <option value="">Elige una categoría</option>
        {categories.map((category) => (
          <option key={category.id} value={category.id}>
            {category.name}
          </option>
        ))}
      </Select>
      <Select label="Prioridad" hint={guide} value={priority} onChange={(event) => pickPriority(event.target.value)}>
        {policies.map((policy) => (
          <option key={policy.priority} value={policy.priority}>
            {policy.label}
          </option>
        ))}
      </Select>
      {create.isError && !rejectedByField && <ErrorNotice message={serverMessage(create.error) ?? CREATE_FAILURE} />}
      <div className={styles.actions}>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? 'Creando...' : 'Crear ticket'}
        </Button>
        <ButtonLink to={MY_TICKETS_PATH} variant="secondary">
          Cancelar
        </ButtonLink>
      </div>
    </form>
  )
}
