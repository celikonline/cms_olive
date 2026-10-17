# Altın Gıda PWA ikonlarını marka renkleriyle üretir.
# Kullanım: powershell -ExecutionPolicy Bypass -File scripts\make_icons.ps1
param([string]$OutDir = (Join-Path $PSScriptRoot '..\public\icons'))
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

function New-Icon([int]$Size,[string]$Name,[double]$TextScale,[switch]$Ring){
  $bmp = New-Object System.Drawing.Bitmap $Size,$Size
  $gfx = [System.Drawing.Graphics]::FromImage($bmp)
  $gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
  $gfx.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
  $bg = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255,85,101,63))
  $gfx.FillRectangle($bg,0,0,$Size,$Size)
  if($Ring){
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(64,246,245,239)),([float]($Size*0.016))
    $gfx.DrawEllipse($pen,[float]($Size*0.17),[float]($Size*0.17),[float]($Size*0.66),[float]($Size*0.66))
    $pen.Dispose()
  }
  $font = New-Object System.Drawing.Font 'Georgia',([float]($Size*$TextScale)),([System.Drawing.FontStyle]::Bold),([System.Drawing.GraphicsUnit]::Pixel)
  $letters = @('A','G')
  $widths = @($letters | ForEach-Object { $gfx.MeasureString($_,$font).Width })
  $heights = @($letters | ForEach-Object { $gfx.MeasureString($_,$font).Height })
  $gap = $Size*0.015
  $x = ($Size-(($widths | Measure-Object -Sum).Sum+$gap))/2
  $brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255,246,245,239))
  for($i=0;$i -lt $letters.Count;$i++){
    $y = ($Size-$heights[$i])/2
    $gfx.DrawString($letters[$i],$font,$brush,[float]$x,[float]$y)
    $x += $widths[$i]+$gap
  }
  $brush.Dispose(); $font.Dispose(); $gfx.Dispose()
  $target = Join-Path $OutDir $Name
  $bmp.Save($target,[System.Drawing.Imaging.ImageFormat]::Png)
  $bmp.Dispose()
  Write-Host ("{0} ({1}x{1})" -f $Name,$Size)
}

New-Icon -Size 192 -Name 'icon-192.png' -TextScale 0.34
New-Icon -Size 512 -Name 'icon-512.png' -TextScale 0.34
New-Icon -Size 512 -Name 'maskable-512.png' -TextScale 0.24
New-Icon -Size 180 -Name 'apple-touch-icon.png' -TextScale 0.34
