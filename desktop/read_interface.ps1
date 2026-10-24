param([long]$WindowHandle = 0)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type @'
using System;
using System.Runtime.InteropServices;
public class SnowBallWindow {
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll")] public static extern bool SetProcessDPIAware();
}
'@
[SnowBallWindow]::SetProcessDPIAware() | Out-Null
if ($WindowHandle -eq 0) { $WindowHandle = [SnowBallWindow]::GetForegroundWindow().ToInt64() }
$root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$WindowHandle)
if (-not $root) { throw 'Select a browser or application window and try again.' }
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$pending = New-Object 'System.Collections.Generic.Queue[System.Windows.Automation.AutomationElement]'
$pending.Enqueue($root)
$controls = New-Object System.Collections.Generic.List[object]
$visited = 0
$clock = [System.Diagnostics.Stopwatch]::StartNew()
while ($pending.Count -gt 0 -and $visited -lt 1500 -and $controls.Count -lt 180 -and $clock.Elapsed.TotalSeconds -lt 6) {
    $node = $pending.Dequeue()
    $visited++
    try {
        $info = $node.Current
        # Never read password controls, field values, or descendants of editors.
        $kind = $info.ControlType.ProgrammaticName.Replace('ControlType.', '')
        if ($info.IsPassword) { continue }
        $rect = $info.BoundingRectangle
        if (-not $info.IsOffscreen -and $rect.Width -gt 0 -and $rect.Height -gt 0) {
            $name = ($info.Name -replace '\s+', ' ').Trim()
            if ($name -and $kind -notin @('Window', 'Pane', 'Group', 'Document')) {
                $controls.Add([pscustomobject]@{
                    id = (($node.GetRuntimeId() | ForEach-Object { $_.ToString() }) -join '.')
                    name = $name.Substring(0, [Math]::Min(120, $name.Length))
                    role = $kind
                    enabled = $info.IsEnabled
                    rect = @([int]$rect.Left, [int]$rect.Top, [int]$rect.Width, [int]$rect.Height)
                })
            }
        }
        if ($kind -eq 'Edit') { continue }
        $child = $walker.GetFirstChild($node)
        while ($child -and $pending.Count -lt 1500 -and $clock.Elapsed.TotalSeconds -lt 6) {
            $pending.Enqueue($child)
            $child = $walker.GetNextSibling($child)
        }
    } catch { continue } # Controls can disappear as the page updates.
}
[pscustomobject]@{
    window = $WindowHandle
    title = $root.Current.Name
    process_id = $root.Current.ProcessId
    truncated = ($pending.Count -gt 0)
    elements = @($controls.ToArray())
} | ConvertTo-Json -Depth 5 -Compress
