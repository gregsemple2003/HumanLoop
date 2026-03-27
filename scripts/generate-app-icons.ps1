param(
    [string]$OutputDirectory = (Join-Path $PSScriptRoot "..\\app\\static\\icons")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Drawing

function New-RoundedRectPath {
    param(
        [double]$X,
        [double]$Y,
        [double]$Width,
        [double]$Height,
        [double]$Radius
    )

    $diameter = $Radius * 2
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc($X, $Y, $diameter, $diameter, 180, 90)
    $path.AddArc($X + $Width - $diameter, $Y, $diameter, $diameter, 270, 90)
    $path.AddArc($X + $Width - $diameter, $Y + $Height - $diameter, $diameter, $diameter, 0, 90)
    $path.AddArc($X, $Y + $Height - $diameter, $diameter, $diameter, 90, 90)
    $path.CloseFigure()
    return $path
}

function New-HumanLoopBitmap {
    param(
        [int]$Size,
        [string]$BackgroundHex = "#91522f",
        [string]$BorderHex = "#e7d1b6",
        [string]$LetterHex = "#fff8ef",
        [string]$InkHex = "#221c16",
        [bool]$ShowAlertBadge = $false,
        [string]$BadgeFillHex = "#ffd36b",
        [string]$BadgeStrokeHex = "#221c16",
        [double]$BadgeScale = 0.24
    )

    $bitmap = New-Object System.Drawing.Bitmap $Size, $Size
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.Clear([System.Drawing.Color]::Transparent)

    $background = [System.Drawing.ColorTranslator]::FromHtml($BackgroundHex)
    $border = [System.Drawing.ColorTranslator]::FromHtml($BorderHex)
    $cream = [System.Drawing.ColorTranslator]::FromHtml($LetterHex)
    $ink = [System.Drawing.ColorTranslator]::FromHtml($InkHex)
    $badgeFill = [System.Drawing.ColorTranslator]::FromHtml($BadgeFillHex)
    $badgeStroke = [System.Drawing.ColorTranslator]::FromHtml($BadgeStrokeHex)

    $padding = [math]::Round($Size * 0.08)
    $outerSize = $Size - ($padding * 2)
    $outerRadius = [math]::Round($outerSize * 0.26)
    $outerPath = New-RoundedRectPath -X $padding -Y $padding -Width $outerSize -Height $outerSize -Radius $outerRadius

    $backgroundBrush = New-Object System.Drawing.SolidBrush $background
    $borderPen = New-Object System.Drawing.Pen -ArgumentList $border, ([float][math]::Max(2, [math]::Round($Size * 0.03)))
    $graphics.FillPath($backgroundBrush, $outerPath)
    $graphics.DrawPath($borderPen, $outerPath)

    $barWidth = [math]::Round($Size * 0.11)
    $barRadius = [math]::Round($barWidth / 2)
    $leftX = [math]::Round($Size * 0.29)
    $rightX = [math]::Round($Size * 0.60)
    $topY = [math]::Round($Size * 0.25)
    $barHeight = [math]::Round($Size * 0.50)
    $crossbarY = [math]::Round($Size * 0.45)
    $crossbarWidth = [math]::Round($Size * 0.27)

    $letterBrush = New-Object System.Drawing.SolidBrush $cream
    foreach ($barX in @($leftX, $rightX)) {
        $barPath = New-RoundedRectPath -X $barX -Y $topY -Width $barWidth -Height $barHeight -Radius $barRadius
        $graphics.FillPath($letterBrush, $barPath)
        $barPath.Dispose()
    }

    $crossbarPath = New-RoundedRectPath -X ($leftX + [math]::Round($barWidth * 0.82)) -Y $crossbarY -Width $crossbarWidth -Height $barWidth -Radius $barRadius
    $graphics.FillPath($letterBrush, $crossbarPath)

    $loopPen = New-Object System.Drawing.Pen -ArgumentList $ink, ([float][math]::Max(4, [math]::Round($Size * 0.035)))
    $loopPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
    $loopPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
    $loopBounds = [System.Drawing.RectangleF]::new(
        [float]([math]::Round($Size * 0.58)),
        [float]([math]::Round($Size * 0.58)),
        [float]([math]::Round($Size * 0.16)),
        [float]([math]::Round($Size * 0.16))
    )
    $graphics.DrawEllipse($loopPen, $loopBounds)
    $graphics.DrawLine(
        $loopPen,
        [float]([math]::Round($Size * 0.72)),
        [float]([math]::Round($Size * 0.64)),
        [float]([math]::Round($Size * 0.82)),
        [float]([math]::Round($Size * 0.64))
    )
    $graphics.DrawLine(
        $loopPen,
        [float]([math]::Round($Size * 0.82)),
        [float]([math]::Round($Size * 0.64)),
        [float]([math]::Round($Size * 0.82)),
        [float]([math]::Round($Size * 0.74))
    )

    if ($ShowAlertBadge) {
        $badgeDiameter = [math]::Round($Size * $BadgeScale)
        $badgeX = [math]::Round($Size * 0.62)
        $badgeY = [math]::Round($Size * 0.08)
        $badgeBrush = New-Object System.Drawing.SolidBrush $badgeFill
        $badgePen = New-Object System.Drawing.Pen -ArgumentList $badgeStroke, ([float][math]::Max(2, [math]::Round($Size * 0.024)))
        $graphics.FillEllipse($badgeBrush, $badgeX, $badgeY, $badgeDiameter, $badgeDiameter)
        $graphics.DrawEllipse($badgePen, $badgeX, $badgeY, $badgeDiameter, $badgeDiameter)

        $markPen = New-Object System.Drawing.Pen -ArgumentList $badgeStroke, ([float][math]::Max(2, [math]::Round($Size * 0.034)))
        $markPen.StartCap = [System.Drawing.Drawing2D.LineCap]::Round
        $markPen.EndCap = [System.Drawing.Drawing2D.LineCap]::Round
        $centerX = $badgeX + ($badgeDiameter / 2)
        $lineTop = $badgeY + ($badgeDiameter * 0.20)
        $lineBottom = $badgeY + ($badgeDiameter * 0.58)
        $dotY = $badgeY + ($badgeDiameter * 0.77)
        $dotDiameter = [math]::Max(2, [math]::Round($badgeDiameter * 0.13))

        $graphics.DrawLine(
            $markPen,
            [float]$centerX,
            [float]$lineTop,
            [float]$centerX,
            [float]$lineBottom
        )
        $graphics.FillEllipse(
            $badgeBrush,
            [float]($centerX - ($dotDiameter / 2)),
            [float]($dotY - ($dotDiameter / 2)),
            [float]$dotDiameter,
            [float]$dotDiameter
        )

        $markPen.Dispose()
        $badgePen.Dispose()
        $badgeBrush.Dispose()
    }

    $crossbarPath.Dispose()
    $loopPen.Dispose()
    $letterBrush.Dispose()
    $borderPen.Dispose()
    $backgroundBrush.Dispose()
    $outerPath.Dispose()
    $graphics.Dispose()

    return $bitmap
}

function Save-PngIcon {
    param(
        [int]$Size,
        [string]$Path,
        [hashtable]$Variant = @{}
    )

    $bitmap = New-HumanLoopBitmap -Size $Size @Variant
    try {
        $bitmap.Save($Path, [System.Drawing.Imaging.ImageFormat]::Png)
    } finally {
        $bitmap.Dispose()
    }
}

function Save-IcoIcon {
    param(
        [int]$Size,
        [string]$Path,
        [hashtable]$Variant = @{}
    )

    $bitmap = New-HumanLoopBitmap -Size $Size @Variant
    try {
        $icon = [System.Drawing.Icon]::FromHandle($bitmap.GetHicon())
        try {
            $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create)
            try {
                $icon.Save($stream)
            } finally {
                $stream.Dispose()
            }
        } finally {
            $icon.Dispose()
        }
    } finally {
        $bitmap.Dispose()
    }
}

