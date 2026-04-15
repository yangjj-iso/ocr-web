$ErrorActionPreference = 'Stop'
Set-Location 'D:\OCR_WEB\ocr\java-control-plane'
Get-Content 'D:\OCR_WEB\ocr\.env' | ForEach-Object {
  $line = $_.Trim()
  if (-not $line -or $line.StartsWith('#')) { return }
  $idx = $line.IndexOf('=')
  if ($idx -lt 1) { return }
  $key = $line.Substring(0, $idx)
  $value = $line.Substring($idx + 1)
  Set-Item -Path ("Env:" + $key) -Value $value
}
& 'C:\Program Files\Java\jdk-21\bin\java.exe' '-jar' 'target\java-control-plane-0.0.1-SNAPSHOT.jar'
