#Requires -Version 7.0
<#
.SYNOPSIS
    JLCPCB用のガーバー、アセンブリデータを出力するスクリプト
.DESCRIPTION
    KiCad 10.0 の CLI を使用して、JLCPCB への発注に必要なファイルを一括生成します。
    実行には PowerShell 7 以上が必要です。
.NOTES
    ファイル名: export_jlcpcb.ps1
#>

$ErrorActionPreference = "Stop"

# -----------------------------------------------------------------------------
# 1. 設定
# -----------------------------------------------------------------------------
# KiCad CLI のパスを解決（PATH優先、なければ標準インストール先を探索）
$kicadCli = Get-Command "kicad-cli.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
if (-not $kicadCli) {
    $candidates = @(
        "C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
        "C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
        "C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
        "C:\Program Files\KiCad\7.0\bin\kicad-cli.exe"
    )
    foreach ($c in $candidates) {
        if (Test-Path $c) {
            $kicadCli = $c
            break
        }
    }
}
if (-not $kicadCli) {
    throw "kicad-cli.exe が見つかりません。KiCad をインストールしているか確認してください。"
}

# プロジェクトパスを自動取得（スクリプト配置フォルダを基準）
$projDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pcbFile = Get-ChildItem -Path $projDir -Filter "*.kicad_pcb" | Select-Object -First 1
$schFile = Get-ChildItem -Path $projDir -Filter "*.kicad_sch" | Select-Object -First 1

if (-not $pcbFile) { throw "*.kicad_pcb が見つかりません。スクリプトをプロジェクトフォルダに配置してください。" }
if (-not $schFile) { throw "*.kicad_sch が見つかりません。" }

$pcb = $pcbFile.FullName
$sch = $schFile.FullName
$projName = [System.IO.Path]::GetFileNameWithoutExtension($pcbFile.Name)

# 出力先
$outDir = Join-Path $projDir "jlcpcb_output"
$gerberDir = Join-Path $outDir "gerbers"
$asmDir = Join-Path $outDir "assembly"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project : $projName"
Write-Host "PCB     : $pcb"
Write-Host "SCH     : $sch"
Write-Host "KiCad   : $kicadCli"
Write-Host "Output  : $outDir"
Write-Host "========================================" -ForegroundColor Cyan

# -----------------------------------------------------------------------------
# 2. 出力ディレクトリの準備
# -----------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $gerberDir | Out-Null
New-Item -ItemType Directory -Force -Path $asmDir | Out-Null

# -----------------------------------------------------------------------------
# 3. ガーバー出力
# -----------------------------------------------------------------------------
Write-Host "`n[1/5] Exporting Gerbers..." -ForegroundColor Yellow
& "$kicadCli" pcb export gerbers --board-plot-params -o "$gerberDir" "$pcb"
if ($LASTEXITCODE -ne 0) { throw "Gerber export failed" }

# -----------------------------------------------------------------------------
# 4. ドリル出力
# -----------------------------------------------------------------------------
Write-Host "`n[2/5] Exporting Drill Files..." -ForegroundColor Yellow
& "$kicadCli" pcb export drill -o "$gerberDir" "$pcb"
if ($LASTEXITCODE -ne 0) { throw "Drill export failed" }

# -----------------------------------------------------------------------------
# 5. Pick & Place (POS) 出力
# -----------------------------------------------------------------------------
Write-Host "`n[3/5] Exporting Pick & Place (POS)..." -ForegroundColor Yellow
$posRaw = Join-Path $asmDir "${projName}-pos.csv"
& "$kicadCli" pcb export pos --format csv --units mm --side both -o "$posRaw" "$pcb"
if ($LASTEXITCODE -ne 0) { throw "POS export failed" }

# -----------------------------------------------------------------------------
# 6. BOM 出力
# -----------------------------------------------------------------------------
Write-Host "`n[4/5] Exporting BOM..." -ForegroundColor Yellow
$bomRaw = Join-Path $asmDir "${projName}-bom.csv"
& "$kicadCli" sch export bom -o "$bomRaw" "$sch"
if ($LASTEXITCODE -ne 0) { throw "BOM export failed" }

# -----------------------------------------------------------------------------
# 7. JLCPCB フォーマット変換
# -----------------------------------------------------------------------------
Write-Host "`n[5/5] Converting to JLCPCB format..." -ForegroundColor Yellow

# --- CPL (Pick & Place) ---
$posData = Import-Csv -Path $posRaw
$posResult = @()
$posResult += "Designator,Mid X,Mid Y,Layer,Rotation"
foreach ($row in $posData) {
    $layer = if ($row.Side -eq "top") { "T" } else { "B" }
    $posResult += "{0},{1},{2},{3},{4}" -f $row.Ref, $row.PosX, $row.PosY, $layer, $row.Rot
}
$posOut = Join-Path $asmDir "${projName}-cpl.csv"
$posResult | Out-File -FilePath $posOut -Encoding utf8
Write-Host "  CPL -> $posOut" -ForegroundColor Green

# --- BOM (JLCPCB用: マウントホール・DNP除外) ---
$bomData = Import-Csv -Path $bomRaw
$bomResult = @()
$bomResult += "Comment,Designator,Footprint,LCSC Part #"
foreach ($row in $bomData) {
    # マウントホールを除外
    if ($row.Value -eq "MountingHole") { continue }
    # DNP（実装除外）を除外
    if ($row.DNP -eq "True" -or $row.DNP -eq "1") { continue }
    # ライブラリ名プレフィックスを除去してフットプリント名を簡潔化
    $footprint = $row.Footprint -replace "^[^:]+:", ""
    $bomResult += "{0},{1},{2}," -f $row.Value, $row.Refs, $footprint
}
$bomOut = Join-Path $asmDir "${projName}-bom-jlc.csv"
$bomResult | Out-File -FilePath $bomOut -Encoding utf8
Write-Host "  BOM -> $bomOut" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 8. ガーバーを ZIP 圧縮
# -----------------------------------------------------------------------------
$zipFile = Join-Path $outDir "${projName}-gerbers.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }
Compress-Archive -Path "$gerberDir\*" -DestinationPath $zipFile
Write-Host "  ZIP -> $zipFile" -ForegroundColor Green

# -----------------------------------------------------------------------------
# 9. サマリー
# -----------------------------------------------------------------------------
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Done! JLCPCB output files generated:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`n[PCB Fabrication]"
Write-Host "  Gerber ZIP : $zipFile"
Write-Host "`n[PCB Assembly (PCBA)]"
Write-Host "  BOM        : $bomOut"
Write-Host "  CPL (POS)  : $posOut"
Write-Host "`n[Raw Files]"
Write-Host "  Raw BOM    : $bomRaw"
Write-Host "  Raw POS    : $posRaw"

Write-Host "`n[Next Steps]" -ForegroundColor Yellow
Write-Host "  1. JLCPCBサイトで Gerber ZIP をアップロード（PCB発注）"
Write-Host "  2. PCBA発注の場合: BOM と CPL をアップロード"
Write-Host "  3. BOM内の 'LCSC Part #' 列に部品番号を手動で登録・マッチング"
Write-Host "  4. マウントホール（H1-H4等）は実装対象から除外してください"
Write-Host "========================================" -ForegroundColor Cyan
