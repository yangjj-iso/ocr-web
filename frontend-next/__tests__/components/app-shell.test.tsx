import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock next/navigation
vi.mock('next/navigation', () => ({
  usePathname: () => '/',
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))

// Mock framer-motion to avoid animation issues in tests
vi.mock('framer-motion', () => ({
  motion: new Proxy({}, {
    get: (_target, prop) => {
      return ({ children, ...props }: any) => {
        const { whileHover, layoutId, initial, animate, exit, transition, ...domProps } = props
        const Tag = String(prop)
        return <Tag {...domProps}>{children}</Tag>
      }
    }
  }) as any,
  AnimatePresence: ({ children }: any) => <>{children}</>,
}))

// Mock aceternity component
vi.mock('@/components/aceternity/animated-gradient-text', () => ({
  AnimatedGradientText: ({ children }: any) => <span>{children}</span>,
}))

// Mock auth hook
vi.mock('@/hooks/use-auth-state', () => ({
  useAuthState: () => ({
    auth: { enabled: true, is_admin: true, username: 'admin' },
    refreshAuthStatus: vi.fn().mockResolvedValue(undefined),
    logout: vi.fn().mockResolvedValue(undefined),
  }),
}))

import { AppShell } from '@/components/app-shell'

describe('AppShell', () => {
  it('renders navigation items', () => {
    render(<AppShell><div>content</div></AppShell>)

    expect(screen.getByText('首页')).toBeInTheDocument()
    expect(screen.getByText('工作台')).toBeInTheDocument()
    expect(screen.getByText('问答台')).toBeInTheDocument()
    expect(screen.getByText('信息检索')).toBeInTheDocument()
  })

  it('renders children content', () => {
    render(<AppShell><div data-testid="child">hello</div></AppShell>)

    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.getByText('hello')).toBeInTheDocument()
  })

  it('shows org link for admin users', () => {
    render(<AppShell><div>content</div></AppShell>)

    expect(screen.getByText('组织架构')).toBeInTheDocument()
  })
})
