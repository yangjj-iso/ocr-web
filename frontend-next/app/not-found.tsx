import Link from 'next/link'
import { FileQuestion } from 'lucide-react'
import { Button } from '@/components/ui/button'

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-6 px-4 text-center">
      <div className="flex h-16 w-16 items-center justify-center rounded-full bg-muted">
        <FileQuestion className="h-8 w-8 text-muted-foreground" />
      </div>
      <div className="space-y-2">
        <h2 className="text-xl font-semibold tracking-tight">页面不存在</h2>
        <p className="text-sm text-muted-foreground max-w-md">
          你访问的页面可能已被移除或地址有误。
        </p>
      </div>
      <Button asChild variant="outline">
        <Link href="/">返回首页</Link>
      </Button>
    </div>
  )
}