$resolvedOutput = [System.IO.Path]::GetFullPath($OutputDirectory)
[System.IO.Directory]::CreateDirectory($resolvedOutput) | Out-Null

$browserVariant = @{
    BackgroundHex = "#91522f"
    BorderHex = "#e7d1b6"
    LetterHex = "#fff8ef"
    InkHex = "#221c16"
}
$desktopIdleVariant = @{
    BackgroundHex = "#68706f"
    BorderHex = "#d7dddc"
    LetterHex = "#f7f7f3"
    InkHex = "#1d2423"
}
$desktopAlertVariant = @{
    BackgroundHex = "#ff7a00"
    BorderHex = "#fff0da"
    LetterHex = "#fffdf8"
    InkHex = "#271406"
    ShowAlertBadge = $true
    BadgeFillHex = "#fff06e"
    BadgeStrokeHex = "#271406"
    BadgeScale = 0.28
}

Save-PngIcon -Size 32 -Path (Join-Path $resolvedOutput "humanloop-32.png") -Variant $browserVariant
Save-PngIcon -Size 192 -Path (Join-Path $resolvedOutput "humanloop-192.png") -Variant $browserVariant
Save-PngIcon -Size 512 -Path (Join-Path $resolvedOutput "humanloop-512.png") -Variant $browserVariant
Save-IcoIcon -Size 64 -Path (Join-Path $resolvedOutput "favicon.ico") -Variant $browserVariant
Save-PngIcon -Size 32 -Path (Join-Path $resolvedOutput "humanloop-desktop-idle-32.png") -Variant $desktopIdleVariant
Save-PngIcon -Size 64 -Path (Join-Path $resolvedOutput "humanloop-desktop-idle-64.png") -Variant $desktopIdleVariant
Save-PngIcon -Size 128 -Path (Join-Path $resolvedOutput "humanloop-desktop-idle-128.png") -Variant $desktopIdleVariant
Save-IcoIcon -Size 64 -Path (Join-Path $resolvedOutput "humanloop-desktop-idle.ico") -Variant $desktopIdleVariant
Save-PngIcon -Size 32 -Path (Join-Path $resolvedOutput "humanloop-desktop-alert-32.png") -Variant $desktopAlertVariant
Save-PngIcon -Size 64 -Path (Join-Path $resolvedOutput "humanloop-desktop-alert-64.png") -Variant $desktopAlertVariant
Save-PngIcon -Size 128 -Path (Join-Path $resolvedOutput "humanloop-desktop-alert-128.png") -Variant $desktopAlertVariant
Save-IcoIcon -Size 64 -Path (Join-Path $resolvedOutput "humanloop-desktop-alert.ico") -Variant $desktopAlertVariant

Write-Host "Generated HumanLoop app icons in $resolvedOutput"
