'use client'

import * as React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

export function ShimmerButton({
  children,
  className,
  shimmerColor = 'hsl(245 58% 80% / 0.3)',
  disabled,
  onClick,
  type,
  ...props
}: {
  children: React.ReactNode
  className?: string
  shimmerColor?: string
  disabled?: boolean
  onClick?: () => void
  type?: 'button' | 'submit' | 'reset'
}) {
  return (
    <motion.button
      whileHover={disabled ? undefined : { scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.97 }}
      disabled={disabled}
      onClick={onClick}
      type={type}
      className={cn(
        'group relative inline-flex items-center justify-center overflow-hidden rounded-xl bg-primary px-6 py-3 text-sm font-semibold text-primary-foreground shadow-soft transition-shadow hover:shadow-glow-sm disabled:pointer-events-none disabled:opacity-50',
        className
      )}
    >
      <div
        className="absolute inset-0 -translate-x-full animate-[shimmer_2.5s_ease-in-out_infinite] bg-gradient-to-r from-transparent via-white/20 to-transparent"
        style={{ '--shimmer-color': shimmerColor } as React.CSSProperties}
      />
      <span className="relative z-10 flex items-center gap-2">{children}</span>
    </motion.button>
  )
}
