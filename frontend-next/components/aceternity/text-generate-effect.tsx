'use client'

import * as React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

export function TextGenerateEffect({
  words,
  className,
  duration = 0.3,
}: {
  words: string
  className?: string
  duration?: number
}) {
  const characters = words.split('')

  return (
    <span className={cn('inline-block', className)}>
      {characters.map((char, i) => (
        <motion.span
          key={`${char}-${i}`}
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{
            duration,
            delay: i * 0.02,
            ease: 'easeOut',
          }}
          className="inline-block"
        >
          {char === ' ' ? ' ' : char}
        </motion.span>
      ))}
    </span>
  )
}
