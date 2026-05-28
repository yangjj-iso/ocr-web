'use client'

import { useCallback, useMemo, useState } from 'react'

const IDLE = 'idle'
const LOADING = 'loading'
const SUCCESS = 'success'
const ERROR = 'error'
const EMPTY = 'empty'

export type AsyncPhase = 'idle' | 'loading' | 'success' | 'error' | 'empty'

export type AsyncState<T> = {
  phase: AsyncPhase
  data: T | null
  error: string
  isLoading: boolean
  isError: boolean
  isEmpty: boolean
  setLoading: () => void
  setSuccess: (value?: T | null) => void
  setEmpty: (value?: T | null) => void
  setError: (message: string) => void
  reset: () => void
}

export function useAsyncState<T>(initialData: T | null = null): AsyncState<T> {
  const [phase, setPhase] = useState<AsyncPhase>(IDLE)
  const [data, setData] = useState<T | null>(initialData)
  const [error, setErrorState] = useState('')

  const setLoading = useCallback(() => {
    setPhase(LOADING)
    setErrorState('')
  }, [])

  const setSuccess = useCallback((value: T | null = null) => {
    setPhase(SUCCESS)
    setData(value)
    setErrorState('')
  }, [])

  const setEmpty = useCallback((value: T | null = null) => {
    setPhase(EMPTY)
    setData(value)
    setErrorState('')
  }, [])

  const setError = useCallback((message: string) => {
    setPhase(ERROR)
    setErrorState(String(message || '请求失败'))
  }, [])

  const reset = useCallback(() => {
    setPhase(IDLE)
    setData(initialData)
    setErrorState('')
  }, [initialData])

  return useMemo(
    () => ({
      phase,
      data,
      error,
      isLoading: phase === LOADING,
      isError: phase === ERROR,
      isEmpty: phase === EMPTY,
      setLoading,
      setSuccess,
      setEmpty,
      setError,
      reset,
    }),
    [phase, data, error, setLoading, setSuccess, setEmpty, setError, reset]
  )
}
