<#
Save selected real XLSX fixtures through installed desktop Excel.
Outputs and Excel's independent TEXT results stay under the repository's tmp.
This script does not generate or approve formal fixtures or golden baselines.
#>
[CmdletBinding()]
param(
    [string[]]$Pattern = @('xlsx-format-number-*.xlsx', 'xlsx-format-percent.xlsx', 'xlsx-format-currency-*.xlsx'),
    [string]$OutputDirectory = 'tmp/xls-number-percent',
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$fixtureRoot = Join-Path $repoRoot 'test_support/fixtures/xlsx'
$tmpRoot = [IO.Path]::GetFullPath((Join-Path $repoRoot 'tmp'))
$destination = [IO.Path]::GetFullPath((Join-Path $repoRoot $OutputDirectory))
if (-not $destination.StartsWith($tmpRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'OutputDirectory must be a subdirectory of this repository''s tmp folder.'
}
$sources = @(foreach ($item in $Pattern) {
    Get-ChildItem -LiteralPath $fixtureRoot -Filter $item -File
})
$sources = @($sources | Sort-Object FullName -Unique)
if ($sources.Count -eq 0) { throw 'No XLSX fixtures matched Pattern.' }
foreach ($source in $sources) {
    $output = Join-Path $destination ($source.BaseName + '.xls')
    if ((Test-Path -LiteralPath $output) -and -not $Force) {
        throw "Output already exists; use -Force to replace the temporary conversion: $output"
    }
}
[void](New-Item -ItemType Directory -Path $destination -Force)

function Release-ComObject($Value) {
    if ($null -ne $Value -and [Runtime.InteropServices.Marshal]::IsComObject($Value)) {
        [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($Value)
    }
}

function Get-WorkbookContent($Application, $Book) {
    $sheets = [Collections.Generic.List[object]]::new()
    $worksheets = $Book.Worksheets
    try {
        for ($index = 1; $index -le $worksheets.Count; $index++) {
            $sheet = $worksheets.Item($index)
            $used = $null
            try {
                $cells = [Collections.Generic.List[object]]::new()
                $used = $sheet.UsedRange
                # Only existing constants/formulas, not style-only empty cells.
                foreach ($cellType in @(2, -4123)) {
                    $content = $null
                    try { $content = $used.SpecialCells($cellType) }
                    catch [Runtime.InteropServices.COMException] { continue }
                    try {
                        foreach ($cell in $content.Cells) {
                            try {
                                $value = $cell.Value2
                                $isError = $Application.WorksheetFunction.IsError($cell)
                                $kind = if ($isError) { 'error' } elseif ($value -is [bool]) { 'boolean' } elseif ($value -is [string]) { 'string' } else { 'number' }
                                if ($isError) { $value = [string]$cell.Text }
                                $display = if ($kind -eq 'number') {
                                    [string]$Application.WorksheetFunction.Text($value, $cell.NumberFormat)
                                } elseif ($kind -eq 'boolean') {
                                    if ($value) { 'TRUE' } else { 'FALSE' }
                                } else { [string]$value }
                                $cells.Add([ordered]@{
                                    row = [int]$cell.Row
                                    column = [int]$cell.Column
                                    kind = $kind
                                    value = $value
                                    from_formula = [bool]$cell.HasFormula
                                    display_text = $display
                                    cell_text = [string]$cell.Text
                                    format_code = [string]$cell.NumberFormat
                                })
                            } finally { Release-ComObject $cell }
                        }
                    } finally { Release-ComObject $content }
                }
                $state = switch ([int]$sheet.Visible) { -1 { 'visible' } 0 { 'hidden' } 2 { 'veryHidden' } }
                $sheets.Add([ordered]@{
                    name = [string]$sheet.Name
                    state = $state
                    cells = @($cells | Sort-Object row, column)
                })
            } finally {
                Release-ComObject $used
                Release-ComObject $sheet
            }
        }
    } finally { Release-ComObject $worksheets }
    return ,$sheets.ToArray()
}

$excel = $null
$books = $null
$results = [Collections.Generic.List[object]]::new()
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $excel.EnableEvents = $false
    $excel.AskToUpdateLinks = $false
    $excel.AutomationSecurity = 3
    $books = $excel.Workbooks
    foreach ($source in $sources) {
        $book = $null
        $sourceHash = (Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256).Hash
        $output = Join-Path $destination ($source.BaseName + '.xls')
        try {
            $book = $books.Open($source.FullName, 0, $true)
            $book.CheckCompatibility = $false
            $before = Get-WorkbookContent $excel $book
            $book.SaveAs($output, 56)
            $book.Close($false)
            Release-ComObject $book
            $book = $null
            $book = $books.Open($output, 0, $true)
            $after = Get-WorkbookContent $excel $book
            if ([int]$book.FileFormat -ne 56) { throw "Excel did not save BIFF8: $output" }
            if ((Get-FileHash -LiteralPath $source.FullName -Algorithm SHA256).Hash -ne $sourceHash) {
                throw "Source fixture changed during conversion: $($source.FullName)"
            }
            $results.Add([ordered]@{
                source = $source.FullName
                source_sha256 = $sourceHash
                path = $output
                sha256 = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash
                date_1904 = [bool]$book.Date1904
                before = $before
                sheets = $after
            })
            Write-Host "Converted $($source.Name)"
        } finally {
            if ($null -ne $book) { $book.Close($false); Release-ComObject $book }
        }
    }
    $manifest = [ordered]@{
        producer = 'Microsoft Excel'
        version = [string]$excel.Version
        build = [string]$excel.Build
        file_format = 56
        display_oracle = 'Excel TEXT(Value2, NumberFormat); cell_text also retains the width-dependent display'
        files = $results.ToArray()
    }
    $manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $destination 'excel-oracle.json') -Encoding utf8
    Write-Host "Saved $($results.Count) XLS files and excel-oracle.json to $destination"
} finally {
    Release-ComObject $books
    if ($null -ne $excel) { $excel.Quit(); Release-ComObject $excel }
}
