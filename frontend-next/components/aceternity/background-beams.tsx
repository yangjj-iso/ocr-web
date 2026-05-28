'use client'

import * as React from 'react'
import { motion } from 'framer-motion'
import { cn } from '@/lib/utils'

export function BackgroundBeams({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'pointer-events-none absolute inset-0 -z-10 overflow-hidden',
        className
      )}
    >
      <svg
        className="absolute inset-0 h-full w-full opacity-40"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="none"
        viewBox="0 0 100 100"
      >
        <defs>
          <linearGradient id="beam-gradient" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="hsl(245 58% 51%)" stopOpacity="0.12" />
            <stop offset="50%" stopColor="hsl(270 60% 55%)" stopOpacity="0.12" />
            <stop offset="100%" stopColor="hsl(245 58% 51%)" stopOpacity="0" />
          </linearGradient>
        </defs>
        {Array.from({ length: 12 }).map((_, idx) => (
          <motion.line
            key={idx}
            x1={5 + idx * 8}
            y1={-5}
            x2={20 + idx * 8}
            y2={110}
            stroke="url(#beam-gradient)"
            strokeWidth="0.4"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 0.7, 0] }}
            transition={{
              delay: idx * 0.3,
              duration: 4 + (idx % 3),
              repeat: Infinity,
              ease: 'easeInOut',
            }}
          />
        ))}
      </svg>
      <div className="absolute -left-40 -top-40 h-80 w-80 rounded-full bg-primary/8 blur-3xl" />
      <div className="absolute -bottom-40 -right-40 h-96 w-96 rounded-full bg-violet-500/8 blur-3xl" />
    </div>
  )
}
