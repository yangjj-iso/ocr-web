import { renderHook, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock the runtime module
vi.mock('@/api/runtime', () => ({
  controlPlaneApiUrl: (path: string) => `http://localhost:8080${path}`,
}))

// Mock EventSource
class MockEventSource {
  static instances: MockEventSource[] = []
  url: string
  withCredentials: boolean
  onopen: (() => void) | null = null
  onerror: (() => void) | null = null
  listeners: Record<string, ((e: MessageEvent) => void)[]> = {}
  readyState = 0

  constructor(url: string, opts?: { withCredentials?: boolean }) {
    this.url = url
    this.withCredentials = opts?.withCredentials ?? false
    MockEventSource.instances.push(this)
  }

  addEventListener(type: string, handler: (e: MessageEvent) => void) {
    if (!this.listeners[type]) this.listeners[type] = []
    this.listeners[type].push(handler)
  }

  close() {
    this.readyState = 2
  }

  // Test helper: simulate open
  simulateOpen() {
    this.readyState = 1
    this.onopen?.()
  }

  // Test helper: simulate event
  simulateEvent(type: string, data: unknown) {
    const event = new MessageEvent(type, { data: JSON.stringify(data) })
    this.listeners[type]?.forEach((h) => h(event))
  }
}

beforeEach(() => {
  MockEventSource.instances = []
  vi.stubGlobal('EventSource', MockEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

import { useTaskSSE } from '@/hooks/use-task-sse'

describe('useTaskSSE', () => {
  it('connects on mount when enabled', () => {
    renderHook(() => useTaskSSE({ taskIds: [1, 2], enabled: true }))

    expect(MockEventSource.instances).toHaveLength(1)
    expect(MockEventSource.instances[0].url).toContain('taskIds=1')
    expect(MockEventSource.instances[0].url).toContain('taskIds=2')
  })

  it('does not connect when disabled', () => {
    renderHook(() => useTaskSSE({ enabled: false }))

    expect(MockEventSource.instances).toHaveLength(0)
  })

  it('reports isConnected after open', async () => {
    const taskIds = [1]
    const { result } = renderHook(() => useTaskSSE({ taskIds, enabled: true }))

    // Wait for useEffect to fire and create the EventSource
    await vi.waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0)
    })

    expect(result.current.isConnected).toBe(false)

    const es = MockEventSource.instances[MockEventSource.instances.length - 1]

    await act(async () => {
      es.onopen?.()
    })

    expect(result.current.isConnected).toBe(true)
  })

  it('calls onEvent callback when event received', async () => {
    const onEvent = vi.fn()
    renderHook(() => useTaskSSE({ taskIds: [1], onEvent }))

    await act(async () => {
      MockEventSource.instances[0].simulateOpen()
      MockEventSource.instances[0].simulateEvent('PROGRESS_UPDATED', {
        taskId: 1,
        percent: 50,
      })
    })

    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ type: 'PROGRESS_UPDATED', taskId: 1, percent: 50 })
    )
  })

  it('disconnects on unmount', () => {
    const { unmount } = renderHook(() => useTaskSSE({ taskIds: [1] }))

    const es = MockEventSource.instances[0]
    unmount()

    expect(es.readyState).toBe(2) // CLOSED
  })

  it('includes batchId in URL when provided', () => {
    renderHook(() => useTaskSSE({ batchId: 'batch-123' }))

    expect(MockEventSource.instances[0].url).toContain('batchId=batch-123')
  })
})
