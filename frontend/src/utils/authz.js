export function parseCapabilities(rawCapabilities) {
  return String(rawCapabilities || '')
    .split(',')
    .map((value) => value.trim().toLowerCase())
    .filter(Boolean)
}

export function buildAuthProfile(source = {}) {
  const role = String(source?.role || (source?.is_admin ? 'admin' : 'member')).trim() || 'member'
  const capabilities = parseCapabilities(source?.capabilities)
  const isTenantAdmin = role === 'tenant_admin'
  const isSysAdmin = Boolean(source?.is_admin) && !isTenantAdmin
  const isDualCapability = !isSysAdmin && !isTenantAdmin && capabilities.includes('operator') && capabilities.includes('searcher')
  const hasOperator = isSysAdmin || isTenantAdmin || capabilities.includes('operator')
  const hasSearcher = isSysAdmin || isTenantAdmin || capabilities.includes('searcher')

  let roleLabel = '租户成员'
  if (isSysAdmin) {
    roleLabel = '公司管理员'
  } else if (isTenantAdmin) {
    roleLabel = '租户管理员'
  } else if (isDualCapability) {
    roleLabel = '著录者+检索者'
  } else if (hasOperator) {
    roleLabel = '著录者'
  } else if (hasSearcher) {
    roleLabel = '检索者'
  }

  return {
    role,
    capabilities,
    isSysAdmin,
    isTenantAdmin,
    isDualCapability,
    hasOperator,
    hasSearcher,
    primaryWorkRole: hasOperator ? 'operator' : hasSearcher ? 'searcher' : 'member',
    roleLabel,
  }
}

export function hasAuthRole(source, expectedRole) {
  const profile = buildAuthProfile(source)
  if (expectedRole === 'sys_admin') return profile.isSysAdmin
  if (expectedRole === 'tenant_admin') return profile.isTenantAdmin
  if (expectedRole === 'operator') return profile.hasOperator
  if (expectedRole === 'searcher') return profile.hasSearcher
  return false
}

export function roleBasedHome(source) {
  const profile = buildAuthProfile(source)
  if (profile.isSysAdmin || profile.isTenantAdmin || profile.hasOperator) return '/dashboard'
  if (profile.hasSearcher) return '/archives'
  return '/dashboard'
}