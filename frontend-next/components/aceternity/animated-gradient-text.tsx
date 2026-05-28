'use client'

import * as React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

interface AnimatedGradientTextProps {
  children: React.ReactNode
  className?: string
  from?: string
  via?: string
  to?: string
}

export function AnimatedGradientText({
  children,
  className,
  from = '#1f4f88',
  via = '#6e46c8',
  to = '#1f4f88',
}: AnimatedGradientTextProps) {
  return (
    <motion.span
      className={cn('inline-block bg-clip-text text-transparent bg-[length:200%_auto] animate-shimmer', className)}
      style={{ backgroundImage: `linear-gradient(90deg, ${from}, ${via}, ${to}, ${via}, ${from})` }}
    >
      {children}
    </motion.span>
  )
}
